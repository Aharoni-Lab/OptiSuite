from __future__ import annotations

import time
from typing import Callable, Optional

import cv2
import numpy as np

import autofocus as af

MIN_INTENSITY = 0
MAX_INTENSITY = 100
# Coarse 10% samples, then 2% steps in a 20%-wide window around the best.
CANDIDATE_INTENSITIES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
FINE_STEP = 2
FINE_WINDOW = 20


def clamp_intensity(value) -> int:
    return int(max(MIN_INTENSITY, min(MAX_INTENSITY, round(float(value)))))


def fine_intensities(center: int) -> list[int]:
    """2% steps across a 20% region centered on the coarse best intensity."""
    lo = clamp_intensity(center - FINE_WINDOW // 2)
    hi = clamp_intensity(center + FINE_WINDOW // 2)
    return list(range(lo, hi + 1, FINE_STEP))


def frame_to_gray(frame) -> np.ndarray:
    """Convert a captured camera frame to 8-bit grayscale."""
    if frame is None:
        raise ValueError("No camera frame available for laplacian scoring")
    image = np.asarray(frame)
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.uint8, copy=False)


def measure_laplacian_score(frame) -> dict:
    """Return Laplacian-variance focus score (higher is sharper / better exposed)."""
    gray_u8 = frame_to_gray(frame)
    if gray_u8.size == 0:
        raise ValueError("Captured frame has no pixels")
    gray = gray_u8.astype(np.float32) / 255.0
    return {"score": float(af.focus_score(gray, metric="laplacian_var"))}


class AutoSolidIntensityController:
    """Sample projector intensities and keep the one with the best Laplacian score."""

    def __init__(
        self,
        *,
        cam_index: int,
        take_screenshot: Callable[[int, Optional[str], str, int], Optional[str]],
        set_intensity: Callable[[int], None],
        log: Callable[[str], None] = print,
        start_intensity: int = 50,
    ):
        self.cam_index = int(cam_index)
        self.take_screenshot = take_screenshot
        self.set_intensity = set_intensity
        self.log = log
        self.intensity = clamp_intensity(start_intensity)
        self.step = 0
        self.best_intensity = self.intensity
        self.best_score = float("-inf")
        self._phase = "coarse"
        self._scored = set()
        self._queue = [self.intensity] + [c for c in CANDIDATE_INTENSITIES if c != self.intensity]

    def suggest_next_intensity(self, frame) -> tuple[int, dict, bool]:
        """Score the current photo and return (next_intensity, stats, done)."""
        stats = measure_laplacian_score(frame)
        stats["intensity"] = self.intensity
        self._scored.add(self.intensity)
        self.step += 1

        if float(stats["score"]) > self.best_score:
            self.best_score = float(stats["score"])
            self.best_intensity = self.intensity

        if self.step >= len(self._queue):
            if self._phase == "coarse":
                extra = [i for i in fine_intensities(self.best_intensity) if i not in self._scored]
                self.log(
                    f"[AutoSolid] coarse best={self.best_intensity}% "
                    f"(laplacian={self.best_score:.6g}); fine scan {extra}"
                )
                if extra:
                    self._phase = "fine"
                    self._queue.extend(extra)
                else:
                    return self._finish(stats)

            if self.step >= len(self._queue):
                return self._finish(stats)

        self.intensity = self._queue[self.step]
        stats["next_intensity"] = self.intensity
        return self.intensity, stats, False

    def _finish(self, stats: dict) -> tuple[int, dict, bool]:
        self.intensity = self.best_intensity
        stats["done_reason"] = "best_laplacian"
        stats["best_intensity"] = self.best_intensity
        stats["best_score"] = self.best_score
        return self.intensity, stats, True

    def run(self, *, out_dir=None, settle_s: float = 0.5, warmup_frames: int = 10) -> tuple[int, dict]:
        """Set intensity, capture a screenshot, and keep the best Laplacian score."""
        while True:
            self.set_intensity(self.intensity)
            if settle_s > 0:
                time.sleep(float(settle_s))

            prefix = f"auto_solid_{self.intensity}"
            img_path = self.take_screenshot(self.cam_index, out_dir, prefix, warmup_frames)
            if not img_path:
                raise RuntimeError(f"Screenshot failed at intensity={self.intensity}%")

            frame = cv2.imread(str(img_path))
            _nxt, stats, done = self.suggest_next_intensity(frame)
            self.log(
                f"[AutoSolid] step={self.step} intensity={stats['intensity']}% "
                f"laplacian={stats['score']:.6g} image={img_path}"
            )
            if done:
                self.set_intensity(self.intensity)
                self.log(
                    f"[AutoSolid] settled at {self.intensity}% "
                    f"(best laplacian={self.best_score:.6g})"
                )
                return self.intensity, stats

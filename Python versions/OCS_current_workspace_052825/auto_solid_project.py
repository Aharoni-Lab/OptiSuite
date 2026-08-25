from __future__ import annotations

import time
from typing import Callable, Optional

import cv2
import numpy as np


TARGET_SPLIT = 125
TARGET_FRAC_BELOW = 0.5
FRAC_TOLERANCE = 0.05
MEDIAN_TOLERANCE = 8
MIN_INTENSITY = 0
MAX_INTENSITY = 100
MAX_STEPS = 10


def clamp_intensity(value) -> int:
    return int(max(MIN_INTENSITY, min(MAX_INTENSITY, round(float(value)))))


def frame_to_gray(frame) -> np.ndarray:
    """Convert a captured camera frame to 8-bit grayscale."""
    if frame is None:
        raise ValueError("No camera frame available for histogram measurement")
    image = np.asarray(frame)
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.uint8, copy=False)


def measure_grayscale_histogram(frame, split: int = TARGET_SPLIT) -> dict:
    """Return grayscale histogram stats for a captured photo."""
    gray = frame_to_gray(frame).reshape(-1)
    if gray.size == 0:
        raise ValueError("Captured frame has no pixels")
    split = int(split)
    frac_below = float(np.mean(gray < split))
    frac_above = float(np.mean(gray > split))
    return {
        "split": split,
        "frac_below": frac_below,
        "frac_above": frac_above,
        "median": float(np.median(gray)),
        "mean": float(np.mean(gray)),
    }


def histogram_is_balanced(stats: dict) -> bool:
    """True when ~50% of pixels are below 125 and ~50% are above."""
    median_ok = abs(float(stats["median"]) - TARGET_SPLIT) <= MEDIAN_TOLERANCE
    frac_ok = abs(float(stats["frac_below"]) - TARGET_FRAC_BELOW) <= FRAC_TOLERANCE
    return median_ok or frac_ok


class AutoSolidIntensityController:
    """Binary-search projector intensity until the camera histogram is balanced."""

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
        self.lo = MIN_INTENSITY
        self.hi = MAX_INTENSITY
        self.step = 0

    def suggest_next_intensity(self, frame) -> tuple[int, dict, bool]:
        """Measure the current photo and return (next_intensity, stats, done)."""
        stats = measure_grayscale_histogram(frame)
        stats["intensity"] = self.intensity
        self.step += 1

        if histogram_is_balanced(stats) or self.step >= MAX_STEPS:
            stats["done_reason"] = "balanced" if histogram_is_balanced(stats) else "max_steps"
            return self.intensity, stats, True

        too_dark = float(stats["median"]) < TARGET_SPLIT
        if too_dark:
            self.lo = self.intensity + 1
        else:
            self.hi = self.intensity - 1

        if self.lo > self.hi:
            stats["done_reason"] = "search_exhausted"
            return self.intensity, stats, True

        nxt = clamp_intensity((self.lo + self.hi) / 2)
        if nxt == self.intensity:
            nxt = clamp_intensity(self.intensity + (1 if too_dark else -1))
        if nxt == self.intensity or nxt < self.lo or nxt > self.hi:
            stats["done_reason"] = "no_better_step"
            return self.intensity, stats, True

        self.intensity = nxt
        stats["next_intensity"] = self.intensity
        return self.intensity, stats, False

    def run(self, *, out_dir=None, settle_s: float = 0.5, warmup_frames: int = 10) -> tuple[int, dict]:
        """Set intensity, capture a screenshot, and search until the histogram is balanced."""
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
                f"median={stats['median']:.1f} below125={100.0 * stats['frac_below']:.1f}% "
                f"above125={100.0 * stats['frac_above']:.1f}% image={img_path}"
            )
            if done:
                self.set_intensity(self.intensity)
                self.log(f"[AutoSolid] settled at {self.intensity}% ({stats.get('done_reason', 'balanced')})")
                return self.intensity, stats

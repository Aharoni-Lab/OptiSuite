from __future__ import annotations

import numpy as np
import cv2
import time
from typing import TYPE_CHECKING

import autofocus as af

if TYPE_CHECKING:
    from camera_app_protocol import CameraAppHost






class CameraFocusScoringMixin:
    """Mixin for camera focus scoring."""
    #---------------------------------------------------------------------------------------------------------------------------------
    # Camera Focus Scoring Functions
    #---------------------------------------------------------------------------------------------------------------------------------

    def _center_crop_fraction(self: CameraAppHost, gray: np.ndarray, fraction: float) -> np.ndarray:
        """Return the centered crop used for focus scoring."""
        f = float(fraction)
        if f >= 1.0:
            return gray
        h, w = gray.shape[:2]
        ch = max(1, int(round(h * f)))
        cw = max(1, int(round(w * f)))
        y0 = (h - ch) // 2
        x0 = (w - cw) // 2
        return gray[y0 : y0 + ch, x0 : x0 + cw]

    def _downscale_max_size(self: CameraAppHost, gray: np.ndarray, max_size: int) -> np.ndarray:
        """Downscale an image so focus scoring stays fast."""
        m = int(max_size)
        if m <= 0:
            return gray
        h, w = gray.shape[:2]
        longest = max(h, w)
        if longest <= m:
            return gray
        scale = m / float(longest)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def compute_focus_score_from_frame(
        self: CameraAppHost, frame_bgr: np.ndarray, metric: af.MetricName = "laplacian_var", roi: float = 0.8, max_size: int = 1024
    ) -> float:
        """Compute a focus score from a BGR camera frame."""
        gray_u8 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = gray_u8.astype(np.float32) / 255.0
        gray = self._downscale_max_size(gray, max_size=max_size)
        gray = self._center_crop_fraction(gray, fraction=roi)
        return float(af.focus_score(gray, metric=metric))

    def score_current_frame(self: CameraAppHost) -> None:
        """Sample one camera repeatedly and log focus-score statistics."""
        cam_index = int(self.score_cam_select.currentIndex())
        if cam_index < 0 or cam_index >= self.cam_mgr.num_cameras:
            self.append_local_log("[Score] no camera available")
            return
        n = int(self.score_n.value())
        metric: af.MetricName = "laplacian_var"
        roi = 0.8
        max_size = 1024

        scores = []
        for i in range(n):
            frame = self.cam_mgr.get_frame(cam_index)
            if frame is None:
                self.append_local_log(f"[Score] cam={cam_index+1} no frame")
                return
            s = self.compute_focus_score_from_frame(frame, metric=metric, roi=roi, max_size=max_size)
            scores.append(s)
            time.sleep(0.02)

        arr = np.array(scores, dtype=np.float64)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0)) if len(arr) > 1 else 0.0
        self.append_local_log(
            f"[Score] cam={cam_index+1} metric={metric} (higher=sharper) n={n} mean={mean:.6g} std={std:.6g} min={arr.min():.6g} max={arr.max():.6g}"
        )

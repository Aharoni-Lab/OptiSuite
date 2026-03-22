from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

#from autofocus.py file
import autofocus as af


# @ means the variable is a class variable
@dataclass(frozen=True)
class AutofocusPoint:
    z_cmd: float
    z_meas: float
    image_path: str
    score: float


class AutofocusRoutine:
    """
    Coarse-to-fine autofocus that:
    - moves the stage in Z to candidate positions
    - captures a screenshot
    - computes a focus score
    - returns to the best Z
    """

    def __init__(
        self,
        *,
        cam_index: int,
        get_position_xyz: Callable[[], tuple[float, float, float]],
        move_to_xyz_and_wait: Callable[[float, float, float, float], None],
        take_screenshot: Callable[[int, str, str], Optional[str]],
        log: Callable[[str], None],
        base_dir: str,
        metric: af.MetricName = "laplacian_var",
        roi: float = 0.8,
        max_size: int = 1024,
        cancel_event: Optional[threading.Event] = None,
    ):
        self.cam_index = int(cam_index)
        self.get_position_xyz = get_position_xyz
        self.move_to_xyz_and_wait = move_to_xyz_and_wait
        self.take_screenshot = take_screenshot
        self.log = log

        self.metric = metric
        self.roi = float(roi)
        self.max_size = int(max_size)
        self.cancel_event = cancel_event or threading.Event()

        self.run_id = uuid.uuid4().hex[:10]
        self.base_dir = str(base_dir)

    def _is_cancelled(self) -> bool:
        return bool(self.cancel_event.is_set())

    def _mk_run_dirs(self) -> tuple[str, str]:
        today = time.strftime("%Y%m%d")
        cam_label = f"cam{self.cam_index + 1}"
        root = (
            Path(self.base_dir)
            / "autofocus"
            / f"run_{self.run_id}_{today}"
            / cam_label
        )
        root.mkdir(parents=True, exist_ok=True)
        results_path = root / "results.jsonl"
        return str(root), str(results_path)

    def _candidate_grid(self, center: float, span: float, step: float) -> list[float]:
        if step <= 0:
            raise ValueError("step must be > 0")
        n = int(math.ceil(span / step))
        zs = [center + k * step for k in range(-n, n + 1)]
        # unique + stable order
        out = []
        seen = set()
        for z in zs:
            z2 = round(float(z), 6)
            if z2 not in seen:
                seen.add(z2)
                out.append(z2)
        return out

    def run(
        self,
        *,
        #total images taken is given by n
        
        rounds: Iterable[tuple[float, float]] = ((3.0, 0.5), (0.6, 0.2)),
        move_timeout_s: float = 30.0,
        settle_s: float = 0.15,
        warmup_frames: int = 3,
    ) -> tuple[float, list[AutofocusPoint]]:
        x0, y0, z0 = self.get_position_xyz()
        self.log(f"[AF] run={self.run_id}")
        self.log(f"[AF] start XYZ=({x0:.3f}, {y0:.3f}, {z0:.3f}) cam={self.cam_index + 1}")

        out_dir, results_path = self._mk_run_dirs()
        best_z = float(z0)
        best_score = -1.0
        all_points: list[AutofocusPoint] = []
        round_summaries = []

        for span, step in rounds:
            if self._is_cancelled():
                self.log("[AF] cancelled")
                break

            zs = self._candidate_grid(best_z, float(span), float(step))
            self.log(f"[AF] sweep span={span} step={step} n={len(zs)} around z={best_z:.3f}")

            round_best_z = best_z
            round_best_score = float("-inf")
            round_best_img = None

            for z in zs:
                if self._is_cancelled():
                    self.log("[AF] cancelled")
                    break

                self.move_to_xyz_and_wait(x0, y0, float(z), move_timeout_s)
                if settle_s > 0:
                    time.sleep(float(settle_s))
                # Record actual stage Z for association/debug
                _x1, _y1, z_meas = self.get_position_xyz()

                # Keep filenames short; cam/model are encoded by the folder name.
                img_tag = time.strftime("%H%M%S")
                prefix = f"af_Z{float(z_meas):.3f}_{img_tag}"
                img_path = self.take_screenshot(self.cam_index, out_dir, prefix, warmup_frames)
                if not img_path:
                    self.log(f"[AF] no image at cmdZ={z:.3f} measZ={z_meas:.3f}")
                    continue

                r = af.score_image(Path(img_path), metric=self.metric, roi=self.roi, max_size=self.max_size)
                pt = AutofocusPoint(z_cmd=float(z), z_meas=float(z_meas), image_path=str(r.path), score=float(r.score))
                all_points.append(pt)

                with open(results_path, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {"z_cmd": pt.z_cmd, "z_meas": pt.z_meas, "path": pt.image_path, "score": pt.score}
                        )
                        + "\n"
                    )

                self.log(f"[AF] cmdZ={pt.z_cmd:.3f} measZ={pt.z_meas:.3f} score={pt.score:.6g} image={img_tag}")

                if pt.score >= round_best_score:
                    round_best_score = pt.score
                    round_best_z = pt.z_meas
                    round_best_img = os.path.basename(pt.image_path)

            best_z = round_best_z
            best_score = round_best_score
            summary = {"span": float(span), "step": float(step), "best_z": float(best_z), "best_score": float(best_score), "best_img": round_best_img}
            round_summaries.append(summary)
            with open(Path(out_dir) / "summary.json", "w", encoding="utf-8") as f:
                json.dump({"rounds": round_summaries, "best_z": float(best_z), "best_score": float(best_score)}, f, indent=2)
            self.log(f"[AF] best round z={best_z:.3f} score={best_score:.6g} img={round_best_img}")

            # score the best image with the usaf target and return the smallest group/element that image resolves
            [group, element] = af.find_usaf_score(Path(round_best_img))

        if not self._is_cancelled():
            self.log(f"[AF] returning to best z={best_z:.3f}")
            self.move_to_xyz_and_wait(x0, y0, float(best_z), move_timeout_s)

        return best_z, all_points


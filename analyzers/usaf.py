from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

import usaf_algo
import yolo_model
from analyzers.base import ResolutionAnalyzer
from core.results import AnalyzerConfig, AnalyzerResult, ContrastSample, OverlayItem, ThresholdReading


@dataclass(slots=True)
class USAFAnalyzerConfig(AnalyzerConfig):
    chart_type: str = "usaf"
    show_preview: bool = False
    debug_mode: bool = False
    use_detection_fallback: bool = True
    allow_model_assist: bool = False
    flip_mode: str = "auto"
    flipped_target: bool = True
    auto_adjust: bool = True
    model_path: str = str(usaf_algo.MODEL_PATH)
    imgsz: int = 2048


def usaf_lp_per_mm(group: int, element: int) -> float:
    return float(2 ** (group + (element - 1) / 6.0))


def usaf_resolution_mm(group: int, element: int) -> float:
    return float(1.0 / (2.0 * usaf_lp_per_mm(group, element)))


@contextlib.contextmanager
def _legacy_config_scope(config: USAFAnalyzerConfig) -> Iterator[None]:
    original = {
        "DEBUG_MODE": usaf_algo.DEBUG_MODE,
        "PREVIEW_MODE": usaf_algo.PREVIEW_MODE,
        "YOLO_DETECT": usaf_algo.YOLO_DETECT,
        "FLIPED_TARGET": usaf_algo.FLIPED_TARGET,
        "AUTO_ADJUST": usaf_algo.AUTO_ADJUST,
    }
    usaf_algo.DEBUG_MODE = config.debug_mode
    usaf_algo.PREVIEW_MODE = config.show_preview
    usaf_algo.YOLO_DETECT = config.allow_model_assist
    usaf_algo.FLIPED_TARGET = config.flipped_target
    usaf_algo.AUTO_ADJUST = config.auto_adjust
    try:
        yield
    finally:
        for key, value in original.items():
            setattr(usaf_algo, key, value)


def _calculate_scores_and_scanlines(context, yolo_detections=None):
    gray = context.gray_image
    normalized_gray = context.normalized_gray

    usaf_algo.find_square_corners(gray.copy())
    if not usaf_algo.valid_squares:
        raise RuntimeError("Could not detect a valid USAF square.")

    retry_count = 0
    retry_origin = False
    raw_scores: dict[int, float] = {}
    raw_scanlines: dict[int, dict] = {}

    while retry_count < len(usaf_algo.valid_squares):
        raw_scores = {}
        raw_scanlines = {}
        retry_condition = False

        corners = usaf_algo.valid_squares[retry_count].reshape(-1, 2).copy()
        corners[:, 1] = gray.shape[0] - corners[:, 1] - 1
        output_list = usaf_algo.coordinate_calibration(gray, corners)
        if output_list is None:
            retry_count += 1
            continue

        center_x, center_y, angle, side_length, _right_ref_corner, _left_ref_corner = output_list
        if retry_count == 1 and not retry_origin and usaf_algo.RETRY_OUTER:
            flip = -1 if usaf_algo.FLIPED_TARGET else 1
            center_offset = np.array([-1.009, 7.791]) * side_length
            center_offset = usaf_algo.get_rotated_pt(0, 0, center_offset[0] * flip, -center_offset[1], angle)
            center_x = center_x + center_offset[0]
            center_y = center_y + center_offset[1]
            side_length = side_length * 3.918
            retry_origin = True
        else:
            retry_origin = False

        for i in range(0, len(usaf_algo.group_positions), 2):
            raw_a = usaf_algo.group_positions[i]
            raw_b = usaf_algo.group_positions[i + 1]
            scale = side_length
            loc_a = (raw_a[0] * scale, raw_a[1] * scale)
            loc_b = (raw_b[0] * scale, raw_b[1] * scale)

            flip = -1 if usaf_algo.FLIPED_TARGET else 1
            pt_a = usaf_algo.get_rotated_pt(center_x, center_y, flip * loc_a[0], -loc_a[1], angle)
            pt_b = usaf_algo.get_rotated_pt(center_x, center_y, flip * loc_b[0], -loc_b[1], angle)
            plot_pt_a = [int(pt_a[0]), int(pt_a[1])]
            plot_pt_b = [int(pt_b[0]), int(pt_b[1])]

            if (
                (pt_a[0] < 0 or pt_a[0] >= gray.shape[1] or pt_a[1] < 0 or pt_a[1] >= gray.shape[0] or
                 pt_b[0] < 0 or pt_b[0] >= gray.shape[1] or pt_b[1] < 0 or pt_b[1] >= gray.shape[0])
                and usaf_algo.RETRY_OFF_IMAGE
            ):
                retry_condition = True
                break

            pt_a, pt_b = usaf_algo.apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
            yolo_repl = False
            if yolo_detections:
                repl_a, repl_b = usaf_algo.find_replacement_keypoints(pt_a, pt_b, yolo_detections)
                if repl_a is not None:
                    pt_a, pt_b = usaf_algo.apply_point_adjustment_algorithm(repl_a, repl_b, normalized_gray)
                    yolo_repl = True

            mask = np.zeros_like(gray, dtype=np.uint8)
            cv2.line(mask, pt_a, pt_b, 255, 4)
            line_pixels = normalized_gray[mask > 0]
            if len(line_pixels) > 0:
                brightest = np.max(line_pixels)
                darkest = np.min(line_pixels)
                diff = float(brightest - darkest)
                score = -diff if yolo_repl else diff
            else:
                score = 0.0

            raw_index = i // 2
            raw_scores[raw_index] = score
            raw_scanlines[raw_index] = {
                "pt_a": [int(pt_a[0]), int(pt_a[1])],
                "pt_b": [int(pt_b[0]), int(pt_b[1])],
                "plot_pt_a": plot_pt_a,
                "plot_pt_b": plot_pt_b,
                "score": float(score),
                "used_yolo": yolo_repl,
            }

        if not retry_condition:
            break
        if not retry_origin:
            retry_count += 1

    if retry_count == len(usaf_algo.valid_squares) or not raw_scores:
        raise RuntimeError("Failed to find valid square for coordinate calibration.")

    final_scores: list[float] = []
    scanline_map: dict[str, dict] = {}
    half_count = len(raw_scores) // 2
    for index in range(half_count):
        vert_score = abs(raw_scores[index])
        horiz_score = abs(raw_scores[index + half_count])
        vert_sign = 1 if raw_scores[index] >= 0 else -1
        horiz_sign = 1 if raw_scores[index + half_count] >= 0 else -1
        net_sign = -1 if vert_sign == -1 or horiz_sign == -1 else 1
        if usaf_algo.SCORE_METHOD == "mean":
            combined_score = (vert_score + horiz_score) / 2.0
        elif usaf_algo.SCORE_METHOD == "max":
            combined_score = max(vert_score, horiz_score)
        elif usaf_algo.SCORE_METHOD == "min":
            combined_score = min(vert_score, horiz_score)
        else:
            combined_score = vert_score
        combined_score *= net_sign
        final_scores.append(float(combined_score))

        group, element = usaf_algo.score_table[index]
        scanline_map[f"{group}:{element}"] = {
            "group": group,
            "element": element,
            "vertical": raw_scanlines[index],
            "horizontal": raw_scanlines[index + half_count],
            "score": float(combined_score),
            "lp_per_mm": usaf_lp_per_mm(group, element),
            "resolution_mm": usaf_resolution_mm(group, element),
        }

    return final_scores, scanline_map


def _candidate_quality(scores: list[float], threshold: float) -> float:
    if not scores:
        return float("-inf")

    abs_scores = [abs(score) for score in scores]
    passed_count = sum(score >= threshold for score in abs_scores)
    total_passed_signal = sum(min(score, threshold * 2.0) for score in abs_scores if score >= threshold)

    violations = 0
    violation_penalty = 0.0
    for index in range(1, len(abs_scores)):
        allowed_next = abs_scores[index - 1] * 1.08
        if abs_scores[index] > allowed_next:
            violations += 1
            violation_penalty += abs_scores[index] - allowed_next

    return (
        passed_count * 5.0
        + total_passed_signal
        - violations * 6.0
        - violation_penalty * 25.0
    )


def _flip_mode_to_candidates(flip_mode: str) -> list[tuple[str, bool]]:
    if flip_mode == "flipped":
        return [("flipped", True)]
    if flip_mode == "not_flipped":
        return [("not_flipped", False)]
    return [("flipped", True), ("not_flipped", False)]


def _select_best_focus_group(scores: list[float], threshold: float):
    chosen_index = None
    for index, score in enumerate(scores):
        if abs(score) >= threshold:
            chosen_index = index

    if chosen_index is None:
        return None, None

    return usaf_algo.score_table[min(chosen_index, len(usaf_algo.score_table) - 1)], chosen_index


class USAFAnalyzer(ResolutionAnalyzer):
    chart_type = "usaf"
    display_name = "USAF 1951"

    def __init__(self, config: USAFAnalyzerConfig | None = None):
        super().__init__(config or USAFAnalyzerConfig())
        self.config: USAFAnalyzerConfig

    def probe(self, context) -> float:
        candidates = _flip_mode_to_candidates(self.config.flip_mode)
        best_probe = 0.1
        for _label, flipped_target in candidates:
            probe_config = replace(self.config, flipped_target=flipped_target)
            try:
                with _legacy_config_scope(probe_config):
                    corners = usaf_algo.find_square_corners(context.gray_image.copy())
                    if corners is not None:
                        calibration = usaf_algo.coordinate_calibration(context.gray_image.copy(), corners)
                        if calibration is not None:
                            best_probe = max(best_probe, 0.96)
                        else:
                            best_probe = max(best_probe, 0.35)
            except Exception:
                continue
        if self.config.flip_mode == "auto" and best_probe >= 0.35:
            best_probe += 0.01
        return best_probe

    def analyze(self, context) -> AnalyzerResult:
        warnings: list[str] = []
        threshold = self.config.contrast_threshold
        detections = None
        if self.config.allow_model_assist:
            model_path = Path(self.config.model_path)
            if model_path.exists():
                detections, _result, _img = yolo_model.extract_yolo_detections(
                    context.image_path,
                    model_path,
                    imgsz=self.config.imgsz,
                )
            else:
                warnings.append(f"Model file not found: {model_path}")

        candidate_results: list[dict] = []
        last_exception: Exception | None = None

        for flip_label, flipped_target in _flip_mode_to_candidates(self.config.flip_mode):
            candidate_config = replace(self.config, flipped_target=flipped_target)
            try:
                with _legacy_config_scope(candidate_config):
                    scores, scanline_map = _calculate_scores_and_scanlines(context, detections)
                    if not scores:
                        raise RuntimeError("USAF score calculation did not return any scores.")
                    best_focus_group, chosen_index = _select_best_focus_group(list(scores), threshold)
                    if best_focus_group is None:
                        raise RuntimeError(
                            f"No USAF group/element met the configured contrast threshold of {threshold:.0%}."
                        )

                    overlay_items: list[OverlayItem] = []
                    corners = usaf_algo.find_square_corners(context.gray_image.copy())
                    if corners is not None:
                        screen_points = [(int(x), int(context.gray_image.shape[0] - y - 1)) for x, y in corners]
                        overlay_items.append(OverlayItem(kind="polygon", points=screen_points, color=(0, 255, 255), thickness=2))

                candidate_results.append(
                    {
                        "flip_label": flip_label,
                        "flipped_target": flipped_target,
                        "scores": scores,
                        "scanline_map": scanline_map,
                        "best_focus_group": best_focus_group,
                        "chosen_index": chosen_index,
                        "overlay_items": overlay_items,
                        "quality": _candidate_quality(list(scores), threshold),
                    }
                )
            except Exception as exc:
                last_exception = exc

        if not candidate_results:
            reading = ThresholdReading(
                label="USAF threshold",
                value="unresolved",
                numeric_value=None,
                unit="group-element",
                threshold=threshold,
                passed=False,
            )
            return AnalyzerResult(
                analyzer_id="usaf",
                chart_type="usaf",
                image_path=context.image_path,
                success=False,
                reading=reading,
                summary="USAF analysis failed.",
                warnings=warnings,
                overlay_items=[],
                error=str(last_exception) if last_exception is not None else "USAF analysis failed.",
                confidence=0.0,
            )

        candidate_results.sort(key=lambda item: item["quality"], reverse=True)
        chosen = candidate_results[0]
        scores = chosen["scores"]
        scanline_map = chosen["scanline_map"]
        best_focus_group = chosen["best_focus_group"]
        chosen_index = chosen["chosen_index"]
        overlay_items = chosen["overlay_items"]

        if self.config.flip_mode == "auto":
            warnings.append(f"Auto flip detection selected: {chosen['flip_label']}")
        else:
            warnings.append(f"Using user-specified flip mode: {chosen['flip_label']}")

        curve: list[ContrastSample] = []
        resolved_label = f"G{best_focus_group[0]} E{best_focus_group[1]}"
        resolved_frequency = usaf_lp_per_mm(best_focus_group[0], best_focus_group[1])
        resolved_resolution_mm = usaf_resolution_mm(best_focus_group[0], best_focus_group[1])

        for index in range(len(scores)):
            group, element = usaf_algo.score_table[index]
            frequency = usaf_lp_per_mm(group, element)
            contrast = float(abs(scores[index]))
            passed = contrast >= threshold
            curve.append(
                ContrastSample(
                    index=index,
                    label=f"G{group} E{element}",
                    frequency=frequency,
                    contrast=contrast,
                    threshold_passed=passed,
                    metadata={"group": group, "element": element},
                )
            )

        reading = ThresholdReading(
            label="Highest resolvable USAF element",
            value=resolved_label,
            numeric_value=resolved_frequency,
            unit="lp/mm",
            threshold=threshold,
            passed=True,
            details={
                "group": best_focus_group[0],
                "element": best_focus_group[1],
                "chosen_index": chosen_index,
                "resolution_lp_mm": resolved_frequency,
                "resolution_mm": resolved_resolution_mm,
                "flipped_target": bool(chosen["flipped_target"]),
                "flip_mode": self.config.flip_mode,
            },
        )

        return AnalyzerResult(
            analyzer_id="usaf",
            chart_type="usaf",
            image_path=context.image_path,
            success=True,
            reading=reading,
            summary=f"Resolved {resolved_label} above {threshold:.0%} contrast.",
            confidence=0.95 if resolved_frequency is not None else 0.75,
            warnings=warnings,
            metrics={
                "group": best_focus_group[0],
                "element": best_focus_group[1],
                "resolved_frequency_lp_mm": resolved_frequency,
                "resolved_resolution_mm": resolved_resolution_mm,
                "score_count": len(scores),
                "chosen_index": chosen_index,
                "flipped_target": bool(chosen["flipped_target"]),
                "flip_quality": float(chosen["quality"]),
            },
            contrast_curve=curve,
            overlay_items=overlay_items,
            metadata={
                "legacy_scores": [float(value) for value in scores],
                "scanlines": scanline_map,
                "formula_source": "USAF 1951 / Thorlabs line-pairs formula",
                "flip_candidates": [
                    {
                        "flip_label": item["flip_label"],
                        "flipped_target": bool(item["flipped_target"]),
                        "quality": float(item["quality"]),
                        "best_group": int(item["best_focus_group"][0]),
                        "best_element": int(item["best_focus_group"][1]),
                        "chosen_index": int(item["chosen_index"]),
                    }
                    for item in candidate_results
                ],
                "selected_flip": chosen["flip_label"],
            },
        )


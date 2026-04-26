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
    image_path = context.image_path
    final_scores, scanline_map = usaf_algo.calculate_focus_scores(image_path, yolo_detections)
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





        # Add all scanline items to overlay_items for display
        #--------------------------------------------------------------------------------------------
        for key, scanline_data in scanline_map.items():
            group = scanline_data["group"]
            element = scanline_data["element"]
            score = scanline_data["score"]

            # Add vertical scanline
            if "pt_a" in scanline_data["vertical"] and "pt_b" in scanline_data["vertical"]:
                pt_a = scanline_data["vertical"]["pt_a"]
                pt_b = scanline_data["vertical"]["pt_b"]
                # Convert to screen coordinates (flip Y axis)
                height = context.gray_image.shape[0]
                screen_pt_a = pt_a  # (pt_a[0], height - pt_a[1] - 1)
                screen_pt_b = pt_b  #(pt_b[0], height - pt_b[1] - 1)
                # Color based on whether this is the resolved element
                color = (0, 255, 0) if group == best_focus_group[0] and element == best_focus_group[1] else (255, 0, 0)
                overlay_items.append(OverlayItem(
                    kind="line",
                    points=[screen_pt_a, screen_pt_b],
                    color=color,
                    thickness=3,
                    text=f"G{group}E{element}V"
                ))
            
            # Add horizontal scanline
            if "pt_a" in scanline_data["horizontal"] and "pt_b" in scanline_data["horizontal"]:
                pt_a = scanline_data["horizontal"]["pt_a"]
                pt_b = scanline_data["horizontal"]["pt_b"]
                # Convert to screen coordinates (flip Y axis)
                height = context.gray_image.shape[0]
                screen_pt_a = pt_a  # (pt_a[0], height - pt_a[1] - 1)
                screen_pt_b = pt_b  #(pt_b[0], height - pt_b[1] - 1)
                # Color based on whether this is the resolved element
                color = (0, 255, 0) if group == best_focus_group[0] and element == best_focus_group[1] else (255, 0, 0)
                overlay_items.append(OverlayItem(
                    kind="line",
                    points=[screen_pt_a, screen_pt_b],
                    color=color,
                    thickness=3,
                    text=f"G{group}E{element}H"
                ))
        #--------------------------------------------------------------------------------------------





        if self.config.flip_mode == "auto":
            warnings.append(f"Auto flip detection selected: {chosen['flip_label']}")
        else:
            warnings.append(f"Using user-specified flip mode: {chosen['flip_label']}")

        curve: list[ContrastSample] = []
        resolved_label = f"G{best_focus_group[0]} E{best_focus_group[1]}"
        resolved_frequency = usaf_algo.usaf_lp_per_mm(best_focus_group[0], best_focus_group[1])
        resolved_resolution_mm = usaf_algo.usaf_resolution_mm(best_focus_group[0], best_focus_group[1])

        # calculate contrast and frequency for all elements and store it in a list "curve"
        for index in range(len(scores)):
            group, element = usaf_algo.score_table[index]
            frequency = usaf_algo.usaf_lp_per_mm(group, element)
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

        # detail for the best resolved element
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
                # list all possible flip candidates 
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


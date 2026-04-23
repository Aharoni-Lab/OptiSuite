from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from analyzers.base import ResolutionAnalyzer
from core.contrast import mtf_from_edge_samples
from core.registration import detect_long_lines, line_to_overlay
from core.results import AnalyzerConfig, AnalyzerResult, ContrastSample, ThresholdReading


@dataclass(slots=True)
class SlantedEdgeAnalyzerConfig(AnalyzerConfig):
    chart_type: str = "slanted_edge"
    strip_half_width: int = 30


class SlantedEdgeAnalyzer(ResolutionAnalyzer):
    chart_type = "slanted_edge"
    display_name = "Slanted Edge"

    def __init__(self, config: SlantedEdgeAnalyzerConfig | None = None):
        super().__init__(config or SlantedEdgeAnalyzerConfig())
        self.config: SlantedEdgeAnalyzerConfig

    def probe(self, context) -> float:
        lines = detect_long_lines(context.gray_image)
        if not lines:
            return 0.15
        longest = max(lines, key=lambda line: np.hypot(line[2] - line[0], line[3] - line[1]))
        angle = abs(float(np.degrees(np.arctan2(longest[3] - longest[1], longest[2] - longest[0]))))
        if 10.0 <= angle <= 80.0 or 100.0 <= angle <= 170.0:
            return 0.9
        return 0.45

    def analyze(self, context) -> AnalyzerResult:
        threshold = self.config.contrast_threshold
        lines = detect_long_lines(context.gray_image)
        if not lines:
            reading = ThresholdReading(
                label="MTF20 crossing",
                value="unresolved",
                numeric_value=None,
                unit="cycles/pixel",
                threshold=threshold,
                passed=False,
            )
            return AnalyzerResult(
                analyzer_id="slanted_edge",
                chart_type="slanted_edge",
                image_path=context.image_path,
                success=False,
                reading=reading,
                summary="No dominant edge detected.",
                confidence=0.0,
                error="No dominant edge detected.",
            )

        line = max(lines, key=lambda candidate: np.hypot(candidate[2] - candidate[0], candidate[3] - candidate[1]))
        x1, y1, x2, y2 = line
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        center = (context.gray_image.shape[1] / 2.0, context.gray_image.shape[0] / 2.0)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            context.normalized_gray,
            rotation_matrix,
            (context.gray_image.shape[1], context.gray_image.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )

        points = np.array([[x1, y1], [x2, y2]], dtype=np.float32)
        transformed = cv2.transform(points.reshape(1, -1, 2), rotation_matrix).reshape(-1, 2)
        x_coords = transformed[:, 0]
        y_coords = transformed[:, 1]
        center_x = int(np.mean(x_coords))
        center_y = int(np.mean(y_coords))
        half_width = self.config.strip_half_width
        x_min = max(0, center_x - half_width)
        x_max = min(rotated.shape[1], center_x + half_width)
        y_min = max(0, int(np.min(y_coords)) - half_width)
        y_max = min(rotated.shape[0], int(np.max(y_coords)) + half_width)

        strip = rotated[y_min:y_max, x_min:x_max]
        if strip.size == 0:
            reading = ThresholdReading(
                label="MTF20 crossing",
                value="unresolved",
                numeric_value=None,
                unit="cycles/pixel",
                threshold=threshold,
                passed=False,
            )
            return AnalyzerResult(
                analyzer_id="slanted_edge",
                chart_type="slanted_edge",
                image_path=context.image_path,
                success=False,
                reading=reading,
                summary="Could not extract a valid slanted-edge strip.",
                confidence=0.0,
                error="Invalid strip around slanted edge.",
            )

        esf = strip.mean(axis=0)
        frequencies, mtf = mtf_from_edge_samples(esf)
        curve = []
        resolved_frequency = None
        for index, (frequency, contrast) in enumerate(zip(frequencies.tolist(), mtf.tolist())):
            if index == 0:
                continue
            passed = contrast >= threshold
            curve.append(
                ContrastSample(
                    index=index,
                    label=f"f{index}",
                    frequency=float(frequency),
                    contrast=float(contrast),
                    threshold_passed=passed,
                )
            )
            if passed:
                resolved_frequency = float(frequency)

        reading = ThresholdReading(
            label="MTF20 crossing",
            value=f"{resolved_frequency:.4f}" if resolved_frequency is not None else "unresolved",
            numeric_value=resolved_frequency,
            unit="cycles/pixel",
            threshold=threshold,
            passed=resolved_frequency is not None,
        )

        return AnalyzerResult(
            analyzer_id="slanted_edge",
            chart_type="slanted_edge",
            image_path=context.image_path,
            success=resolved_frequency is not None,
            reading=reading,
            summary=(
                f"Slanted-edge MTF20 reached {resolved_frequency:.4f} cycles/pixel."
                if resolved_frequency is not None
                else "MTF never stayed above the threshold."
            ),
            confidence=max(self.probe(context), 0.35),
            warnings=[],
            metrics={"edge_angle_deg": angle, "strip_shape": list(strip.shape)},
            contrast_curve=curve,
            overlay_items=[line_to_overlay(line, color=(255, 255, 0))],
            error=None if resolved_frequency is not None else "MTF curve did not cross the threshold.",
        )


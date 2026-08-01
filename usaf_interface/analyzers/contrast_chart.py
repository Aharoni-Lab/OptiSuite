from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from analyzers.base import ResolutionAnalyzer
from core.contrast import michelson_contrast
from core.registration import approximate_patch_rectangles
from core.results import AnalyzerConfig, AnalyzerResult, ContrastSample, OverlayItem, ThresholdReading


@dataclass(slots=True)
class ContrastChartAnalyzerConfig(AnalyzerConfig):
    chart_type: str = "contrast"


class ContrastChartAnalyzer(ResolutionAnalyzer):
    chart_type = "contrast"
    display_name = "Contrast Pattern"

    def __init__(self, config: ContrastChartAnalyzerConfig | None = None):
        super().__init__(config or ContrastChartAnalyzerConfig())
        self.config: ContrastChartAnalyzerConfig

    def probe(self, context) -> float:
        rectangles = approximate_patch_rectangles(context.gray_image)
        if len(rectangles) >= 6:
            return 0.96
        if len(rectangles) >= 4:
            return 0.85
        if len(rectangles) >= 2:
            return 0.55
        reduced = cv2.resize(context.gray_image, (4, 4), interpolation=cv2.INTER_AREA)
        if float(reduced.max() - reduced.min()) > 50:
            return 0.45
        return 0.2

    def analyze(self, context) -> AnalyzerResult:
        threshold = self.config.contrast_threshold
        rectangles = approximate_patch_rectangles(context.gray_image)
        if len(rectangles) < 2:
            grid_h, grid_w = 4, 4
            patch_h = context.gray_image.shape[0] // grid_h
            patch_w = context.gray_image.shape[1] // grid_w
            rectangles = []
            for row in range(grid_h):
                for col in range(grid_w):
                    x1 = col * patch_w
                    y1 = row * patch_h
                    x2 = x1 + patch_w
                    y2 = y1 + patch_h
                    rectangles.append((x1, y1, x2, y2))

        rectangles = sorted(rectangles, key=lambda rect: (rect[1], rect[0]))
        intensities: list[float] = []
        overlays: list[OverlayItem] = []
        for rect in rectangles:
            x1, y1, x2, y2 = rect
            roi = context.normalized_gray[y1:y2, x1:x2]
            intensity = float(np.mean(roi)) if roi.size else 0.0
            intensities.append(intensity)
            overlays.append(
                OverlayItem(kind="rect", points=[(x1, y1), (x2, y2)], color=(0, 255, 255), thickness=2)
            )

        samples: list[ContrastSample] = []
        resolved_pair = None
        resolved_contrast = None
        for index in range(len(rectangles) - 1):
            contrast = michelson_contrast(max(intensities[index], intensities[index + 1]), min(intensities[index], intensities[index + 1]))
            passed = contrast >= threshold
            samples.append(
                ContrastSample(
                    index=index,
                    label=f"patch pair {index + 1}",
                    frequency=float(index + 1),
                    contrast=float(contrast),
                    threshold_passed=passed,
                )
            )
            if passed:
                resolved_pair = index + 1
                resolved_contrast = float(contrast)

        reading = ThresholdReading(
            label="Highest contrast patch pair above threshold",
            value=str(resolved_pair) if resolved_pair is not None else "unresolved",
            numeric_value=float(resolved_pair) if resolved_pair is not None else None,
            unit="pair index",
            threshold=threshold,
            passed=resolved_pair is not None,
            details={"contrast": resolved_contrast},
        )

        return AnalyzerResult(
            analyzer_id="contrast",
            chart_type="contrast",
            image_path=context.image_path,
            success=resolved_pair is not None,
            reading=reading,
            summary=(
                f"Contrast pattern remained above threshold through pair {resolved_pair}."
                if resolved_pair is not None
                else "No adjacent patch pair stayed above the threshold."
            ),
            confidence=max(self.probe(context), 0.3),
            warnings=[],
            metrics={"patch_count": len(rectangles)},
            contrast_curve=samples,
            overlay_items=overlays,
            error=None if resolved_pair is not None else "No contrast patch pair passed the threshold.",
        )


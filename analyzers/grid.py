from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analyzers.base import ResolutionAnalyzer
from core.contrast import dominant_frequency_1d, percentile_contrast
from core.registration import detect_long_lines, grid_frequency_signature, line_to_overlay
from core.results import AnalyzerConfig, AnalyzerResult, ContrastSample, OverlayItem, ThresholdReading


@dataclass(slots=True)
class GridAnalyzerConfig(AnalyzerConfig):
    chart_type: str = "grid"


class GridAnalyzer(ResolutionAnalyzer):
    chart_type = "grid"
    display_name = "Grid / Grating"

    def __init__(self, config: GridAnalyzerConfig | None = None):
        super().__init__(config or GridAnalyzerConfig())
        self.config: GridAnalyzerConfig

    def probe(self, context) -> float:
        lines = detect_long_lines(context.gray_image)
        horizontal = 0
        vertical = 0
        oblique = 0
        for x1, y1, x2, y2 in lines:
            angle = abs(float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))) % 180.0
            if angle < 15.0 or angle > 165.0:
                horizontal += 1
            elif 75.0 < angle < 105.0:
                vertical += 1
            else:
                oblique += 1

        if horizontal >= 2 and vertical >= 2 and oblique <= horizontal + vertical:
            return 0.95

        row_score, col_score = grid_frequency_signature(context.gray_image)
        max_score = max(row_score, col_score, 1.0)
        min_score = min(row_score, col_score)
        if min_score <= 0:
            return 0.15
        return min(0.95, 0.35 + 0.6 * min_score / max_score)

    def analyze(self, context) -> AnalyzerResult:
        threshold = self.config.contrast_threshold
        normalized = context.normalized_gray
        row_profile = normalized.mean(axis=1)
        col_profile = normalized.mean(axis=0)

        row_frequency, _row_amplitude = dominant_frequency_1d(row_profile)
        col_frequency, _col_amplitude = dominant_frequency_1d(col_profile)
        row_contrast = percentile_contrast(row_profile)
        col_contrast = percentile_contrast(col_profile)

        samples: list[ContrastSample] = []
        frequencies = []
        if row_frequency is not None:
            frequencies.append(row_frequency)
            samples.append(
                ContrastSample(
                    index=0,
                    label="horizontal repetition",
                    frequency=float(row_frequency),
                    contrast=float(row_contrast),
                    threshold_passed=row_contrast >= threshold,
                )
            )
        if col_frequency is not None:
            frequencies.append(col_frequency)
            samples.append(
                ContrastSample(
                    index=1,
                    label="vertical repetition",
                    frequency=float(col_frequency),
                    contrast=float(col_contrast),
                    threshold_passed=col_contrast >= threshold,
                )
            )

        overlay_items: list[OverlayItem] = []
        for line in detect_long_lines(context.gray_image)[:8]:
            overlay_items.append(line_to_overlay(line))

        passed_frequencies = [
            sample.frequency
            for sample in samples
            if sample.frequency is not None and sample.threshold_passed
        ]
        resolved_frequency = max(passed_frequencies) if passed_frequencies else None

        reading = ThresholdReading(
            label="Highest grid repetition frequency above threshold",
            value=f"{resolved_frequency:.4f}" if resolved_frequency is not None else "unresolved",
            numeric_value=resolved_frequency,
            unit="cycles/pixel",
            threshold=threshold,
            passed=resolved_frequency is not None,
        )

        return AnalyzerResult(
            analyzer_id="grid",
            chart_type="grid",
            image_path=context.image_path,
            success=resolved_frequency is not None,
            reading=reading,
            summary=(
                f"Grid repetition resolved to {resolved_frequency:.4f} cycles/pixel."
                if resolved_frequency is not None
                else "Grid contrast never exceeded threshold."
            ),
            confidence=max(self.probe(context), 0.3),
            warnings=[],
            metrics={
                "row_contrast": float(row_contrast),
                "col_contrast": float(col_contrast),
                "row_frequency": row_frequency,
                "col_frequency": col_frequency,
            },
            contrast_curve=samples,
            overlay_items=overlay_items,
            error=None if resolved_frequency is not None else "No grid direction passed the contrast threshold.",
        )


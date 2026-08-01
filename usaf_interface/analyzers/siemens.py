from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import cv2

from analyzers.base import ResolutionAnalyzer
from core.contrast import dominant_frequency_1d, percentile_contrast, sample_along_circle
from core.registration import detect_circle
from core.results import AnalyzerConfig, AnalyzerResult, ContrastSample, OverlayItem, ThresholdReading


@dataclass(slots=True)
class SiemensAnalyzerConfig(AnalyzerConfig):
    chart_type: str = "siemens"
    min_radius_fraction: float = 0.15
    max_radius_fraction: float = 0.48
    radial_steps: int = 24


class SiemensAnalyzer(ResolutionAnalyzer):
    chart_type = "siemens"
    display_name = "Siemens Star"

    def __init__(self, config: SiemensAnalyzerConfig | None = None):
        super().__init__(config or SiemensAnalyzerConfig())
        self.config: SiemensAnalyzerConfig

    def probe(self, context) -> float:
        circle = detect_circle(context.gray_image)
        if circle is None:
            return 0.15

        center = (float(circle[0]), float(circle[1]))
        radius = float(circle[2]) * 0.7
        profile = sample_along_circle(context.normalized_gray, center, radius, sample_count=720)
        contrast = percentile_contrast(profile)
        dominant_frequency, _amplitude = dominant_frequency_1d(profile, sample_spacing=1.0)
        gx = cv2.Sobel(context.gray_image, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(context.gray_image, cv2.CV_32F, 0, 1, ksize=3)
        gradient_magnitude = cv2.magnitude(gx, gy)
        edge_profile = sample_along_circle(gradient_magnitude, center, float(circle[2]), sample_count=360)
        edge_support = float(np.percentile(edge_profile, 25))
        if dominant_frequency is None or contrast < 0.15 or edge_support < 100.0:
            return 0.3
        return 0.9

    def analyze(self, context) -> AnalyzerResult:
        threshold = self.config.contrast_threshold
        warnings: list[str] = []
        overlay_items: list[OverlayItem] = []

        circle = detect_circle(context.gray_image)
        if circle is None:
            center = (context.gray_image.shape[1] / 2.0, context.gray_image.shape[0] / 2.0)
            max_radius = min(context.gray_image.shape[:2]) * self.config.max_radius_fraction
            warnings.append("No clear Siemens circle found. Falling back to image center.")
        else:
            center = (float(circle[0]), float(circle[1]))
            max_radius = float(circle[2])
            overlay_items.append(
                OverlayItem(kind="circle", points=[(int(center[0]), int(center[1]))], radius=int(max_radius), color=(0, 255, 255), thickness=2)
            )

        min_radius = max(10.0, min(context.gray_image.shape[:2]) * self.config.min_radius_fraction)
        radii = np.linspace(min_radius, max_radius, self.config.radial_steps)
        samples: list[ContrastSample] = []
        resolved_frequency = None
        resolved_radius = None
        sample_count = 720

        for index, radius in enumerate(radii):
            profile = sample_along_circle(context.normalized_gray, center, float(radius), sample_count=sample_count)
            contrast = percentile_contrast(profile)
            dominant_frequency, _amplitude = dominant_frequency_1d(profile, sample_spacing=1.0)
            if dominant_frequency is None:
                continue

            circumference = max(1.0, 2.0 * np.pi * radius)
            cycles_per_pixel = float(dominant_frequency * sample_count / circumference)
            passed = contrast >= threshold
            samples.append(
                ContrastSample(
                    index=index,
                    label=f"radius {radius:.1f}px",
                    frequency=cycles_per_pixel,
                    contrast=float(contrast),
                    threshold_passed=passed,
                    metadata={"radius_px": float(radius)},
                )
            )
            if passed:
                resolved_frequency = cycles_per_pixel
                resolved_radius = float(radius)

        if resolved_radius is not None:
            overlay_items.append(
                OverlayItem(
                    kind="circle",
                    points=[(int(center[0]), int(center[1]))],
                    radius=int(resolved_radius),
                    color=(255, 0, 255),
                    thickness=2,
                )
            )

        success = bool(samples and resolved_frequency is not None)
        reading = ThresholdReading(
            label="Highest Siemens spatial frequency above threshold",
            value=f"{resolved_frequency:.4f}" if resolved_frequency is not None else "unresolved",
            numeric_value=resolved_frequency,
            unit="cycles/pixel",
            threshold=threshold,
            passed=resolved_frequency is not None,
            details={"radius_px": resolved_radius},
        )

        return AnalyzerResult(
            analyzer_id="siemens",
            chart_type="siemens",
            image_path=context.image_path,
            success=success,
            reading=reading,
            summary=(
                f"Resolved Siemens star contrast to {resolved_frequency:.4f} cycles/pixel."
                if resolved_frequency is not None
                else "Could not find a Siemens frequency above threshold."
            ),
            confidence=0.85 if circle is not None else 0.55,
            warnings=warnings,
            metrics={
                "center_x": center[0],
                "center_y": center[1],
                "resolved_radius_px": resolved_radius,
            },
            contrast_curve=samples,
            overlay_items=overlay_items,
            error=None if success else "No Siemens radii remained above threshold.",
        )


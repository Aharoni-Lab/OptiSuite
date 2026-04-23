from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


ChartType = Literal["auto", "usaf", "siemens", "grid", "slanted_edge", "contrast"]
FlipMode = Literal["auto", "not_flipped", "flipped"]


@dataclass(slots=True)
class OverlayItem:
    kind: Literal["line", "rect", "circle", "polygon", "point", "text"]
    points: list[tuple[int, int]] = field(default_factory=list)
    color: tuple[int, int, int] = (0, 255, 0)
    thickness: int = 2
    radius: int = 0
    text: str = ""


@dataclass(slots=True)
class ContrastSample:
    index: int
    label: str
    frequency: float | None = None
    contrast: float | None = None
    threshold_passed: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ThresholdReading:
    label: str
    value: str
    numeric_value: float | None = None
    unit: str = ""
    threshold: float = 0.2
    passed: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyzerConfig:
    chart_type: ChartType = "auto"
    contrast_threshold: float = 0.2
    show_preview: bool = False
    debug_mode: bool = False
    use_detection_fallback: bool = True
    allow_model_assist: bool = False
    flip_mode: FlipMode = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyzerResult:
    analyzer_id: str
    chart_type: ChartType
    image_path: str
    success: bool
    reading: ThresholdReading
    summary: str
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    contrast_curve: list[ContrastSample] = field(default_factory=list)
    overlay_items: list[OverlayItem] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def image_name(self) -> str:
        return Path(self.image_path).name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["image_name"] = self.image_name
        return data


@dataclass(slots=True)
class RouterDecision:
    chart_type: ChartType
    confidence: float
    reason: str
    candidates: dict[str, float] = field(default_factory=dict)
    used_model_fallback: bool = False


@dataclass(slots=True)
class ImageContext:
    image_path: str
    color_image: Any
    gray_image: Any
    normalized_gray: Any


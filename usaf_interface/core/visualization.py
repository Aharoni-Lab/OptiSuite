from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from usaf_interface.core.results import AnalyzerResult, OverlayItem

_RUNTIME_IMAGE_CACHE: dict[str, np.ndarray] = {}


def register_runtime_image(image_path: str, image: np.ndarray | None) -> None:
    if image is None:
        return
    _RUNTIME_IMAGE_CACHE[str(Path(image_path))] = image.copy()


def get_runtime_image(image_path: str) -> np.ndarray | None:
    cached = _RUNTIME_IMAGE_CACHE.get(str(Path(image_path)))
    if cached is None:
        return None
    return cached.copy()


def draw_overlay_item(image: np.ndarray, item: OverlayItem) -> None:
    color = tuple(int(value) for value in item.color)
    if item.kind == "line" and len(item.points) >= 2:
        cv2.line(image, item.points[0], item.points[1], color, item.thickness)
    elif item.kind == "rect" and len(item.points) >= 2:
        cv2.rectangle(image, item.points[0], item.points[1], color, item.thickness)
    elif item.kind == "circle" and item.points:
        cv2.circle(image, item.points[0], int(item.radius), color, item.thickness)
    elif item.kind == "polygon" and len(item.points) >= 3:
        pts = np.array(item.points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(image, [pts], True, color, item.thickness)
    elif item.kind == "point" and item.points:
        cv2.circle(image, item.points[0], max(2, item.thickness + 1), color, -1)
    elif item.kind == "text" and item.points:
        cv2.putText(image, item.text, item.points[0], cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, max(1, item.thickness))


def render_result_image(
    result: AnalyzerResult,
    max_size: tuple[int, int] | None = None,
    extra_overlay_items: list[OverlayItem] | None = None,
) -> Image.Image:
    image_key = str(Path(result.image_path))
    cached_image = _RUNTIME_IMAGE_CACHE.get(image_key)
    image = cached_image.copy() if cached_image is not None else cv2.imread(image_key)
    if image is None:
        fallback = Image.new("RGB", max_size or (640, 480), color=(30, 30, 30))
        return fallback

    for item in result.overlay_items:
        draw_overlay_item(image, item)
    # extra overlay for the current group and element being plotted in the plotter
    for item in extra_overlay_items or []:
        draw_overlay_item(image, item)

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rendered = Image.fromarray(image_rgb)
    if max_size is not None:
        rendered.thumbnail(max_size)
    return rendered


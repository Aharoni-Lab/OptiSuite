from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from core.results import AnalyzerResult, OverlayItem


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
    image = cv2.imread(str(result.image_path))
    if image is None:
        fallback = Image.new("RGB", max_size or (640, 480), color=(30, 30, 30))
        return fallback

    for item in result.overlay_items:
        draw_overlay_item(image, item)
    for item in extra_overlay_items or []:
        draw_overlay_item(image, item)

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rendered = Image.fromarray(image_rgb)
    if max_size is not None:
        rendered.thumbnail(max_size)
    return rendered


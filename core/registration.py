from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from core.results import ImageContext, OverlayItem


def load_image_context(image_path: str) -> ImageContext:
    color = cv2.imread(str(image_path))
    if color is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    brightest = float(np.max(gray))
    if brightest <= 0:
        normalized = gray.astype(np.float32)
    else:
        normalized = gray.astype(np.float32) / brightest

    return ImageContext(
        image_path=str(Path(image_path)),
        color_image=color,
        gray_image=gray,
        normalized_gray=normalized,
    )


def detect_long_lines(gray_image: np.ndarray) -> list[tuple[int, int, int, int]]:
    edges = cv2.Canny(gray_image, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=80,
        minLineLength=max(gray_image.shape[:2]) // 5,
        maxLineGap=20,
    )
    if lines is None:
        return []
    return [tuple(line[0]) for line in lines]


def detect_circle(gray_image: np.ndarray) -> tuple[int, int, int] | None:
    blurred = cv2.medianBlur(gray_image, 5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(gray_image.shape[:2]) // 4,
        param1=100,
        param2=20,
        minRadius=min(gray_image.shape[:2]) // 10,
        maxRadius=min(gray_image.shape[:2]) // 2,
    )
    if circles is None:
        return None
    x, y, radius = circles[0][0]
    return int(x), int(y), int(radius)


def dominant_line_angle(lines: list[tuple[int, int, int, int]]) -> float | None:
    if not lines:
        return None

    weighted_angles: list[tuple[float, float]] = []
    for x1, y1, x2, y2 in lines:
        dx = x2 - x1
        dy = y2 - y1
        length = float(np.hypot(dx, dy))
        if length < 1:
            continue
        angle = float(np.degrees(np.arctan2(dy, dx)))
        weighted_angles.append((angle, length))

    if not weighted_angles:
        return None

    best_angle, _weight = max(weighted_angles, key=lambda item: item[1])
    return best_angle


def grid_frequency_signature(gray_image: np.ndarray) -> tuple[float, float]:
    rows = gray_image.mean(axis=1)
    cols = gray_image.mean(axis=0)
    row_fft = np.abs(np.fft.rfft(rows - rows.mean()))
    col_fft = np.abs(np.fft.rfft(cols - cols.mean()))
    row_score = float(np.max(row_fft[1:])) if row_fft.size > 1 else 0.0
    col_score = float(np.max(col_fft[1:])) if col_fft.size > 1 else 0.0
    return row_score, col_score


def approximate_patch_rectangles(gray_image: np.ndarray) -> list[tuple[int, int, int, int]]:
    blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    rectangles: list[tuple[int, int, int, int]] = []
    min_area = gray_image.shape[0] * gray_image.shape[1] * 0.01

    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.03 * peri, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        area = w * h
        if area >= min_area:
            rectangles.append((x, y, x + w, y + h))

    unique_rectangles = []
    seen = set()
    for rect in rectangles:
        key = tuple(int(value / 4) for value in rect)
        if key not in seen:
            seen.add(key)
            unique_rectangles.append(rect)
    return unique_rectangles


def line_to_overlay(line: tuple[int, int, int, int], color: tuple[int, int, int] = (0, 255, 0)) -> OverlayItem:
    x1, y1, x2, y2 = line
    return OverlayItem(kind="line", points=[(x1, y1), (x2, y2)], color=color, thickness=2)


from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def create_siemens_star(path: Path, size: int = 512, spokes: int = 48) -> None:
    image = np.full((size, size, 3), 255, dtype=np.uint8)
    center = np.array([size // 2, size // 2])
    radius = size // 2 - 24

    for index in range(spokes):
        angle_start = 2.0 * math.pi * index / spokes
        angle_end = 2.0 * math.pi * (index + 1) / spokes
        color = 0 if index % 2 == 0 else 255
        points = np.array(
            [
                center,
                center + radius * np.array([math.cos(angle_start), math.sin(angle_start)]),
                center + radius * np.array([math.cos(angle_end), math.sin(angle_end)]),
            ],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(image, points, (color, color, color))

    cv2.circle(image, tuple(center), radius, (0, 0, 0), 3)
    cv2.imwrite(str(path), image)


def create_grid_pattern(path: Path, size: int = 512, period: int = 32) -> None:
    image = np.full((size, size, 3), 255, dtype=np.uint8)
    for row in range(0, size, period):
        cv2.line(image, (0, row), (size - 1, row), (0, 0, 0), 4)
    for col in range(0, size, period):
        cv2.line(image, (col, 0), (col, size - 1), (0, 0, 0), 4)
    cv2.imwrite(str(path), image)


def create_slanted_edge(path: Path, width: int = 640, height: int = 480) -> None:
    image = np.full((height, width, 3), 240, dtype=np.uint8)
    points = np.array([[0, height], [0, int(height * 0.3)], [width, 0], [width, height]], dtype=np.int32)
    cv2.fillConvexPoly(image, points, (30, 30, 30))
    cv2.line(image, (0, int(height * 0.3)), (width, 0), (255, 255, 255), 3)
    cv2.imwrite(str(path), image)


def create_contrast_chart(path: Path, width: int = 640, height: int = 480) -> None:
    image = np.full((height, width, 3), 200, dtype=np.uint8)
    patch_values = [240, 60, 220, 80, 200, 100, 180, 120]
    margin_x = 40
    margin_y = 60
    patch_w = 120
    patch_h = 120
    gap_x = 20
    gap_y = 30

    index = 0
    for row in range(2):
        for col in range(4):
            x1 = margin_x + col * (patch_w + gap_x)
            y1 = margin_y + row * (patch_h + gap_y)
            value = patch_values[index]
            cv2.rectangle(image, (x1, y1), (x1 + patch_w, y1 + patch_h), (value, value, value), -1)
            cv2.rectangle(image, (x1, y1), (x1 + patch_w, y1 + patch_h), (0, 0, 0), 2)
            index += 1
    cv2.imwrite(str(path), image)


def create_blank_image(path: Path, width: int = 512, height: int = 512) -> None:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.imwrite(str(path), image)


def main() -> None:
    entries = []

    usaf_dir = ROOT / "usaf"
    siemens_dir = ROOT / "siemens"
    grid_dir = ROOT / "grid"
    slanted_edge_dir = ROOT / "slanted_edge"
    contrast_dir = ROOT / "contrast"

    for directory in (usaf_dir, siemens_dir, grid_dir, slanted_edge_dir, contrast_dir):
        ensure_dir(directory)

    source_usaf = ROOT.parent / "test" / "test_image_g6e6_copy.png"
    target_usaf = usaf_dir / "usaf_reference.png"
    shutil.copy2(source_usaf, target_usaf)
    entries.append(
        {
            "name": "usaf_reference",
            "path": str(target_usaf.relative_to(ROOT.parent)),
            "expected_chart_type": "usaf",
            "expected_success": True,
        }
    )

    siemens_path = siemens_dir / "siemens_star.png"
    create_siemens_star(siemens_path)
    entries.append(
        {
            "name": "siemens_star",
            "path": str(siemens_path.relative_to(ROOT.parent)),
            "expected_chart_type": "siemens",
            "expected_success": True,
        }
    )

    grid_path = grid_dir / "grid_pattern.png"
    create_grid_pattern(grid_path)
    entries.append(
        {
            "name": "grid_pattern",
            "path": str(grid_path.relative_to(ROOT.parent)),
            "expected_chart_type": "grid",
            "expected_success": True,
        }
    )

    slanted_edge_path = slanted_edge_dir / "slanted_edge.png"
    create_slanted_edge(slanted_edge_path)
    entries.append(
        {
            "name": "slanted_edge",
            "path": str(slanted_edge_path.relative_to(ROOT.parent)),
            "expected_chart_type": "slanted_edge",
            "expected_success": True,
        }
    )

    contrast_path = contrast_dir / "contrast_chart.png"
    create_contrast_chart(contrast_path)
    entries.append(
        {
            "name": "contrast_chart",
            "path": str(contrast_path.relative_to(ROOT.parent)),
            "expected_chart_type": "contrast",
            "expected_success": True,
        }
    )

    failure_dir = ROOT / "failure"
    ensure_dir(failure_dir)
    blank_path = failure_dir / "blank.png"
    create_blank_image(blank_path)
    entries.append(
        {
            "name": "blank_failure",
            "path": str(blank_path.relative_to(ROOT.parent)),
            "expected_chart_type": "contrast",
            "expected_success": False,
        }
    )

    manifest_path = ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()


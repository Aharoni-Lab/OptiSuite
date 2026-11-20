"""
USAF 1951 scoring pipeline: find the big square, count the nested patterns with YOLO, place every
glyph's scanline by nested SIFT matching on the annotated templates (nested_match.py) and score
them with the scanline checker.
"""
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np


def calculate_scanline_contrast_scores(self, img):
    '''
    Scanline contrast scores for every glyph of the groups in view.

    Args:
        img: BGR image (contrast-normalized); the scanlines are drawn onto it.

    Returns (final_score, scanline_map) from bundle_scanline_scores; the per-glyph checker
    result and the matching record are in self.C.nested_result.
    '''
    if img is None:
        raise ValueError("usaf_algo.calculate_scanline_contrast_scores: Input image is None.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    normalized_gray = np.clip(gray.astype(float) / max(1, int(gray.max())), 0, 1)

    try:
        self.find_square_corners(gray)
    except ValueError:
        pass    # no square: nested matching uses a centred dummy square for layer 1

    pt4_pattern_result = self.count_4pts_pattern(img)
    self.C.pattern_count = len(pt4_pattern_result.boxes)
    if not self.C.FLIP_FIXED:
        self.yolo_4pt_calculation(pt4_pattern_result)     # sets FLIPED_TARGET
    if self.C.DEBUG_MODE:
        print(f"YOLO detected {self.C.pattern_count} patterns, flipped={self.C.FLIPED_TARGET}")
        plt.figure(figsize=(10, 8))
        plt.imshow(cv2.cvtColor(pt4_pattern_result.plot(font_size=1, line_width=1), cv2.COLOR_BGR2RGB))
        plt.title("4-point pattern detections")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

    out = self.nested_scanline_contrast_scores(img, gray, normalized_gray)

    if self.C.PREVIEW_MODE:
        plt.figure("Preview Scanlines", figsize=(8, 8))
        plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        plt.title("Preview Scanlines (green = resolved)")
        plt.show()
    return out


def bundle_scanline_scores(self, scores, scanlines):
    '''
    Merge each element's two scanlines (slot i and i + n, n = len(scores) // 2) into one score
    per score_table entry. Returns (final_score, scanline_map).
    '''
    final_score = {}
    scanline_map = {}
    n = len(scores) // 2
    for i in range(n):
        vert_score = abs(scores[i]["score"])
        horiz_score = abs(scores[i + n]["score"])

        if scores[i]["type"] == "local_min" or scores[i + n]["type"] == "local_min":
            temp_type = "local_min"
        else:
            temp_type = "grid"

        if self.C.SCORE_METHOD == "mean":
            temp_score = (vert_score + horiz_score) / 2.0
        elif self.C.SCORE_METHOD == "max":
            temp_score = max(vert_score, horiz_score)
        elif self.C.SCORE_METHOD == "min":
            temp_score = min(vert_score, horiz_score)
        else:
            temp_score = vert_score

        final_score[i] = {"score": float(temp_score), "type": temp_type}

        group, element = self.C.score_table[i]
        scanline_map[f"{group}:{element}"] = {
            "group": group,
            "element": element,
            "vertical": scanlines[i],
            "horizontal": scanlines[i + n],
            "score": float(temp_score),
            "type": temp_type,
            "lp_per_mm": self.usaf_lp_per_mm(group, element),
            "resolution_mm": self.usaf_resolution_mm(group, element),
        }

    return final_score, scanline_map


def find_usaf_score(self, image_path):
    '''
    Best resolved element for an image: the highest (group, element) the scanline checker
    calls resolved.

    Returns (best [group, element], scan_index, scanline_map, scores, processed image).
    '''
    self.C.current_image_path = str(image_path)
    raw = cv2.imread(str(image_path))
    if raw is None:
        raise ValueError(f"usaf_algo.find_usaf_score: Failed to read image from {image_path}")
    self.C.current_raw_image = raw.copy()
    img = np.clip(self.normalize_image_contrast(raw), 0, 255).astype(np.uint8)

    scores, scanline_map = self.calculate_scanline_contrast_scores(img)
    checker = self.C.nested_result["checker"]
    if checker["best"] is None:
        raise ValueError("usaf_algo.find_usaf_score: No best focus group found (no element resolved)")
    if self.C.DEBUG_MODE:
        print(f"Scores for {image_path}: {scores}")
    print(f"Best focus group for {image_path}: {checker['best'][0]}, element {checker['best'][1]}")
    return checker["best"], checker["scan_index"], scanline_map, scores, img


def score_image_routine(self, image_path):
    '''
    find_usaf_score without the processed image, cached to LOG_PATH/usaf_log_<name>.json.
    Images that can't be scored (unreadable, nested matching failed, nothing resolved) are
    logged and give None.
    '''
    usaf_result = None
    try:
        usaf_result = list(self.find_usaf_score(image_path))[:4]
    except ValueError as e:
        print(f"{e} ({image_path}). Skipping this image.")
    with open(self.C.LOG_PATH / f"usaf_log_{Path(image_path).stem}.json", "w") as file:
        json.dump((str(image_path), usaf_result), file, indent=4)
    return usaf_result

import cv2
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from . import constants as C



def sample_line_profile(gray, pt_a, pt_b, sample_count=200):
    """
    Samples a line profile with sub-pixel accuracy and guaranteed ordering.
    """
    # 1. Generate floating-point coordinates along the line
    # These represent the exact path from A to B
    xs = np.linspace(pt_a[0], pt_b[0], sample_count, dtype=np.float32)
    ys = np.linspace(pt_a[1], pt_b[1], sample_count, dtype=np.float32)

    # 2. Use Bi-linear Interpolation for smoother intensity values
    # Reshaping to (1, -1) makes it a 1-pixel high 'image' for remap
    line_pixels = cv2.remap(
        gray,
        xs.reshape(1, -1),
        ys.reshape(1, -1),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT
    ).flatten()

    # 3. Return coordinates (rounded for visualization) and the smooth pixels
    coords = np.column_stack((xs, ys))
    return coords, line_pixels



def is_image_clear(curr_image, threshold=3.0):
    if curr_image is None or curr_image.size == 0:
        if C.DEBUG_MODE:
            print("Input image is None or empty.")
        return 0.0

    # 2. Convert to Grayscale
    if curr_image.ndim == 3:
        gray = cv2.cvtColor(curr_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = curr_image

    denoised = cv2.bilateralFilter(gray, 5, 75, 75)
    laplacian_mtt = cv2.Laplacian(denoised, cv2.CV_64F)
    score = laplacian_mtt.var()
    if C.DEBUG_MODE:
        print("blurry score: ", score)
    return score >= threshold


def normalize_image_contrast(image, normalize_range=(0, 255)):
    """Normalize all pixels globally to the specified range.

    Args:
        image: Input image.
        normalize_range: Output range, inclusive. Default (0, 255)."""
    if image is None or image.size == 0:
        return image
    min_val = image.min()
    max_val = image.max()
    if max_val == min_val:
        return image.copy()
    out = (image.astype(np.float32) - float(min_val)) * ((normalize_range[1] - normalize_range[0]) / float(max_val - min_val)) + normalize_range[0]
    return out












def gradient_visualization(i, smooth_pixels, filtered_min_indices, local_min_count, dy):
    scan_idx = i // 2
    unique_count = len(C.score_table)
    base_idx = scan_idx % unique_count
    orientation = "vertical" if scan_idx < unique_count else "horizontal"
    group, element = C.score_table[base_idx]
    group_match = C.GRADIENT_PLOT_GROUP is None or group == C.GRADIENT_PLOT_GROUP
    element_match = C.GRADIENT_PLOT_ELEMENT is None or element == C.GRADIENT_PLOT_ELEMENT
    orient_match = C.GRADIENT_PLOT_ORIENTATION in ("both", orientation)

    if group_match and element_match and orient_match:
        print(
            f"Gradient debug: G{group} E{element} ({orientation}) "
            f"min_count={local_min_count}, minima={filtered_min_indices.tolist() if hasattr(filtered_min_indices, 'tolist') else filtered_min_indices}"
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, num="Gradient Debug", figsize=(10, 6), clear=True)
        ax1.plot(smooth_pixels, label="Smoothed intensity", color="tab:blue", linewidth=1.5)
        if len(filtered_min_indices) > 0:
            ax1.scatter(
                filtered_min_indices,
                smooth_pixels[filtered_min_indices],
                color="red",
                s=20,
                label="Detected minima",
                zorder=3,
            )
        ax1.set_title(f"Intensity profile - G{group} E{element} ({orientation})")
        ax1.set_xlabel("Sample index")
        ax1.set_ylabel("Intensity")
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc="best")

        ax2.plot(dy, label="Gradient", color="tab:orange", linewidth=1.5)
        ax2.axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
        ax2.set_title("Gradient profile")
        ax2.set_xlabel("Sample index")
        ax2.set_ylabel("dI/dx")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best")

        plt.tight_layout()
        plt.show(block=True)








def usaf_lp_per_mm(group: int, element: int) -> float:
    return float(2 ** (group + (element - 1) / 6.0))

def usaf_resolution_mm(group: int, element: int) -> float:
    return float(1.0 / (2.0 * usaf_lp_per_mm(group, element)))




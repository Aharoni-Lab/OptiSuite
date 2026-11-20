import cv2
import numpy as np


def sample_line_profile(self, gray, pt_a, pt_b, sample_count=200):
    """
    Samples a line profile with sub-pixel accuracy and guaranteed ordering.
    Returns (coords, line_pixels).
    """
    xs = np.linspace(pt_a[0], pt_b[0], sample_count, dtype=np.float32)
    ys = np.linspace(pt_a[1], pt_b[1], sample_count, dtype=np.float32)
    # bilinear interpolation along the line; (1, -1) makes it a 1-pixel high image for remap
    line_pixels = cv2.remap(
        gray,
        xs.reshape(1, -1),
        ys.reshape(1, -1),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT
    ).flatten()
    return np.column_stack((xs, ys)), line_pixels


def extend_line(self, pt_a, pt_b, extend_length=1.0):
    """Extends segment AB at both ends by extend_length x its length."""
    a = np.array(pt_a, dtype=np.float32)
    b = np.array(pt_b, dtype=np.float32)
    direction = b - a
    length = np.linalg.norm(direction)
    if length == 0:
        return a, b
    unit_vector = direction / length
    new_a = a - (unit_vector * extend_length * length)
    new_b = b + (unit_vector * extend_length * length)
    return (int(new_a[0]), int(new_a[1])), (int(new_b[0]), int(new_b[1]))


def normalize_image_contrast(self, image, normalize_range=(0, 255)):
    """Normalize all pixels globally to the specified range (inclusive, default (0, 255))."""
    if image is None or image.size == 0:
        return image
    min_val = image.min()
    max_val = image.max()
    if max_val == min_val:
        return image.copy()
    out = (image.astype(np.float32) - float(min_val)) * ((normalize_range[1] - normalize_range[0]) / float(max_val - min_val)) + normalize_range[0]
    return out


def usaf_lp_per_mm(self, group: int, element: int) -> float:
    return float(2 ** (group + (element - 1) / 6.0))


def usaf_resolution_mm(self, group: int, element: int) -> float:
    return float(1.0 / (2.0 * self.usaf_lp_per_mm(group, element)))

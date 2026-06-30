
import cv2
import numpy as np
import constants as C
from sift_warp import _sift_ref_origin_for_target







def get_rotated_pt(cx, cy, local_x, local_y, angle):
    '''
    find a rotated point at a certain angle and distance from a center point
    '''
    # Standard rotation formula
    rx = cx + local_x * np.cos(angle) - local_y * np.sin(angle)
    ry = cy + local_x * np.sin(angle) + local_y * np.cos(angle)
    return (int(rx), int(ry))





def usaf2screen_classic(pt, center_x, center_y, angle, side_length):
    # This scales the usaf coordinates to pixel scale
    scale = side_length
    loc = (pt[0] * scale, pt[1] * scale)

    # Convert from pixel usaf coordinate to screen coordinate
    # x were fliped b/c the usaf target is fliped
    # y were fliped b/c the screen coordinate system
    flip = -1 if C.FLIPED_TARGET else 1
    pt_a = get_rotated_pt(center_x, center_y, flip * loc[0], -loc[1], angle)
    return pt_a







def usaf2ref(pt):
    """
    Map a USAF-coordinate point to reference-image pixel coordinates using
    C.SIFT_REF_ORIGIN and SIFT_REF_PIXELS_PER_UNIT_*.

    Uses the same axis/sign convention as usaf2screen and
    sift_homography_with_origin.
    """
    origin = _sift_ref_origin_for_target()
    flip = -1 if C.FLIPED_TARGET else 1
    local_x = flip * pt[0]
    local_y = -pt[1]

    ref_x = origin[0] + local_x * C.SIFT_REF_PIXELS_PER_UNIT_X
    ref_y = origin[1] + local_y * C.SIFT_REF_PIXELS_PER_UNIT_Y
    return (ref_x, ref_y)


def usaf2screen_homography(pt, h_matrix):
    """
    Map a USAF-coordinate point to test-image screen coordinates via the reference
    image and homography from sift_homography_with_origin (ref -> test).

    1. USAF -> ref image pixels (angle=0, SIFT calibration constants, C.FLIPED_TARGET).
    2. Ref pixel -> local USAF frame -> test image via h_matrix (handles shear and other warps).

    h_matrix must be the matrix returned when calibrating with sift_homography_with_origin
    on the same (possibly flipped) reference image and sift origin as coordinate_calibration.
    """
    ref_x, ref_y = usaf2ref(pt)
    origin = _sift_ref_origin_for_target()
    local_x = (ref_x - origin[0]) / C.SIFT_REF_PIXELS_PER_UNIT_X
    local_y = (ref_y - origin[1]) / C.SIFT_REF_PIXELS_PER_UNIT_Y
    pt_local = np.array([[[local_x, local_y]]], dtype=np.float32)
    mapped = cv2.perspectiveTransform(pt_local, h_matrix)[0, 0]
    return (float(mapped[0]), float(mapped[1]))





def fast_usaf2screen_homography(pts, h_matrix):
    """Batched version of usaf2screen_homography.

    Takes a sequence of USAF-coordinate points and maps all of them to
    test-image screen coordinates in a single cv2.perspectiveTransform call.

    Args:
        pts:      Iterable of (x, y) USAF-coordinate points.
        h_matrix: Homography matrix (ref -> test) as returned by
                  sift_homography_with_origin / coordinate_calibration.

    Returns:
        List of (screen_x, screen_y) float tuples in the same order as ``pts``.
    """
    flip = -1 if C.FLIPED_TARGET else 1
    arr = np.array(pts, dtype=np.float32)           # (N, 2)
    local = np.empty_like(arr)
    local[:, 0] = flip * arr[:, 0]
    local[:, 1] = -arr[:, 1]
    pts_in = local.reshape(-1, 1, 2)                # (N, 1, 2) required by perspectiveTransform
    mapped = cv2.perspectiveTransform(pts_in, h_matrix).reshape(-1, 2)  # (N, 2)
    return [(float(mapped[i, 0]), float(mapped[i, 1])) for i in range(len(mapped))]





def ref_to_screen_homography_matrix(h_matrix):
    origin = _sift_ref_origin_for_target()
    ref_pixel_to_local = np.array(
        [
            [1.0 / C.SIFT_REF_PIXELS_PER_UNIT_X, 0.0, -origin[0] / C.SIFT_REF_PIXELS_PER_UNIT_X],
            [0.0, 1.0 / C.SIFT_REF_PIXELS_PER_UNIT_Y, -origin[1] / C.SIFT_REF_PIXELS_PER_UNIT_Y],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return np.asarray(h_matrix, dtype=np.float64) @ ref_pixel_to_local




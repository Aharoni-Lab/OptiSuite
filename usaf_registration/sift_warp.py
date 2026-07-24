import cv2
import numpy as np
import matplotlib.pyplot as plt
from . import constants as C




def get_sift_reference_image():
    return cv2.imread(C.SIFT_REF_IMAGE_PATH)




def _sift_ref_origin_for_target():
    """Origin on the SIFT reference image, mirrored when C.FLIPED_TARGET (matches coordinate_calibration)."""
    origin = C.SIFT_REF_ORIGIN
    if C.FLIPED_TARGET:
        ref_image = get_sift_reference_image()
        if ref_image is not None:
            origin = (ref_image.shape[1] - 1 - C.SIFT_REF_ORIGIN[0], C.SIFT_REF_ORIGIN[1])
    return origin






def sift_homography_with_origin(
    image1,
    image2,
    origin1=(0.0, 0.0),
    pixels_per_unit_x=1.0,
    pixels_per_unit_y=1.0,
    ratio_test=0.75,
    ransac_reproj_threshold=3.0,
    min_match_count=8,
    show_plot=True,
):
    """
    Find SIFT keypoints on image1/image2 and estimate homography from image1 to image2.
    image1 points are shifted to a local coordinate frame with origin at `origin1`,
    then scaled independently on x/y by `pixels_per_unit_x` and `pixels_per_unit_y`.
    """
    if image1 is None or image2 is None:
        raise ValueError("sift_warp.sift_homography_with_origin: image1 and image2 must not be None")
    if pixels_per_unit_x <= 0 or pixels_per_unit_y <= 0:
        raise ValueError("sift_warp.sift_homography_with_origin: pixels_per_unit_x and pixels_per_unit_y must be > 0")

    if image1.ndim == 3:
        gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
        vis1 = cv2.cvtColor(image1, cv2.COLOR_BGR2RGB)
    else:
        gray1 = image1.copy()
        vis1 = cv2.cvtColor(image1, cv2.COLOR_GRAY2RGB)

    if image2.ndim == 3:
        gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        vis2 = cv2.cvtColor(image2, cv2.COLOR_BGR2RGB)
    else:
        gray2 = image2.copy()
        vis2 = cv2.cvtColor(image2, cv2.COLOR_GRAY2RGB)

    if not hasattr(cv2, "SIFT_create"):
        raise RuntimeError("sift_warp.sift_homography_with_origin: OpenCV SIFT is unavailable in this build (missing cv2.SIFT_create)")

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(gray1, None)
    kp2, des2 = sift.detectAndCompute(gray2, None)
    if des1 is None or des2 is None or len(kp1) == 0 or len(kp2) == 0:
        raise RuntimeError("sift_warp.sift_homography_with_origin: Failed to extract SIFT descriptors from one or both images")

    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    knn_matches = matcher.knnMatch(des1, des2, k=2)
    good_matches = []
    for pair in knn_matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio_test * n.distance:
            good_matches.append(m)

    if len(good_matches) < min_match_count:
        raise RuntimeError(f"sift_warp.sift_homography_with_origin: Not enough good SIFT matches ({len(good_matches)}), need at least {min_match_count}")

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    # Convert src_pts to local coordinate frame and apply independent x/y scaling
    origin1 = np.array(origin1, dtype=np.float32)
    src_pts_local = src_pts - origin1[None, :]
    src_pts_local[:, 0] = src_pts_local[:, 0] / float(pixels_per_unit_x)
    src_pts_local[:, 1] = src_pts_local[:, 1] / float(pixels_per_unit_y)

    H, inlier_mask = cv2.findHomography(src_pts_local, dst_pts, cv2.RANSAC, ransac_reproj_threshold)
    if H is None or inlier_mask is None:
        raise RuntimeError("sift_warp.sift_homography_with_origin: Failed to estimate homography from SIFT correspondences")

    angle_deg = C.SIFT_ANGLE if C.SIFT_ANGLE is not None else 0.0
    if angle_deg != 0.0:
        theta = np.deg2rad(angle_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        R = np.array(
            [
                [cos_t, -sin_t, 0.0],
                [sin_t, cos_t, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        H = np.asarray(H, dtype=np.float64) @ R

    inlier_mask = inlier_mask.ravel().astype(bool)
    src_inlier = src_pts[inlier_mask]
    dst_inlier = dst_pts[inlier_mask]

    origin_local = np.array([[[0.0, 0.0]]], dtype=np.float32)
    origin_in_image2 = cv2.perspectiveTransform(origin_local, H)[0, 0]

    if show_plot:
        _, (ax1, ax2) = plt.subplots(1, 2, num="SIFT Homography Debug", figsize=(13, 6), clear=True)

        ax1.imshow(vis1)
        ax1.scatter([k.pt[0] for k in kp1], [k.pt[1] for k in kp1], s=6, c="yellow", alpha=0.35, label="All keypoints")
        if len(src_inlier) > 0:
            ax1.scatter(src_inlier[:, 0], src_inlier[:, 1], s=12, c="lime", alpha=0.9, label="Inlier matches")
        ax1.scatter([origin1[0]], [origin1[1]], s=80, c="red", marker="x", linewidths=2, label="Origin (image1)")
        ax1.set_title("Image1 keypoints + origin")
        ax1.set_xlim(0, vis1.shape[1])
        ax1.set_ylim(vis1.shape[0], 0)
        ax1.legend(loc="best")

        ax2.imshow(vis2)
        ax2.scatter([k.pt[0] for k in kp2], [k.pt[1] for k in kp2], s=6, c="yellow", alpha=0.35, label="All keypoints")
        if len(dst_inlier) > 0:
            ax2.scatter(dst_inlier[:, 0], dst_inlier[:, 1], s=12, c="cyan", alpha=0.9, label="Inlier matches")
        ax2.scatter([origin_in_image2[0]], [origin_in_image2[1]], s=80, c="magenta", marker="x", linewidths=2, label="Mapped origin")
        ax2.set_title("Image2 keypoints + mapped origin")
        ax2.set_xlim(0, vis2.shape[1])
        ax2.set_ylim(vis2.shape[0], 0)
        ax2.legend(loc="best")

        plt.tight_layout()
        plt.show(block=True)

    result = {
        "keypoints1": kp1,
        "keypoints2": kp2,
        "good_matches": good_matches,
        "inlier_mask": inlier_mask,
        "src_pts": src_pts,
        "src_pts_local": src_pts_local,
        "dst_pts": dst_pts,
        "src_inlier": src_inlier,
        "dst_inlier": dst_inlier,
        "origin1": (float(origin1[0]), float(origin1[1])),
        "pixels_per_unit_x": float(pixels_per_unit_x),
        "pixels_per_unit_y": float(pixels_per_unit_y),
        "origin_in_image2": (float(origin_in_image2[0]), float(origin_in_image2[1])),
    }
    return H, result




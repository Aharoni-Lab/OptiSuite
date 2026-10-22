"""
Draws scanlines for 4 variants per image: SIFT unadjusted, SIFT adjusted,
SIFT+elastix unadjusted, SIFT+elastix adjusted. Thick lines (red=unadjusted,
green=adjusted), two comparison images per source image (SIFT pair, elastix pair).

Note: AUTO_ADJUST defaults to False in production -- this forces it on to visualize
what it WOULD do, not what runs by default.

Usage:
    source .venv-usaf/bin/activate
    python scanline_adjust_report/run_batch.py
"""
import json
import re
import sys
import time
import importlib
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from usaf_interface.usaf_registration import UsafRegistration

itk = importlib.import_module("itk")

DATASET_DIR = Path("/Users/emmazhang/Downloads/usaf test images.v1i.coco/train")
OUT_DIR = Path(__file__).resolve().parent
ANNOTATED_DIR = OUT_DIR / "annotated"

sift_results = {r["image_id"]: r for r in json.loads((OUT_DIR.parent / "sift_batch_results" / "results.json").read_text())}

LINE_THICKNESS = 4


def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def resize_w(im_, w):
    h_ = max(1, int(im_.shape[0] * w / im_.shape[1]))
    return cv2.resize(im_, (w, h_))


def norm01(a):
    a = a.astype(np.float32)
    mn, mx = a.min(), a.max()
    return (a - mn) / (mx - mn) if mx > mn else a * 0


def setup_elastix(reg, gray):
    ref_image_sift = reg.get_sift_reference_image()
    if reg.C.FLIPED_TARGET:
        ref_image_sift = cv2.flip(ref_image_sift, 1)
    ref_gray = cv2.cvtColor(ref_image_sift, cv2.COLOR_BGR2GRAY)
    h_ref_to_target = reg.ref_to_screen_homography_matrix(reg.C._sift_h_matrix)
    sift_warped_ref = cv2.warpPerspective(ref_gray, h_ref_to_target, (gray.shape[1], gray.shape[0]))
    ys, xs = np.nonzero(sift_warped_ref)
    if len(xs) == 0:
        raise RuntimeError("SIFT-warped reference empty")
    margin = reg.C.ITKELASTIX_ROI_MARGIN
    x0 = max(0, int(xs.min()) - margin)
    y0 = max(0, int(ys.min()) - margin)
    x1 = min(gray.shape[1], int(xs.max()) + margin + 1)
    y1 = min(gray.shape[0], int(ys.max()) + margin + 1)
    fixed_roi = sift_warped_ref[y0:y1, x0:x1]
    moving_roi = gray[y0:y1, x0:x1]
    fixed_image = itk.image_from_array(norm01(fixed_roi))
    moving_image = itk.image_from_array(norm01(moving_roi))
    params = itk.ParameterObject.New()
    pmap = params.GetDefaultParameterMap(reg.C.ITKELASTIX_PARAMETER_MAP)
    pmap["Metric"] = ["AdvancedMattesMutualInformation"]
    pmap["NumberOfHistogramBins"] = ["32"]
    pmap["NumberOfResolutions"] = [str(reg.C.ITKELASTIX_NUMBER_OF_RESOLUTIONS)]
    pmap["MaximumNumberOfIterations"] = [str(reg.C.ITKELASTIX_MAX_ITERATIONS)]
    pmap["FinalGridSpacingInPhysicalUnits"] = [str(reg.C.ITKELASTIX_FINAL_GRID_SPACING)]
    pmap["GridSpacingSchedule"] = [
        str(float(2 ** (reg.C.ITKELASTIX_NUMBER_OF_RESOLUTIONS - i - 1)))
        for i in range(reg.C.ITKELASTIX_NUMBER_OF_RESOLUTIONS)
    ]
    params.AddParameterMap(pmap)
    _, transform_params = itk.elastix_registration_method(fixed_image, moving_image, parameter_object=params, log_to_console=False)
    reg.C._itk_transform_params = transform_params
    reg.C._itk_moving_image = moving_image
    reg.C._itk_output_dir = tempfile.mkdtemp(prefix="itkelastix_adjcmp_")
    reg.C._itk_roi_offset = (x0, y0)
    reg.C._itk_point_cache = {}


def draw_pair(img_norm, unadj_pts, adj_pts):
    vis = img_norm.copy()
    for (a, b), (aa, ab) in zip(unadj_pts, adj_pts):
        cv2.line(vis, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 0, 255), LINE_THICKNESS)
        cv2.line(vis, (int(aa[0]), int(aa[1])), (int(ab[0]), int(ab[1])), (0, 220, 0), LINE_THICKNESS)
    return vis


def process_image(file_path, original_name, image_id, flip_used):
    result = {"image_id": image_id, "original_name": original_name, "error": None}
    img = cv2.imread(str(file_path))
    if img is None:
        result["error"] = "failed to read image"
        return result

    reg = UsafRegistration()
    reg.C.PT_TRANSFORM = "sift"
    reg.C.FLIPED_TARGET = flip_used
    reg.C.AUTO_ADJUST = True  # force-enabled to visualize; defaults to False in production
    img_norm = reg.normalize_image_contrast(img)
    img_norm = np.clip(img_norm, 0, 255).astype(np.uint8)
    gray = cv2.cvtColor(img_norm, cv2.COLOR_BGR2GRAY)

    try:
        reg.find_square_corners(gray)
        if len(reg.C.valid_squares) == 0:
            result["error"] = "no square found"
            return result
        corners = reg.C.valid_squares[0].reshape(-1, 2)
        calib = reg.coordinate_calibration(gray, corners)
        if calib is None:
            result["error"] = "calibration failed"
            return result
        cx, cy, angle, sl = calib[0], calib[1], calib[2], calib[3]
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    brightest = np.max(gray)
    normalized_gray = np.clip(gray.astype(float) / brightest, 0, 1)
    n_total = len(reg.C.group_positions) // 2
    base = f"{image_id:03d}_{safe_name(Path(original_name).stem)}"

    # --- SIFT: unadjusted + adjusted ---
    sift_unadj, sift_adj = [], []
    sift_moves = []
    for k in range(n_total):
        raw_a = np.array(reg.C.group_positions[2 * k], dtype=np.float64)
        raw_b = np.array(reg.C.group_positions[2 * k + 1], dtype=np.float64)
        pt_a = reg.usaf_point_to_screen(raw_a, cx, cy, angle, sl)
        pt_b = reg.usaf_point_to_screen(raw_b, cx, cy, angle, sl)
        sift_unadj.append((pt_a, pt_b))
        try:
            adj_a, adj_b = reg.apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
        except Exception:
            adj_a, adj_b = pt_a, pt_b
        sift_adj.append((adj_a, adj_b))
        sift_moves.append(float(np.linalg.norm(np.array(adj_a) - np.array(pt_a)) + np.linalg.norm(np.array(adj_b) - np.array(pt_b))))

    vis_sift = draw_pair(img_norm, sift_unadj, sift_adj)
    sift_name = f"{base}_sift_adjust_compare.png"
    cv2.imwrite(str(ANNOTATED_DIR / sift_name), resize_w(vis_sift, 1100))
    result["sift_file"] = f"annotated/{sift_name}"
    result["sift_avg_move_px"] = round(sum(sift_moves) / len(sift_moves), 2)
    result["sift_max_move_px"] = round(max(sift_moves), 2)

    # --- SIFT+elastix: unadjusted + adjusted ---
    try:
        reg.C.PT_TRANSFORM = "elastix"
        setup_elastix(reg, gray)
        raw_pts = list(reg.C.group_positions.values())
        mapped = reg.fast_ref_usaf_point_to_target(raw_pts, n_workers=4)
        elastix_unadj, elastix_adj = [], []
        elastix_moves = []
        for k in range(n_total):
            pt_a, pt_b = mapped[2 * k], mapped[2 * k + 1]
            elastix_unadj.append((pt_a, pt_b))
            try:
                adj_a, adj_b = reg.apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
            except Exception:
                adj_a, adj_b = pt_a, pt_b
            elastix_adj.append((adj_a, adj_b))
            elastix_moves.append(float(np.linalg.norm(np.array(adj_a) - np.array(pt_a)) + np.linalg.norm(np.array(adj_b) - np.array(pt_b))))

        vis_elastix = draw_pair(img_norm, elastix_unadj, elastix_adj)
        elastix_name = f"{base}_elastix_adjust_compare.png"
        cv2.imwrite(str(ANNOTATED_DIR / elastix_name), resize_w(vis_elastix, 1100))
        result["elastix_file"] = f"annotated/{elastix_name}"
        result["elastix_avg_move_px"] = round(sum(elastix_moves) / len(elastix_moves), 2)
        result["elastix_max_move_px"] = round(max(elastix_moves), 2)
    except Exception as e:
        result["elastix_error"] = f"{type(e).__name__}: {e}"

    result["n_total"] = n_total
    return result


def main():
    coco = json.loads((DATASET_DIR / "_annotations.coco.json").read_text())
    images = coco["images"]
    print(f"processing {len(images)} images...")

    results = []
    for i, im in enumerate(images):
        sift_r = sift_results.get(im["id"])
        if sift_r is None or not sift_r.get("calibration_ok"):
            results.append({"image_id": im["id"], "original_name": im.get("extra", {}).get("name", ""), "error": "no prior SIFT calibration"})
            print(f"[{i+1}/{len(images)}] skip (no SIFT calibration)")
            continue
        extra = im.get("extra", {})
        original_name = extra.get("name", im["file_name"])
        file_path = DATASET_DIR / im["file_name"]
        t0 = time.time()
        r = process_image(file_path, original_name, im["id"], sift_r["flip_used"])
        r["elapsed_s"] = round(time.time() - t0, 2)
        r["user_tags"] = extra.get("user_tags", [])
        results.append(r)
        status = "OK" if r.get("elastix_file") else f"PARTIAL ({r.get('error') or r.get('elastix_error')})"
        print(f"[{i+1}/{len(images)}] {original_name}: {status} ({r['elapsed_s']}s)")

    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT_DIR / 'results.json'}")


if __name__ == "__main__":
    main()

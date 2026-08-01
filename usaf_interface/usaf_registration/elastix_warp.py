import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import importlib
from . import constants as C
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from .transforms import usaf2screen_homography, fast_usaf2screen_homography, ref_to_screen_homography_matrix




try:
    itk = importlib.import_module("itk")
except ImportError:
    itk = None





def normalize_for_registration(image):
    image = image.astype(np.float32)
    min_val = float(np.min(image))
    max_val = float(np.max(image))
    if max_val <= min_val:
        raise ValueError("elastix_warp.normalize_for_registration: Cannot normalize image with zero or negative dynamic range.")
    return (image - min_val) / (max_val - min_val)






def _run_transformix_batch(local_points, work_dir):
    """Write a batch of local-space points, run transformix once, return list of local-space output points."""
    input_path = Path(work_dir) / "inputpoints.txt"
    output_path = Path(work_dir) / "outputpoints.txt"

    lines = [f"point\n{len(local_points)}"] + [f"{lx} {ly}" for lx, ly in local_points]
    input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if output_path.exists():
        output_path.unlink()

    transformix = itk.TransformixFilter.New(C._itk_moving_image)
    transformix.SetFixedPointSetFileName(str(input_path))
    transformix.SetTransformParameterObject(C._itk_transform_params)
    transformix.SetOutputDirectory(str(work_dir))
    if hasattr(transformix, "SetLogToConsole"):
        transformix.SetLogToConsole(C.ITKELASTIX_LOG_TO_CONSOLE)
    transformix.UpdateLargestPossibleRegion()

    with open(output_path, "r", encoding="utf-8") as f:
        out_lines = f.readlines()

    results = []
    for line in out_lines:
        part = line.split("OutputPoint = [", 1)[1].split("]", 1)[0]
        x, y = [float(v) for v in part.split()[:2]]
        results.append((x, y))
    return results


def fast_transformix_point(points, n_workers=4):
    """Transform a list of points through ITKElastix in parallel.

    Points are split into ``n_workers`` batches; each batch is submitted to a
    thread that calls transformix once against its own temporary working
    directory.  Results are reassembled in the original order.  Points already
    present in the global cache are returned immediately without touching
    the engine.
    """
    if C._itk_transform_params is None:
        raise RuntimeError("elastix_warp.fast_transformix_point: ITKElastix registration has not been performed yet.")
    if not points:
        return []

    ox, oy = C._itk_roi_offset

    # ── split into cached / uncached ──────────────────────────────────────────
    output = [None] * len(points)
    uncached_idx = []       # positions in `points` that need the engine
    uncached_local = []     # corresponding ROI-local coordinates

    for i, pt in enumerate(points):
        key = (round(float(pt[0]), 4), round(float(pt[1]), 4))
        if key in C._itk_point_cache:
            output[i] = C._itk_point_cache[key]
        else:
            uncached_idx.append(i)
            uncached_local.append((float(pt[0]) - ox, float(pt[1]) - oy))

    if not uncached_local:
        return output

    # ── chunk into batches and run in parallel ────────────────────────────────
    n_workers = max(1, min(n_workers, len(uncached_local)))
    chunk_size = (len(uncached_local) + n_workers - 1) // n_workers
    chunks = [
        (uncached_idx[i: i + chunk_size], uncached_local[i: i + chunk_size])
        for i in range(0, len(uncached_local), chunk_size)
    ]

    work_dirs = [tempfile.mkdtemp(prefix="itkelastix_batch_") for _ in chunks]

    def process_chunk(args):
        orig_indices, local_pts, work_dir = args
        local_results = _run_transformix_batch(local_pts, work_dir)
        return orig_indices, local_pts, local_results

    chunk_args = [(idx_list, loc_list, wd) for (idx_list, loc_list), wd in zip(chunks, work_dirs)]

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(process_chunk, arg): arg for arg in chunk_args}
        for future in as_completed(futures):
            orig_indices, local_pts, local_results = future.result()
            for orig_i, (lx, ly), (rx, ry) in zip(orig_indices, local_pts, local_results):
                result = (rx + ox, ry + oy)
                orig_pt = points[orig_i]
                key = (round(float(orig_pt[0]), 4), round(float(orig_pt[1]), 4))
                C._itk_point_cache[key] = result
                output[orig_i] = result

    return output













def transformix_point(point):
    if C._itk_transform_params is None:
        raise RuntimeError("elastix_warp.transformix_point: ITKElastix registration has not been performed yet.")

    key = (round(float(point[0]), 4), round(float(point[1]), 4))
    if key in C._itk_point_cache:
        return C._itk_point_cache[key]

    ox, oy = C._itk_roi_offset
    local_x = float(point[0]) - ox
    local_y = float(point[1]) - oy
    input_path = Path(C._itk_output_dir) / "inputpoints.txt"
    output_path = Path(C._itk_output_dir) / "outputpoints.txt"
    input_path.write_text(f"point\n1\n{local_x} {local_y}\n", encoding="utf-8")
    if output_path.exists():
        output_path.unlink()

    transformix = itk.TransformixFilter.New(C._itk_moving_image)
    transformix.SetFixedPointSetFileName(str(input_path))
    transformix.SetTransformParameterObject(C._itk_transform_params)
    transformix.SetOutputDirectory(str(C._itk_output_dir))
    if hasattr(transformix, "SetLogToConsole"):
        transformix.SetLogToConsole(C.ITKELASTIX_LOG_TO_CONSOLE)
    transformix.UpdateLargestPossibleRegion()

    with open(output_path, "r", encoding="utf-8") as f:
        line = f.readline()
    output_part = line.split("OutputPoint = [", 1)[1].split("]", 1)[0]
    x, y = [float(value) for value in output_part.split()[:2]]
    result = (x + ox, y + oy)
    C._itk_point_cache[key] = result
    return result


def ref_usaf_point_to_target(pt):
    rough_x, rough_y = usaf2screen_homography(pt, C._sift_h_matrix)
    return transformix_point((rough_x, rough_y))


def fast_ref_usaf_point_to_target(pts, n_workers=4):
    """Batched version of ref_usaf_point_to_target.

    Maps a list of USAF-coordinate points to target-image coordinates by
    first converting all points to rough screen coordinates in one vectorized
    call (fast_usaf2screen_homography), then refining them all through
    ITKElastix in parallel (fast_transformix_point).

    Args:
        pts:       Iterable of (x, y) USAF-coordinate points.
        n_workers: Number of parallel transformix workers (passed through to
                   fast_transformix_point).

    Returns:
        List of (target_x, target_y) float tuples in the same order as ``pts``.
    """
    pts = list(pts)
    if not pts:
        return []
    rough_pts = fast_usaf2screen_homography(pts, C._sift_h_matrix)
    return fast_transformix_point(rough_pts, n_workers=n_workers)


def show_itkelastix_preview(target_gray, sift_warped_ref, fixed_roi, registered_target_roi, roi_rect):
    def overlay(a, b):
        return np.dstack((normalize_for_registration(a), normalize_for_registration(b), normalize_for_registration(b)))

    x0, y0, w, h = roi_rect
    plt.figure("ITKElastix Mapping Preview", figsize=(13, 8))
    plt.clf()

    ax1 = plt.subplot(2, 2, 1)
    ax1.imshow(target_gray, cmap="gray")
    ax1.set_title("Target image")
    ax1.axis("off")

    ax2 = plt.subplot(2, 2, 2)
    ax2.imshow(overlay(target_gray, sift_warped_ref))
    ax2.set_title("SIFT warped ref overlay")
    ax2.axis("off")

    ax3 = plt.subplot(2, 2, 3)
    ax3.imshow(overlay(fixed_roi, registered_target_roi))
    ax3.set_title("ITKElastix ROI overlay")
    ax3.axis("off")

    ax4 = plt.subplot(2, 2, 4)
    ax4.imshow(target_gray, cmap="gray")
    ax4.add_patch(plt.Rectangle((x0, y0), w, h, fill=False, edgecolor="cyan", linewidth=1.5))
    ax4.set_title("SIFT circles, ITKElastix x")
    ax4.axis("off")

    for label, coord in zip(["TR", "TL", "LR", "LL"], [C.top_right_ref_coord, C.top_left_ref_coord, C.low_right_ref_coord, C.low_left_ref_coord]):
        sx, sy = usaf2screen_homography(coord, C._sift_h_matrix)
        ix, iy = ref_usaf_point_to_target(coord)
        ax4.scatter([sx], [sy], s=45, c="yellow", marker="o")
        ax4.scatter([ix], [iy], s=55, c="lime", marker="x")
        ax4.text(ix + 5, iy - 5, label, color="lime", fontsize=9)

    plt.tight_layout()
    plt.show(block=True)


def setup_itkelastix_ref_mapping(ref_image, target_gray, h_matrix):
    if itk is None:
        raise RuntimeError("elastix_warp.setup_itkelastix_ref_mapping: Install ITKElastix with: pip install itk-elastix")

    ref_gray = cv2.cvtColor(ref_image, cv2.COLOR_BGR2GRAY) if ref_image.ndim == 3 else ref_image.copy()
    h_ref_to_target = ref_to_screen_homography_matrix(h_matrix)
    sift_warped_ref = cv2.warpPerspective(ref_gray, h_ref_to_target, (target_gray.shape[1], target_gray.shape[0]))

    ys, xs = np.nonzero(sift_warped_ref)
    if len(xs) == 0:
        raise RuntimeError("elastix_warp.setup_itkelastix_ref_mapping: SIFT-warped reference is empty")
    x0 = max(0, int(xs.min()) - C.ITKELASTIX_ROI_MARGIN)
    y0 = max(0, int(ys.min()) - C.ITKELASTIX_ROI_MARGIN)
    x1 = min(target_gray.shape[1], int(xs.max()) + C.ITKELASTIX_ROI_MARGIN + 1)
    y1 = min(target_gray.shape[0], int(ys.max()) + C.ITKELASTIX_ROI_MARGIN + 1)

    fixed_roi = sift_warped_ref[y0:y1, x0:x1]  # fixed points are rough SIFT target-space points
    moving_roi = target_gray[y0:y1, x0:x1]     # transformix maps fixed points into this target image
    fixed_image = itk.image_from_array(normalize_for_registration(fixed_roi))
    moving_image = itk.image_from_array(normalize_for_registration(moving_roi))

    params = itk.ParameterObject.New()
    parameter_map = params.GetDefaultParameterMap(C.ITKELASTIX_PARAMETER_MAP)
    parameter_map["Metric"] = ["AdvancedMattesMutualInformation"]
    parameter_map["NumberOfHistogramBins"] = ["32"]
    parameter_map["NumberOfResolutions"] = [str(C.ITKELASTIX_NUMBER_OF_RESOLUTIONS)]
    parameter_map["MaximumNumberOfIterations"] = [str(C.ITKELASTIX_MAX_ITERATIONS)]
    if C.ITKELASTIX_PARAMETER_MAP == "bspline":
        parameter_map["FinalGridSpacingInPhysicalUnits"] = [str(C.ITKELASTIX_FINAL_GRID_SPACING)]
        parameter_map["GridSpacingSchedule"] = [
            str(float(2 ** (C.ITKELASTIX_NUMBER_OF_RESOLUTIONS - idx - 1)))
            for idx in range(C.ITKELASTIX_NUMBER_OF_RESOLUTIONS)
        ]
    params.AddParameterMap(parameter_map)
    registered, transform_params = itk.elastix_registration_method(
        fixed_image,
        moving_image,
        parameter_object=params,
        log_to_console=C.ITKELASTIX_LOG_TO_CONSOLE,
    )

    C._itk_transform_params = transform_params
    C._itk_moving_image = moving_image
    C._itk_output_dir = tempfile.mkdtemp(prefix="itkelastix_usaf_")
    C._itk_roi_offset = (x0, y0)
    C._itk_point_cache = {}

    if C.ITKELASTIX_SHOW_PLOT:
        show_itkelastix_preview(
            target_gray,
            sift_warped_ref,
            fixed_roi,
            itk.array_from_image(registered),
            (x0, y0, x1 - x0, y1 - y0),
        )

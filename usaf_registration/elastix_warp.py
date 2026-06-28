import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import importlib
import constants as C
import tempfile
from transforms import usaf2screen_homography, ref_to_screen_homography_matrix




try:
    itk = importlib.import_module("itk")
except ImportError:
    itk = None





def normalize_for_registration(image):
    image = image.astype(np.float32)
    min_val = float(np.min(image))
    max_val = float(np.max(image))
    if max_val <= min_val:
        return np.zeros_like(image, dtype=np.float32)
    return (image - min_val) / (max_val - min_val)


def transformix_point(point):
    if C._itk_transform_params is None:
        return (float(point[0]), float(point[1]))

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
        raise RuntimeError("Install ITKElastix with: pip install itk-elastix")

    ref_gray = cv2.cvtColor(ref_image, cv2.COLOR_BGR2GRAY) if ref_image.ndim == 3 else ref_image.copy()
    h_ref_to_target = ref_to_screen_homography_matrix(h_matrix)
    sift_warped_ref = cv2.warpPerspective(ref_gray, h_ref_to_target, (target_gray.shape[1], target_gray.shape[0]))

    ys, xs = np.nonzero(sift_warped_ref)
    if len(xs) == 0:
        raise RuntimeError("SIFT-warped reference is empty")
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

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from yolo_model import extract_yolo_detections, visualize_detections, count_4pts_pattern
from scipy.signal import savgol_filter
import constants as C
from sift_warp import get_sift_reference_image, sift_homography_with_origin
from classic_warp import find_white_corner_in_region, find_target_orientation, get_adjusted_top_corners_from_enclosing_rectangle, find_square_corners
from elastix_warp import setup_itkelastix_ref_mapping, ref_usaf_point_to_target
from pt_adjust import apply_point_adjustment_algorithm, find_replacement_keypoints, extend_line
from transforms import usaf2screen_homography, usaf2screen_classic, get_rotated_pt
from pattern_crop import find_pattern_crop, classify_pattern_resolution, show_pattern_classification_results


#------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Coordinate Definitions:
# usaf coordinate system: origin is the center of the square in usaf target, axis align with edge of square and 1.0 unit = side length of the square
#                         negative y axis point toward center of the target, and positive x axis point toward the group with higher group number
# standard coordinate system: origin at the bottom left corner of the image, positive y axis point upward, positive x axis point rightward, unit in pixel
# screen coordinate system: origin at the top left corner of the image, positive y axis point downward, positive x axis point rightward, unit in pixel
#------------------------------------------------------------------------------------------------------------------------------------------------------------------







def usaf_lp_per_mm(group: int, element: int) -> float:
    return float(2 ** (group + (element - 1) / 6.0))

def usaf_resolution_mm(group: int, element: int) -> float:
    return float(1.0 / (2.0 * usaf_lp_per_mm(group, element)))






def coordinate_calibration(gray, corners):
    '''
    Calibrates the coordinate system using the corners of the square
    '''
    C._sift_h_matrix = None
    C._itk_transform_params = None
    C._itk_moving_image = None
    C._itk_output_dir = None
    C._itk_roi_offset = (0, 0)
    C._itk_point_cache = {}

    # if any corner is on the edge of the image, return None to trigger retry with next best square
    if not C.USE_SIFT_REF_CALIBRATION:
        for corner in corners:
            if corner[0] <= 0 or corner[0] >= gray.shape[1] - 1 or corner[1] <= 0 or corner[1] >= gray.shape[0] - 1:
                if C.DEBUG_MODE:
                    print("Corner on edge detected, retrying with next best square...")
                return None


    # Initial coordinate calibration using the corners of the square
    corners = np.array(corners)
    min_x = np.min(corners[:, 0])
    max_x = np.max(corners[:, 0])
    min_y = np.min(corners[:, 1])
    max_y = np.max(corners[:, 1])
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    side_length = np.linalg.norm(corners[0] - corners[1])

    index = np.argmax(corners[:, 1])
    top_corner = corners[index]
    # remove the top corner from corners
    corners = np.delete(corners, index, axis=0)
    index = np.argmin(corners[:, 0])
    left_corner = corners[index]
    corners = np.delete(corners, index, axis=0)
    index = np.argmax(corners[:, 0])
    right_corner = corners[index]
    corners = np.delete(corners, index, axis=0)
    index = np.argmin(corners[:, 1])
    bottom_corner = corners[index]

    #find unit vector that point from left corner to top corner
    unit_vector = (top_corner - left_corner) / np.linalg.norm(top_corner - left_corner)
    #find angle of unit vector with y axis, negate because the screen coordinate system is flipped
    angle = -np.arctan2(unit_vector[1], unit_vector[0])

    # if 0.9 * np.pi / 2 < np.abs(angle) or 0.1 * np.pi / 2 > np.abs(angle):
        # raise ValueError("Angle too small or large, retrying with rotation...")


    # find orientation of the target
    orientation = find_target_orientation(gray, center_x, center_y, unit_vector, side_length)
    angle = angle + orientation * np.pi / 2



    #Seconary coordinate calibration using the reference corners
    # left and right ref corner are in standard coordinates 
    TL_dir = C.prefer_dir_table[orientation][0]
    TR_dir = C.prefer_dir_table[orientation][1]
    BL_dir = C.prefer_dir_table[orientation][2]
    BR_dir = C.prefer_dir_table[orientation][3]
    if C.FLIPED_TARGET:
        TR_dir, TL_dir = TL_dir, TR_dir
        BR_dir, BL_dir = BL_dir, BR_dir
    
    if C.USE_SIFT_REF_CALIBRATION:
        ref_image = get_sift_reference_image()
        if ref_image is None:
            if C.DEBUG_MODE:
                print(f"Failed to load SIFT reference image: {C.SIFT_REF_IMAGE_PATH}")
            return None
        try:
            ref_image_sift = ref_image
            sift_origin = C.SIFT_REF_ORIGIN
            if C.FLIPED_TARGET:
                # Mirror the reference image to match flipped target orientation.
                ref_image_sift = cv2.flip(ref_image, 1)
                sift_origin = (ref_image.shape[1] - 1 - C.SIFT_REF_ORIGIN[0], C.SIFT_REF_ORIGIN[1])

            h_matrix, _ = sift_homography_with_origin(
                ref_image_sift,
                gray,
                origin1=sift_origin,
                pixels_per_unit_x=C.SIFT_REF_PIXELS_PER_UNIT_X,
                pixels_per_unit_y=C.SIFT_REF_PIXELS_PER_UNIT_Y,
                ratio_test=C.SIFT_REF_RATIO_TEST,
                ransac_reproj_threshold=C.SIFT_REF_RANSAC_REPROJ,
                min_match_count=C.SIFT_REF_MIN_MATCH_COUNT,
                show_plot=C.SIFT_REF_SHOW_PLOT,
            )
            C._sift_h_matrix = h_matrix
            if C.USE_ITKELASTIX_REF_CALIBRATION:
                try:
                    setup_itkelastix_ref_mapping(ref_image_sift, gray, h_matrix)
                except Exception as exc:
                    C._itk_transform_params = None
                    C._itk_moving_image = None
                    C._itk_output_dir = None
                    C._itk_roi_offset = (0, 0)
                    C._itk_point_cache = {}
                    if C.DEBUG_MODE:
                        print(f"ITKElastix mapping failed; using SIFT only: {exc}")
            # Use same axis/sign convention as usaf2screen:
            # x may flip by C.FLIPED_TARGET, and y is inverted for screen coordinates.
            flip = -1 if C.FLIPED_TARGET else 1
            if C._itk_transform_params is not None:
                mapped = np.array(
                    [
                        ref_usaf_point_to_target(C.top_right_ref_coord),
                        ref_usaf_point_to_target(C.top_left_ref_coord),
                        ref_usaf_point_to_target(C.low_right_ref_coord),
                        ref_usaf_point_to_target(C.low_left_ref_coord),
                    ],
                    dtype=np.float64,
                )
            else:
                ref_pts_local = np.array(
                    [
                        [[flip * C.top_right_ref_coord[0], -C.top_right_ref_coord[1]]],
                        [[flip * C.top_left_ref_coord[0], -C.top_left_ref_coord[1]]],
                        [[flip * C.low_right_ref_coord[0], -C.low_right_ref_coord[1]]],
                        [[flip * C.low_left_ref_coord[0], -C.low_left_ref_coord[1]]],
                    ],
                    dtype=np.float32,
                )
                mapped = cv2.perspectiveTransform(ref_pts_local, h_matrix).reshape(-1, 2)
            # mapped points are in screen coordinates; convert to standard coordinates
            # to match the legacy find_white_corner_in_region() output convention.
            top_right_ref_corner = (float(mapped[0, 0]), float(gray.shape[0] - 1 - mapped[0, 1]))
            top_left_ref_corner = (float(mapped[1, 0]), float(gray.shape[0] - 1 - mapped[1, 1]))
            low_right_ref_corner = (float(mapped[2, 0]), float(gray.shape[0] - 1 - mapped[2, 1]))
            low_left_ref_corner = (float(mapped[3, 0]), float(gray.shape[0] - 1 - mapped[3, 1]))
 
            if C.SIFT_REF_SHOW_PLOT:
                sift_vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
                labels = ["TR", "TL", "LR", "LL"]
                colors = ["magenta", "cyan", "yellow", "lime"]
                plt.figure("SIFT mapped ref corners", figsize=(8, 8))
                plt.clf()
                plt.imshow(sift_vis)
                for idx, (x, y) in enumerate(mapped):
                    x_i, y_i = int(round(x)), int(round(y))
                    plt.scatter([x_i], [y_i], s=60, c=colors[idx], marker="x")
                    plt.text(x_i + 6, y_i - 6, labels[idx], color=colors[idx], fontsize=9)
                    print(f"Mapped reference corner {labels[idx]}: ({x_i}, {y_i})")
                plt.title("Mapped reference corners on test image")
                plt.xlim(0, sift_vis.shape[1])
                plt.ylim(sift_vis.shape[0], 0)
                plt.tight_layout()
                plt.show(block=True)
        except Exception as exc:
            if C.DEBUG_MODE:
                print(f"SIFT reference calibration failed: {exc}")
            return None
    else:
        top_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_right_ref_coord, 1.0/5.0, TL_dir)
        top_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_left_ref_coord, 1.0/5.0, TR_dir)
        low_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_right_ref_coord, 1.0/5.0, BL_dir)
        low_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_left_ref_coord, 1.0/5.0, BR_dir)


    if top_right_ref_corner is not None and top_left_ref_corner is not None and low_right_ref_corner is not None and low_left_ref_corner is not None and C.FOUR_KP == True:
        adjusted_top_right, adjusted_top_left = get_adjusted_top_corners_from_enclosing_rectangle(
            top_right_ref_corner,
            top_left_ref_corner,
            low_right_ref_corner,
            low_left_ref_corner,
        )

        ref_vector = np.array(adjusted_top_right) - np.array(adjusted_top_left)
        ref_unit_vector = ref_vector / np.linalg.norm(ref_vector)
        flip = 1 if C.FLIPED_TARGET else -1
        ref_normal_vector = flip * np.array([-ref_unit_vector[1], ref_unit_vector[0]])
        dist = np.sqrt(ref_vector[0]**2 + ref_vector[1]**2)
        #recalculate angle using the right reference corner and left reference corner

        #find angle of ref_normal_vector with y axis, negate because the screen coordinate system is flipped for top case
        angle = np.arctan2(np.abs(ref_unit_vector[1]), np.abs(ref_unit_vector[0]))
        if orientation == 0:                     #top case
            angle = -angle
        elif orientation == 3:                   #left case
            angle = angle - np.pi
        elif orientation == 2:                   #bottom case
            angle = np.pi - angle
        elif orientation == 1:                   #right case
            angle = angle

        if C.DEBUG_MODE:
            print(f"Angle: {angle / np.pi * 180}")

        #recalculate center_x and center_y using the right reference corner and left reference corner
        #the center should be 0.579617834395 * distance from right reference corner to left reference corner away from 
        #the left reference corner in the direction of the unit vector from left reference corner to right reference corner
        if dist > 0:
            # Calculate the offset distance in usaf axis but standard scale based on ratio
            sum_length = C.top_left_ref_coord[0] + np.abs(C.top_right_ref_coord[0])
            offset_dist_x = C.top_left_ref_coord[0] * dist / sum_length
            offset_dist_y = 1.00 * dist * 0.5 / sum_length
            center_x = adjusted_top_left[0] + (ref_unit_vector[0] * offset_dist_x) - (ref_normal_vector[0] * offset_dist_y)
            center_y = adjusted_top_left[1] + (ref_unit_vector[1] * offset_dist_x) - (ref_normal_vector[1] * offset_dist_y)
            # convert from standard coordinate back to screen coordinates
            center_y = gray.shape[0] - 1 - center_y

            #recalculate side_length using the distance between the right reference corner and left reference corner
            # evil magic scaling factor 1.007
            side_length = 1.00 * dist * 1.007 / sum_length

        return [center_x, center_y, angle, side_length, adjusted_top_right, adjusted_top_left, low_right_ref_corner, low_left_ref_corner]
    elif top_right_ref_corner is not None and top_left_ref_corner is not None and C.FOUR_KP == False:
        ref_vector = np.array(top_right_ref_corner) - np.array(top_left_ref_corner)
        ref_unit_vector = ref_vector / np.linalg.norm(ref_vector)
        flip = 1 if C.FLIPED_TARGET else -1
        ref_normal_vector = flip * np.array([-ref_unit_vector[1], ref_unit_vector[0]])
        dist = np.sqrt(ref_vector[0]**2 + ref_vector[1]**2)
        #recalculate angle using the right reference corner and left reference corner

        #find angle of ref_normal_vector with y axis, negate because the screen coordinate system is flipped for top case
        angle = np.arctan2(np.abs(ref_unit_vector[1]), np.abs(ref_unit_vector[0]))
        if orientation == 0:                     #top case
            angle = -angle
        elif orientation == 3:                   #left case
            angle = angle - np.pi
        elif orientation == 2:                   #bottom case
            angle = np.pi - angle
        elif orientation == 1:                   #right case
            angle = angle

        if C.DEBUG_MODE:
            print(f"Angle: {angle / np.pi * 180}")

        #recalculate center_x and center_y using the right reference corner and left reference corner
        #the center should be 0.579617834395 * distance from right reference corner to left reference corner away from 
        #the left reference corner in the direction of the unit vector from left reference corner to right reference corner
        if dist > 0:
            # Calculate the offset distance in usaf axis but standard scale based on ratio
            sum_length = C.top_left_ref_coord[0] + np.abs(C.top_right_ref_coord[0])
            offset_dist_x = C.top_left_ref_coord[0] * dist / sum_length
            offset_dist_y = 1.00 * dist * 0.5 / sum_length
            center_x = top_left_ref_corner[0] + (ref_unit_vector[0] * offset_dist_x) - (ref_normal_vector[0] * offset_dist_y)
            center_y = top_left_ref_corner[1] + (ref_unit_vector[1] * offset_dist_x) - (ref_normal_vector[1] * offset_dist_y)
            # convert from standard coordinate back to screen coordinates
            center_y = gray.shape[0] - 1 - center_y

            #recalculate side_length using the distance between the right reference corner and left reference corner
            # evil magic scaling factor 1.007
            side_length = 1.00 * dist * 1.007 / sum_length

        return [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, None, None]
    else:
        return None



def misalignment_handling(clean_detection, clean_img, normalized_gray):
    min_box_area = -1
    min_box = None
    for detection in clean_detection:
        # perfom point adjustment algorithm to the keypoints of the detection
        # find the smallest box with keypoint scanline where the color difference in normalized gray is greater than 0.2
        detection_box = detection['bbox']
        keypoints = detection['keypoints']
        if len(keypoints) >= 2:
            pt_a, pt_b = keypoints[0], keypoints[1]
            pt_a_adj, pt_b_adj = apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
            # Create a mask for the line
            mask = np.zeros_like(normalized_gray, dtype=np.uint8)
            cv2.line(mask, pt_a_adj, pt_b_adj, 255, 4)
            # Get pixel values along the line from normalized_gray
            line_pixels = normalized_gray[mask > 0]
            if len(line_pixels) > 0:
                brightest = np.max(line_pixels)
                darkest = np.min(line_pixels)
                diff = brightest - darkest
                if diff > 0.2:
                    box_area = (detection_box[2] - detection_box[0]) * (detection_box[3] - detection_box[1])
                    if min_box_area == -1 or box_area < min_box_area:
                        min_box_area = box_area
                        min_box = detection_box

    # display the min_box on the image if found
    if min_box is not None:
        img_with_box = clean_img.copy()
        cv2.rectangle(img_with_box, (min_box[0], min_box[1]), (min_box[2], min_box[3]), (0, 255, 255), 2)  # yellow box
        plt.figure("best YOLO Box")
        plt.imshow(cv2.cvtColor(img_with_box, cv2.COLOR_BGR2RGB))
        plt.title("best YOLO Box")
        plt.show()


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





def usaf_point_to_screen(pt, center_x, center_y, angle, side_length):
    """Map USAF coords to test-image screen pixels for scanlines."""
    if C._itk_transform_params is not None and C.PT_TRANSFORM == "elastix":
        x, y = ref_usaf_point_to_target(pt)
        return (int(round(x)), int(round(y)))
    if C._sift_h_matrix is not None and C.PT_TRANSFORM == "sift":
        x, y = usaf2screen_homography(pt, C._sift_h_matrix)
        return (int(round(x)), int(round(y)))
    return usaf2screen_classic(pt, center_x, center_y, angle, side_length)


def score_pattern_crops(image_label="image", crop_dir=Path("pattern_crop")):
    """
    Score saved pattern crops from low to high resolution. Return the last element
    before either vertical or horizontal crop becomes unresolved.
    """
    crop_dir = Path(crop_dir)
    evaluated_crops = []
    last_resolved_result = None
    for scan_index in [idx for idx in sorted(C.score_table.keys()) if idx >= 0]:
        group, element = C.score_table[scan_index]
        vertical_path = find_pattern_crop(crop_dir, image_label, "vertical", scan_index)
        horizontal_path = find_pattern_crop(crop_dir, image_label, "horizontal", scan_index)

        vertical_result = None
        horizontal_result = None
        vertical_img = None
        horizontal_img = None
        if vertical_path is not None:
            vertical_img = cv2.imread(str(vertical_path))
            if vertical_img is not None:
                vertical_result = classify_pattern_resolution(vertical_img)
        if horizontal_path is not None:
            horizontal_img = cv2.imread(str(horizontal_path))
            if horizontal_img is not None:
                horizontal_result = classify_pattern_resolution(horizontal_img)

        evaluated_crops.append(
            {
                "group": group,
                "element": element,
                "vertical_img": vertical_img,
                "horizontal_img": horizontal_img,
                "vertical_result": vertical_result,
                "horizontal_result": horizontal_result,
            }
        )

        if str(vertical_result).lower() == "unresolved" or str(horizontal_result).lower() == "unresolved":
            if C.PATTERN_CLASSIFICATION_SHOW_PLOT:
                show_pattern_classification_results(evaluated_crops)
            if last_resolved_result is not None:
                print(
                    f"Pattern crop classifier best focus: "
                    f"group {['group']}, element {last_resolved_result['element']}"
                )
            else:
                print("Pattern crop classifier found unresolved at first scanned element")
            return last_resolved_result

        if str(vertical_result).lower() == "resolved" and str(horizontal_result).lower() == "resolved":
            last_resolved_result = {
                "group": group,
                "element": element,
                "scan_index": scan_index,
                "vertical_result": vertical_result,
                "horizontal_result": horizontal_result,
                "vertical_path": str(vertical_path) if vertical_path is not None else None,
                "horizontal_path": str(horizontal_path) if horizontal_path is not None else None,
            }

    if last_resolved_result is not None:
        print(
            f"Pattern crop classifier best focus: "
            f"group {last_resolved_result['group']}, element {last_resolved_result['element']}"
        )
    else:
        print("Pattern crop classifier found no resolved pattern")
    if C.PATTERN_CLASSIFICATION_SHOW_PLOT:
        show_pattern_classification_results(evaluated_crops)
    return last_resolved_result


def calculate_focus_scores(curr_image, yolo_detections=None, retry_instance = 0):
    '''
    Calculate the focus scores for each group element based on the defined scanlines and the detected corners for coordinate calibration.
    If YOLO detections are provided, replace scanline endpoints that fall within YOLO bounding boxes with YOLO keypoints.
    
    Args:
        curr_image: BGR image array (same format as cv2.imread)
        yolo_detections: Optional list of YOLO detections with 'bbox' and 'keypoints' keys
    
    Return a ordered dictionary of scores for each group element, where the key is the group element number and the value is the focus score.
    '''
    initial_retry_instance = retry_instance
    if curr_image is None:
        return None
    img = curr_image
    
    clean_img = img.copy()
    clean_detection = yolo_detections.copy() if yolo_detections is not None else None
    # Prepocessing:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Find the brightest pixel
    brightest = np.max(gray)
    # Create normalized image duplicate
    normalized_gray = gray.astype(float) / brightest
    # Ensure values are between 0 and 1 (though division by max should already do this)
    normalized_gray = np.clip(normalized_gray, 0, 1)

    # Find square corners
    corners = find_square_corners(gray)

    # Coordinate calibration
    C.retry_count = 0
    retry_condition = False
    retry_origin = False
    scores = {}

    while C.retry_count < C.valid_squares.__len__():
        scanlines = {}
        scores = {}  # reset scores before retrying
        img = clean_img.copy()
        retry_condition = False

        corners = C.valid_squares[C.retry_count].reshape(-1, 2).copy()
        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        output_list = coordinate_calibration(gray, corners)

        if output_list is None:
            C.retry_count = C.retry_count + 1
            if C.DEBUG_MODE:
                print(f"Retrying coordinate calibration with next best square... Attempt {C.retry_count}")
            continue

        [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner] = output_list



        # get the outer coordinate from the center coordinate
        if C.retry_count == 1 and not retry_origin and C.RETRY_OUTER:
            flip = -1 if C.FLIPED_TARGET else 1
            # convert from usaf coordinate to pixel scale
            center_offset = np.array([-1.009, 7.791]) * side_length
            center_offset = get_rotated_pt(0, 0, center_offset[0] * flip, -center_offset[1], angle)
            center_x = center_x + center_offset[0]
            center_y = center_y + center_offset[1]
            side_length = side_length * 3.918
            retry_origin = True
        else:
            retry_origin = False


        
        yolo_repl = False
        local_min = False
        # Iterate through the dictionary in pairs
        # range(0, len, 2) gives us 0, 2, 4...
        for i in range(0, len(C.group_positions), 2):
            yolo_repl = False
            local_min = False

            # Get the raw usaf coordinates (tuples)
            raw_a = C.group_positions[i]
            raw_b = C.group_positions[i+1]

            # Convert USAF coords to screen coordinates (uses C._sift_h_matrix when SIFT calibration ran)
            pt_a = usaf_point_to_screen(raw_a, center_x, center_y, angle, side_length)
            pt_b = usaf_point_to_screen(raw_b, center_x, center_y, angle, side_length)

            # if the pts fall outside the image, retry with the next best square
            if (pt_a[0] < 0 or pt_a[0] >= gray.shape[1] or pt_a[1] < 0 or pt_a[1] >= gray.shape[0] or \
            pt_b[0] < 0 or pt_b[0] >= gray.shape[1] or pt_b[1] < 0 or pt_b[1] >= gray.shape[0]) and C.RETRY_OFF_IMAGE:
                retry_condition = True
                break

            # point adjustment algorithm:
            # Adjust points until both are white
            pt_a_adj, pt_b_adj = apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
            pt_a, pt_b = pt_a_adj, pt_b_adj

            # ====== YOLO INTEGRATION: Check and replace points if they fall within YOLO bounding boxes ======
            if yolo_detections is not None and len(yolo_detections) > 0 and C.YOLO_DETECT:
                repl_a, repl_b = find_replacement_keypoints(pt_a, pt_b, yolo_detections)
                if repl_a is not None:
                    pt_a, pt_b = apply_point_adjustment_algorithm(repl_a, repl_b, normalized_gray)
                    yolo_repl = True

            scanline_center = (
                (float(pt_a[0]) + float(pt_b[0])) / 2.0,
                (float(pt_a[1]) + float(pt_b[1])) / 2.0,
            )
            scanline_length = np.linalg.norm(np.array(pt_a, dtype=np.float64) - np.array(pt_b, dtype=np.float64))
            scanline_box_half_size = 0.9 * scanline_length
            box_top_left = (
                int(round(scanline_center[0] - scanline_box_half_size)),
                int(round(scanline_center[1] - scanline_box_half_size)),
            )
            box_bottom_right = (
                int(round(scanline_center[0] + scanline_box_half_size)),
                int(round(scanline_center[1] + scanline_box_half_size)),
            )
            cv2.rectangle(img, box_top_left, box_bottom_right, (0, 255, 255), 1)

            crop_x1 = max(0, box_top_left[0])
            crop_y1 = max(0, box_top_left[1])
            crop_x2 = min(clean_img.shape[1], box_bottom_right[0])
            crop_y2 = min(clean_img.shape[0], box_bottom_right[1])
            if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                pattern_crop_dir = Path("pattern_crop")
                pattern_crop_dir.mkdir(exist_ok=True)
                crop_img = clean_img[crop_y1:crop_y2, crop_x1:crop_x2]
                interpolation = cv2.INTER_AREA if crop_img.shape[0] > 256 or crop_img.shape[1] > 256 else cv2.INTER_CUBIC
                crop_img = cv2.resize(crop_img, (256, 256), interpolation=interpolation)
                if i // 2 <= 32:
                    crop_name = f"{C.current_image_label}_horizontal_scan_{i // 2:03d}.png"
                else:
                    crop_name = f"{C.current_image_label}_vertical_scan_{(i // 2) - 33:03d}.png"
                cv2.imwrite(str(pattern_crop_dir / crop_name), crop_img)

            # Create a mask for the line
            mask = np.zeros_like(gray, dtype=np.uint8)
            cv2.line(mask, pt_a, pt_b, 255, 2)
            # Get pixel values along the line from normalized_gray
            line_pixels = normalized_gray[mask > 0]

            if len(line_pixels) > 0:
                p95 = np.percentile(line_pixels, 98)
                p5 = np.percentile(line_pixels, 2)
                score = p95 - p5
            else:
                score = 0



            if C.GRADIENT_MIN:
                pt_a_e, pt_b_e = extend_line(pt_a, pt_b, extend_length=0.2)
                _, line_pixels = sample_line_profile(normalized_gray, pt_a_e, pt_b_e, sample_count=100)
                if len(line_pixels) < 3:
                    local_min_count = 0
                else:
                    smooth_pixels = savgol_filter(line_pixels, window_length=15, polyorder=3)
                    dy = np.gradient(smooth_pixels)
                    # Find where derivative crosses zero from negative to positive
                    is_min = (dy[:-1] < -0.0001) & (dy[1:] > 0.0001)
                    # Convert boolean mask to actual indices of the minima
                    min_indices = np.where(is_min)[0]

                    if len(min_indices) > 1:
                        diffs = np.diff(min_indices)
                        mask = np.concatenate(([True], diffs > 1))
                        filtered_min_indices = min_indices[mask]
                        local_min_count = len(filtered_min_indices)
                    else:
                        filtered_min_indices = min_indices
                        local_min_count = len(min_indices)

                    local_min = local_min_count >= 2

                    if C.GRADIENT_PLOT_ENABLE:
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




            if local_min:
                score_type = "local_min"
            elif yolo_repl:
                score_type = "yolo"
            else:
                score_type = "grid"



            scores[i // 2] = {"score": score, "type": score_type}
            scanlines[i // 2] = {
                "pt_a": [int(pt_a[0]), int(pt_a[1])],
                "pt_b": [int(pt_b[0]), int(pt_b[1])],
                "score": float(score),
                "used_yolo": yolo_repl,
            }

            # Draw the line on the image
            line_color = (0, 0, 255) if not yolo_repl else (255, 0, 255)  # Magenta if replaced by YOLO
            cv2.line(img, pt_a, pt_b, line_color, 2)

        if not retry_condition:
            if retry_instance <= 0:
                break

            if retry_origin == False:
                C.retry_count = C.retry_count + 1
                retry_instance = retry_instance - 1
                continue


        if retry_origin == False:
            C.retry_count = C.retry_count + 1
        
        if C.DEBUG_MODE:
            print(f"Found out image scanline, Retrying with next best square... Attempt {C.retry_count}")

    if C.retry_count == C.valid_squares.__len__():
        if C.DEBUG_MODE:
            print(f"Failed to find valid square after {C.retry_count} attempts")
        scores = {}  # reset scores
        return None, None

    if yolo_detections is not None and len(yolo_detections) > 15:
        misalignment_handling(clean_detection, clean_img.copy(), normalized_gray)

    if initial_retry_instance != 0 and not (0.9 * C.INITIAL_ANGLE < np.abs(angle) < 1.1 * C.INITIAL_ANGLE):
        if C.DEBUG_MODE:
            print("large angles diff quit")
        return None, None


    # squ_scan_pt1 = usaf2screen(squ_scan_coord1, center_x, center_y, angle, side_length)
    # squ_scan_pt2 = usaf2screen(squ_scan_coord2, center_x, center_y, angle, side_length)

    # square detection function
    # _, peak_num, peak_screen_pts, _, _ = scanline_jmp(
    #     normalized_gray, squ_scan_pt1, squ_scan_pt2, sample_count = 500, savgol_window=10, deriv_eps = 0.1
    # )
    # print("The number of square is: ", peak_num)


    if initial_retry_instance == 0:
        pt4_pattern_result = count_4pts_pattern(clean_img)
        C.pattern_count = len(pt4_pattern_result.boxes)
        # show image with annotation
        if C.DEBUG_MODE:
            # 1. Plot the YOLO results (outputs BGR image)
            annotated = pt4_pattern_result.plot(font_size=1, line_width=1)

            # 2. Convert from BGR to RGB exactly ONCE
            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)

            # 3. Display the already-converted image
            plt.figure(figsize=(10, 8))
            plt.imshow(annotated_rgb)  # <-- Fixed: Just pass the RGB image here
            plt.title("Custom Keypoint Visualization")
            plt.axis("off")  
            plt.tight_layout()
            plt.show()

    C.G1 = 8 - C.pattern_count * 2 + C.retry_count * 2
    if C.DEBUG_MODE:
        print("C.G1 is: ", C.G1)
        print("C.pattern_count is: ", C.pattern_count)
        print("C.retry_count is: ", C.retry_count)
    C.initialize_score_table()







    if C.PREVIEW_MODE:
        # Display the result
        # convert the right reference corner and left reference corner from standard to screen coordinates
        top_right_ref_corner = (int(top_right_ref_corner[0]), int(gray.shape[0] - top_right_ref_corner[1] - 1))
        top_left_ref_corner = (int(top_left_ref_corner[0]), int(gray.shape[0] - top_left_ref_corner[1] - 1))
        cv2.circle(img, top_right_ref_corner, 2, (255, 0, 255), -1)  # magenta for right reference corner
        cv2.circle(img, top_left_ref_corner, 2, (255, 255, 0), -1)  # cyan for left reference corner


        if C.FOUR_KP == True:
            low_right_ref_corner = (int(low_right_ref_corner[0]), int(gray.shape[0] - low_right_ref_corner[1] - 1))
            low_left_ref_corner = (int(low_left_ref_corner[0]), int(gray.shape[0] - low_left_ref_corner[1] - 1))
            cv2.circle(img, low_right_ref_corner, 2, (255, 0, 255), -1)  # magenta for right reference corner
            cv2.circle(img, low_left_ref_corner, 2, (255, 255, 0), -1)  # cyan for left reference corner


        # calculate region dimension and draw the region 
        right_region_size_px = int((1.0/5.0) * side_length)
        left_region_size_px = int((1.0/5.0) * side_length)
        # convert the right reference corner and left reference corner from usaf to screen coordinates, then draw the region around them,
        # cast to int for cv2.rectangle
        right_rotated_pt = usaf_point_to_screen(C.top_right_ref_coord, center_x, center_y, angle, side_length)
        left_rotated_pt = usaf_point_to_screen(C.top_left_ref_coord, center_x, center_y, angle, side_length)
        cv2.rectangle(img, (int(right_rotated_pt[0] - right_region_size_px), int(right_rotated_pt[1] - right_region_size_px)),                  (int(right_rotated_pt[0] + right_region_size_px), int(right_rotated_pt[1] + right_region_size_px)), (255, 0, 255), 2)
        cv2.rectangle(img, (int(left_rotated_pt[0] - left_region_size_px), int(left_rotated_pt[1] - left_region_size_px)),                  (int(left_rotated_pt[0] + left_region_size_px), int(left_rotated_pt[1] + left_region_size_px)), (255, 255, 0), 2)
        # cv2.rectangle(img, (int(right_number_pt1[0] - num_box_offset1), int(right_number_pt1[1] - num_box_offset1)),                  (int(right_number_pt1[0] + num_box_offset1), int(right_number_pt1[1] + num_box_offset1)), (0, 255, 255), 2)
        # cv2.rectangle(img, (int(left_number_pt1[0] - num_box_offset1), int(left_number_pt1[1] - num_box_offset1)),                  (int(left_number_pt1[0] + num_box_offset1), int(left_number_pt1[1] + num_box_offset1)), (0, 255, 255), 2)
        # cv2.rectangle(img, (int(right_number_pt2[0] - num_box_offset2), int(right_number_pt2[1] - num_box_offset2)),                  (int(right_number_pt2[0] + num_box_offset2), int(right_number_pt2[1] + num_box_offset2)), (0, 255, 255), 2)
        # cv2.rectangle(img, (int(left_number_pt2[0] - num_box_offset2), int(left_number_pt2[1] - num_box_offset2)),                  (int(left_number_pt2[0] + num_box_offset2), int(left_number_pt2[1] + num_box_offset2)), (0, 255, 255), 2)
        # cv2.rectangle(img, (int(right_number_pt3[0] - num_box_offset3), int(right_number_pt3[1] - num_box_offset3)),                  (int(right_number_pt3[0] + num_box_offset3), int(right_number_pt3[1] + num_box_offset3)), (0, 255, 255), 2)
        # cv2.rectangle(img, (int(left_number_pt3[0] - num_box_offset3), int(left_number_pt3[1] - num_box_offset3)),                  (int(left_number_pt3[0] + num_box_offset3), int(left_number_pt3[1] + num_box_offset3)), (0, 255, 255), 2)
        # cv2.line(img, squ_scan_pt1, squ_scan_pt2, (0, 0, 255), 2)
        # for pt_coordinate in peak_screen_pts:
        #      cv2.circle(img, (int(pt_coordinate[0]), int(pt_coordinate[1])), 8, (255, 0, 0), -1)

        # mark the center of the square with a blue circle
        cv2.circle(img, (int(center_x), int(center_y)), 8, (255, 0, 0), -1)  # blue for center of the square
        
        plt.figure("Preview Scanlines", figsize=(8, 8))
        plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        plt.title("Preview Scanlines")
        plt.show()







    final_score = {}
    scanline_map = {}
    for i in range(len(scores) // 2):
        vert_score = abs(scores[i]["score"])
        horiz_score = abs(scores[i + len(scores) // 2]["score"])

        if scores[i]["type"] == "local_min" or scores[i + len(scores) // 2]["type"] == "local_min":
            temp_type = "local_min"
        elif scores[i]["type"] == "yolo" or scores[i + len(scores) // 2]["type"] == "yolo":
            temp_type = "yolo"
        else:
            temp_type = "grid"
        
        if C.SCORE_METHOD == "mean":
            temp_score = (vert_score + horiz_score) / 2.0
        elif C.SCORE_METHOD == "max":
            temp_score = max(vert_score, horiz_score)
        elif C.SCORE_METHOD == "min":
            temp_score = min(vert_score, horiz_score)
        else:
            temp_score = vert_score
        
        final_score[i] = {"score": float(temp_score), "type": temp_type}

        group, element = C.score_table[i]
        scanline_map[f"{group}:{element}"] = {
            "group": group,
            "element": element,
            "vertical": scanlines[i],
            "horizontal": scanlines[i + len(scores) // 2],
            "score": float(temp_score),
            "type": temp_type,
            "lp_per_mm": usaf_lp_per_mm(group, element),
            "resolution_mm": usaf_resolution_mm(group, element),
        }

        if retry_instance == 0:
            C.INITIAL_ANGLE = np.abs(angle)

    return final_score, scanline_map





def find_best_focus_group(scores_list, threshold=0.3):
    '''
    Find the index in the scores where the descending order of scores changes to ascending order,
    or where the score drops below a certain threshold (e.g., 0.2), which indicates the best focus group.
    Return the corresponding group and element number from the score table.
    '''
    # We need at least 2 scores to compare
    if scores_list is None:
        return None, None
    chosen_index = 0
    if len(scores_list) < 2:
        print("Not enough scores to compare")
        return C.score_table[chosen_index], chosen_index

    last_yolo_index = 1
    for i in range(0, len(scores_list)): 
        if scores_list[i]["score"] > threshold and scores_list[i]["type"] == "yolo":
            last_yolo_index = i + 1

    last_local_min_index = 1
    for i in range(0, len(scores_list)):
        if scores_list[i]["score"] > threshold and scores_list[i]["type"] == "local_min":
            last_local_min_index = i + 1

    last_index = max(last_yolo_index, last_local_min_index)

    if last_index == len(scores_list):
        print("all resolved")
        chosen_index = len(C.score_table) - 1
        return C.score_table[chosen_index], chosen_index
    
    for i in range(last_index, len(scores_list)):
        if C.FOCUS_GROUP_LAST_ABOVE_THRESHOLD:
            if scores_list[i]["score"] > threshold:
                chosen_index = min(i, len(C.score_table) - 1)
        elif scores_list[i]["score"] > scores_list[i - 1]["score"] * 1.5 or scores_list[i]["score"] < threshold:
            # If the score starts going UP, the previous index was the "bottom"
            chosen_index = min(i - 1, len(C.score_table) - 1)
            return C.score_table[chosen_index], chosen_index

    if C.FOCUS_GROUP_LAST_ABOVE_THRESHOLD:
        return C.score_table[chosen_index], chosen_index

    # If it never goes up, return first element
    print("No score goes up")
    chosen_index = len(C.score_table) - 1
    return C.score_table[chosen_index], chosen_index



def find_usaf_score(image_path, imgsz=2048, threshold=0.3):
    '''
    Find the usaf focus score for a given image path, which is the best focus group number 
    based on the defined scanlines and the detected corners for coordinate calibration.
    
    Args:
        image_path: Path to the image
        imgsz: Image size for YOLO inference
    
    Returns:
        Tuple of (group_number, element_number) indicating best focus group
    '''
    C.current_image_label = Path(image_path).stem
    curr_image = cv2.imread(image_path)
    if curr_image is None:
        return None

    if not is_image_clear(curr_image, 2):
        print("The image is too blurry for detection")
        return None
    
    while True:
        yolo_detections = None
        if C.YOLO_DETECT:
            yolo_detections, _result, _img = extract_yolo_detections(curr_image, imgsz=imgsz)
        if C.PREVIEW_MODE and C.YOLO_DETECT:
            visualize_detections(_img, _result, yolo_detections)
        # Calculate focus scores
        scores = {}
        scanline_map = {}
        best_focus_group = {}
        chosen_index = {}
        run_indices = [0] if C.USE_SIFT_REF_CALIBRATION else [0, 1, 2]
        try:
            for idx in run_indices:
                scores[idx], scanline_map[idx] = calculate_focus_scores(curr_image, yolo_detections, idx)
                
                if C.YOLO_CLASSIFICATION:
                    pattern_crop_result = score_pattern_crops(C.current_image_label)
                    best_focus_group[idx] = [pattern_crop_result["group"], pattern_crop_result["element"]]
                    chosen_index[idx] = pattern_crop_result["scan_index"]
                else:
                    best_focus_group[idx], chosen_index[idx] = find_best_focus_group(scores[idx], threshold=threshold)
                
                if C.DEBUG_MODE:
                    print(f"scores[{idx}]", scores[idx])
                    print(f"best_focus_group[{idx}]", best_focus_group[idx])
            break
        except ValueError:
            # rotate current image by 30 degrees and fill background with black
            (h, w) = curr_image.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, -30, 1.0)

            cos = np.abs(matrix[0, 0])
            sin = np.abs(matrix[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            matrix[0, 2] += (new_w / 2) - center[0]
            matrix[1, 2] += (new_h / 2) - center[1]

            curr_image = cv2.warpAffine(curr_image, matrix, (new_w, new_h))

        except Exception as e:
            print(f"Failed to calculate focus scores for {image_path}: {e}")
            return None
    
    # Keep only valid focus group entries (some attempts can return None).
    best_focus_info = []
    for i in run_indices:
        group = best_focus_group[i]
        if group is None:
            continue
        if not isinstance(group, (list, tuple)) or len(group) < 2:
            continue
        best_focus_info.append([group, chosen_index[i], scanline_map[i], scores[i]])
        if C.DEBUG_MODE:
            print("candidate best focus group", group)

    if not best_focus_info:
        print("No best focus group found")
        return None

    # Winner: highest group number, then highest element number.
    final_best_focus_info = max(best_focus_info, key=lambda x: (x[0][0], x[0][1]))

    if final_best_focus_info[3] is not None and C.DEBUG_MODE:
        print(f"Scores for {image_path}: {final_best_focus_info[3]}")

    print(f"Best focus group for {image_path}: {final_best_focus_info[0][0]}, element {final_best_focus_info[0][1]}")

    C.G1 = 2
    C.initialize_score_table()

    # Return legacy outputs plus processed image used during scoring.
    return final_best_focus_info[0], final_best_focus_info[1], final_best_focus_info[2], final_best_focus_info[3], curr_image


for image_path in C.images:
    find_usaf_score(image_path)

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from .yolo_model import extract_yolo_detections, visualize_detections, count_4pts_pattern, yolo_4pt_calculation
from scipy.signal import savgol_filter
import shutil
import os
from . import constants as C
from .sift_warp import get_sift_reference_image, sift_homography_with_origin, _sift_ref_origin_for_target
from .classic_warp import find_white_corner_in_region, find_target_orientation, get_adjusted_top_corners_from_enclosing_rectangle, find_square_corners
from .elastix_warp import setup_itkelastix_ref_mapping, ref_usaf_point_to_target, fast_ref_usaf_point_to_target
from .pt_adjust import apply_point_adjustment_algorithm, find_replacement_keypoints, extend_line
from .transforms import usaf2screen_homography, usaf2screen_classic, get_rotated_pt
from .pattern_crop import verify_pattern_crops, scanline_region_cropping
from .helper import sample_line_profile, is_image_clear, normalize_image_contrast, gradient_visualization, usaf_lp_per_mm, usaf_resolution_mm
from .scoring import find_best_focus_group, score_pattern_crops


#------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Coordinate Definitions:
# usaf coordinate system: origin is the center of the square in usaf target, axis align with edge of square and 1.0 unit = side length of the square
#                         negative y axis point toward center of the target, and positive x axis point toward the group with higher group number
# standard coordinate system: origin at the bottom left corner of the image, positive y axis point upward, positive x axis point rightward, unit in pixel
# screen coordinate system: origin at the top left corner of the image, positive y axis point downward, positive x axis point rightward, unit in pixel
#------------------------------------------------------------------------------------------------------------------------------------------------------------------






def map_ref_corners_classic(orientation, gray, center_x, center_y, angle, side_length):
    #Seconary coordinate calibration using the reference corners
    # left and right ref corner are in standard coordinates 
    TL_dir = C.prefer_dir_table[orientation][0]
    TR_dir = C.prefer_dir_table[orientation][1]
    BL_dir = C.prefer_dir_table[orientation][2]
    BR_dir = C.prefer_dir_table[orientation][3]
    if C.FLIPED_TARGET:
        TR_dir, TL_dir = TL_dir, TR_dir
        BR_dir, BL_dir = BL_dir, BR_dir

    # --------------------------------------------------------------------------------------------
    # Classic corner calculation
    # --------------------------------------------------------------------------------------------

    top_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_right_ref_coord, 1.0/5.0, TL_dir)
    top_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_left_ref_coord, 1.0/5.0, TR_dir)
    low_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_right_ref_coord, 1.0/5.0, BL_dir)
    low_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_left_ref_coord, 1.0/5.0, BR_dir)

    return top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner






def map_ref_corners_sift(orientation, gray, center_x, center_y, angle, side_length):
    sift_angle = 0
    sift_length = 0

    ref_image_sift = get_sift_reference_image()
    if ref_image_sift is None:
        if C.DEBUG_MODE:
            print(f"Failed to load SIFT reference image: {C.SIFT_REF_IMAGE_PATH}")
        raise RuntimeError(f"usaf_algo.coordinate_calibration: Failed to load SIFT reference image: {C.SIFT_REF_IMAGE_PATH}")
    if C.FLIPED_TARGET:
        # Mirror the reference image to match flipped target orientation.
        ref_image_sift = cv2.flip(ref_image_sift, 1)
    sift_origin = _sift_ref_origin_for_target()

    # --------------------------------------------------------------------------------------------
    # SIFT Homography
    # --------------------------------------------------------------------------------------------

    C._sift_h_matrix, _ = sift_homography_with_origin(
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

    # --------------------------------------------------------------------------------------------
    # ITKElastix mapping
    # --------------------------------------------------------------------------------------------

    if C.USE_ITKELASTIX_REF_CALIBRATION:
        try:
            setup_itkelastix_ref_mapping(ref_image_sift, gray, C._sift_h_matrix)
        except Exception as e:
            C._itk_transform_params = None
            C._itk_moving_image = None
            C._itk_output_dir = None
            C._itk_roi_offset = (0, 0)
            C._itk_point_cache = {}
            print(f"ITKElastix mapping failed; using SIFT only: {e}")

    # --------------------------------------------------------------------------------------------
    # Reference corner calculation
    # --------------------------------------------------------------------------------------------

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
        mapped = cv2.perspectiveTransform(ref_pts_local, C._sift_h_matrix).reshape(-1, 2)
    
    # calculatel angle relative to +ive horizontal (-pi, pi)
    sift_ref_vector = mapped[0] - mapped[2]
    sift_ref_unit_vector = sift_ref_vector / np.linalg.norm(sift_ref_vector)
    sift_angle = np.arctan2(sift_ref_unit_vector[1], sift_ref_unit_vector[0])
    sift_length = np.linalg.norm(sift_ref_vector)
    if C.DEBUG_MODE:
        print(f"SIFT reference vector: {sift_ref_vector}, angle: {sift_angle}, length: {sift_length}")

    # --------------------------------------------------------------------------------------------
    # Convention conversion and Visualization
    # --------------------------------------------------------------------------------------------

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

    return top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner

















































def grid_calculation(top_right_ref_corner, top_left_ref_corner, orientation, gray):
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
    
    return center_x, center_y, angle, side_length








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



    # --------------------------------------------------------------------------------------------
    # Classic calibration precalculation
    # --------------------------------------------------------------------------------------------
    


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
    #find angle of unit vector with +x axis, negate because the screen coordinate system is flipped
    angle = -np.arctan2(unit_vector[1], unit_vector[0])

    # if 0.9 * np.pi / 2 < np.abs(angle) or 0.1 * np.pi / 2 > np.abs(angle):
        # raise ValueError("usaf_algo.coordinate_calibration: Angle too small or large, retrying with rotation...")

    # find orientation of the target
    orientation = find_target_orientation(gray, center_x, center_y, unit_vector, side_length)
    angle = angle + orientation * np.pi / 2



    # --------------------------------------------------------------------------------------------
    # Calibration Corner Detection
    # --------------------------------------------------------------------------------------------

    sift_angle = None
    classic_angle = None
    sift_length = None

    top_right_ref_corner = None
    top_left_ref_corner = None
    low_right_ref_corner = None
    low_left_ref_corner = None

    if not C.USE_SIFT_REF_CALIBRATION or C.PT_TRANSFORM == "auto":
        top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner = map_ref_corners_classic(
            orientation, gray, center_x, center_y, angle, side_length
        )
    if top_right_ref_corner is not None and top_left_ref_corner is not None and C.PT_TRANSFORM == "auto":
        _, _, classic_angle, _ = grid_calculation(top_right_ref_corner, top_left_ref_corner, orientation, gray)
        if C.DEBUG_MODE:
            print("Classic angle(from grid_calculation):", classic_angle)
    
    if C.USE_SIFT_REF_CALIBRATION or C.PT_TRANSFORM == "auto":
        top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner = map_ref_corners_sift(
            orientation, gray, center_x, center_y, angle, side_length
        )
    if top_right_ref_corner is not None and top_left_ref_corner is not None and C.PT_TRANSFORM == "auto":
        _, _, sift_angle, sift_length = grid_calculation(top_right_ref_corner, top_left_ref_corner, orientation, gray)
        pt1 = np.array(C.top_right_ref_coord)
        pt2 = np.array(C.low_right_ref_coord)
        sift_length = np.linalg.norm(pt1 - pt2) * sift_length
        if C.DEBUG_MODE:
            print("SIFT angle(from grid_calculation):", sift_angle)
            print("SIFT length(from grid_calculation):", sift_length)

    # --------------------------------------------------------------------------------------------
    # Calculate grid from corners
    # --------------------------------------------------------------------------------------------

    if top_right_ref_corner is not None and top_left_ref_corner is not None and low_right_ref_corner is not None and low_left_ref_corner is not None and C.FOUR_KP == True:
        adjusted_top_right, adjusted_top_left = get_adjusted_top_corners_from_enclosing_rectangle(
            top_right_ref_corner,
            top_left_ref_corner,
            low_right_ref_corner,
            low_left_ref_corner,
        )
        center_x, center_y, angle, side_length = grid_calculation(adjusted_top_right, adjusted_top_left, orientation, gray)
        return [center_x, center_y, angle, side_length, adjusted_top_right, adjusted_top_left, low_right_ref_corner, low_left_ref_corner, classic_angle, sift_angle, sift_length]
    elif top_right_ref_corner is not None and top_left_ref_corner is not None and C.FOUR_KP == False:
        center_x, center_y, angle, side_length = grid_calculation(top_right_ref_corner, top_left_ref_corner, orientation, gray)
        return [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, None, None, classic_angle, sift_angle, sift_length]
    elif (top_right_ref_corner is None or top_left_ref_corner is None) and C.PT_TRANSFORM == "auto":
        if C.DEBUG_MODE:
            print("No valid sift reference corners found for PT_TRANSFORM='auto'")
        return [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, None, None, classic_angle, sift_angle, sift_length]
    else:
        return None




def usaf_point_to_screen(pt, center_x, center_y, angle, side_length):
    """Map USAF coords to test-image screen pixels for scanlines."""
    if C._itk_transform_params is not None and C.PT_TRANSFORM == "elastix":
        x, y = ref_usaf_point_to_target(pt)
        return (int(round(x)), int(round(y)))
    if C._sift_h_matrix is not None and C.PT_TRANSFORM == "sift":
        x, y = usaf2screen_homography(pt, C._sift_h_matrix)
        return (int(round(x)), int(round(y)))
    return usaf2screen_classic(pt, center_x, center_y, angle, side_length)




def scanline_visualization(img, gray, center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner=None, low_left_ref_corner=None):
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

    # mark the center of the square with a blue circle
    cv2.circle(img, (int(center_x), int(center_y)), 8, (255, 0, 0), -1)  # blue for center of the square
    
    plt.figure("Preview Scanlines", figsize=(8, 8))
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title("Preview Scanlines")
    plt.show()





def calculate_scanline_contrast_scores(curr_image, yolo_detections=None, retry_instance = 0):
    '''
    Calculate the scanline contrast scores for each group element based on the defined scanlines and the detected corners for coordinate calibration.
    If YOLO detections are provided, replace scanline endpoints that fall within YOLO bounding boxes with YOLO keypoints.
    
    Args:
        curr_image: BGR image array (same format as cv2.imread)
        yolo_detections: Optional list of YOLO detections with 'bbox' and 'keypoints' keys
    
    Return a ordered dictionary of scores for each group element, where the key is the group element number and the value is the focus score.
    '''
    initial_retry_instance = retry_instance
    if curr_image is None:
        raise ValueError("usaf_algo.calculate_scanline_contrast_scores: Input image is None.")
    img = curr_image
    


    # --------------------------------------------------------------------------------------------
    # Preprocessing and SIFT config
    # --------------------------------------------------------------------------------------------



    clean_img = img.copy()
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

    if initial_retry_instance == 0:
        pt4_pattern_result = count_4pts_pattern(clean_img)
        C.pattern_count = len(pt4_pattern_result.boxes)
        parsed, yolo_angles, yolo_box_lengths, yolo_dir = yolo_4pt_calculation(pt4_pattern_result, clean_img)

        # show image with annotation
        if C.DEBUG_MODE:
            print(f"YOLO detected {C.pattern_count} patterns. Parsed results: {parsed}")
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

    if C.USE_SIFT_REF_CALIBRATION:
        sift_config_index = max(min(C.pattern_count - 1, 2), 0)
        C.SIFT_REF_IMAGE_PATH = C.SIFT_CONFIG_LIST[sift_config_index]["REF_IMAGE_PATH"]
        C.SIFT_REF_ORIGIN = C.SIFT_CONFIG_LIST[sift_config_index]["REF_ORIGIN"]  
        C.SIFT_REF_PIXELS_PER_UNIT_X = C.SIFT_CONFIG_LIST[sift_config_index]["REF_PIXELS_PER_UNIT_X"]  
        C.SIFT_REF_PIXELS_PER_UNIT_Y = C.SIFT_CONFIG_LIST[sift_config_index]["REF_PIXELS_PER_UNIT_Y"]  
        C.SIFT_ANGLE = C.SIFT_CONFIG_LIST[sift_config_index]["ANGLE"]



    # --------------------------------------------------------------------------------------------
    # Main retry loop for coordinate calibration and scoring
    # --------------------------------------------------------------------------------------------



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


        # --------------------------------------------------------------------------------------------
        # Coordinate calibration
        # --------------------------------------------------------------------------------------------


        corners = C.valid_squares[C.retry_count].reshape(-1, 2).copy()
        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        output_list = coordinate_calibration(gray, corners)

        if output_list is None:
            C.retry_count = C.retry_count + 1
            if C.DEBUG_MODE:
                print(f"Retrying coordinate calibration with next best square... Attempt {C.retry_count}")
            continue

        [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner, classic_angle, sift_angle, sift_length] = output_list


        # --------------------------------------------------------------------------------------------
        # Retry Outer Logic
        # --------------------------------------------------------------------------------------------


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


        # --------------------------------------------------------------------------------------------
        # Scanline calculation and scoring
        # --------------------------------------------------------------------------------------------
        
        if C._itk_transform_params is not None and C.PT_TRANSFORM == "elastix":
            mapped_scanlines = fast_ref_usaf_point_to_target(C.group_positions.values(), n_workers=4)

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
            if C._itk_transform_params is not None and C.PT_TRANSFORM == "elastix":
                pt_a = mapped_scanlines[i]
                pt_b = mapped_scanlines[i+1]
            else:
                pt_a = usaf_point_to_screen(raw_a, center_x, center_y, angle, side_length)
                pt_b = usaf_point_to_screen(raw_b, center_x, center_y, angle, side_length)

            # if the pts fall outside the image, retry with the next best square
            if (pt_a[0] < 0 or pt_a[0] >= gray.shape[1] or pt_a[1] < 0 or pt_a[1] >= gray.shape[0] or \
            pt_b[0] < 0 or pt_b[0] >= gray.shape[1] or pt_b[1] < 0 or pt_b[1] >= gray.shape[0]) and C.RETRY_OFF_IMAGE:
                retry_condition = True
                break

            # --------------------------------------------------------------------------------------------
            # Scanline adjustment and replacement
            # --------------------------------------------------------------------------------------------

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

            # --------------------------------------------------------------------------------------------
            # Scanline region cropping for pattern classification
            # --------------------------------------------------------------------------------------------

            scanline_region_cropping(img, clean_img, pt_a, pt_b, i)

            # --------------------------------------------------------------------------------------------
            # Contrast scoring
            # --------------------------------------------------------------------------------------------

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

            # --------------------------------------------------------------------------------------------
            # Gradient logic
            # --------------------------------------------------------------------------------------------

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

                    # visualize gradient
                    if C.GRADIENT_PLOT_ENABLE:
                        gradient_visualization(i, smooth_pixels, filtered_min_indices, local_min_count, dy)

            # --------------------------------------------------------------------------------------------
            # Score processing and visualization
            # --------------------------------------------------------------------------------------------

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


        # --------------------------------------------------------------------------------------------
        # Retry Logic after scanline processing
        # --------------------------------------------------------------------------------------------


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



    # --------------------------------------------------------------------------------------------
    # Exception and Abort handling
    # --------------------------------------------------------------------------------------------



    if C.retry_count == C.valid_squares.__len__():
        if C.DEBUG_MODE:
            print(f"Failed to find valid square after {C.retry_count} attempts")
        scores = {}  # reset scores
        # return none and program will handle it
        return None, None

    if yolo_detections is not None and len(yolo_detections) > 15:
        if C.DEBUG_MODE:
            print("grid misalignment detected")
        # return none and program will handle it
        return None, None

    if initial_retry_instance != 0 and not (0.9 * C.initial_angle < np.abs(angle) < 1.1 * C.initial_angle):
        if C.DEBUG_MODE:
            print("large angles diff quit")
        # return none and program will handle it
        return None, None



    # --------------------------------------------------------------------------------------------
    # Dynamic G1 calculation and pattern counting for scoring
    # --------------------------------------------------------------------------------------------



    C.G1 = 8 - C.pattern_count * 2 + min(C.retry_count, 2) * 2
    if C.DEBUG_MODE:
        print("C.G1 is: ", C.G1)
        print("C.pattern_count is: ", C.pattern_count)
        print("C.retry_count is: ", C.retry_count)
    C.initialize_score_table()



    # --------------------------------------------------------------------------------------------
    # Visualization
    # --------------------------------------------------------------------------------------------



    if C.PREVIEW_MODE:
        scanline_visualization(img, gray, center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner)



    # --------------------------------------------------------------------------------------------
    # Data Bundling
    # --------------------------------------------------------------------------------------------



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
            C.initial_angle = np.abs(angle)

    return final_score, scanline_map





def find_usaf_score(image_path, imgsz=2048, threshold=0.3):
    '''
    Find the usaf focus score for a given image path, which is the best focus group number 
    based on the defined scanlines and the detected corners for coordinate calibration.

    handles retry if the angle was two small 
    
    Args:
        image_path: Path to the image
        imgsz: Image size for YOLO inference
    
    Returns:
        Tuple of (group_number, element_number) indicating best focus group
    '''
    C.current_image_label = Path(image_path).stem
    if C.CONST_LABEL:
        C.current_image_label = "image"
    curr_image = cv2.imread(image_path)
    if curr_image is None:
        raise ValueError(f"usaf_algo.find_usaf_score: Failed to read image from {image_path}")

    curr_image = normalize_image_contrast(curr_image)
    curr_image = np.clip(curr_image, 0, 255).astype(np.uint8)

    if not is_image_clear(curr_image, 2.0):
        raise ValueError("usaf_algo.find_usaf_score: The image is too blurry for detection")
    
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
        run_indices = [0] if C.USE_SIFT_REF_CALIBRATION or C.YOLO_DETECT else [0, 1, 2]
        try:
            for idx in run_indices:
                scores[idx], scanline_map[idx] = calculate_scanline_contrast_scores(curr_image, yolo_detections, idx)
                
                if C.YOLO_CLASSIFICATION:
                    pattern_crop_result = score_pattern_crops(C.current_image_label)
                    if C.ENABLE_VERIFY_PATTERN_CROP:
                        pattern_crop_result = verify_pattern_crops(pattern_crop_result)
                    best_focus_group[idx] = [pattern_crop_result["group"], pattern_crop_result["element"]]
                    chosen_index[idx] = pattern_crop_result["scan_index"]
                else:
                    best_focus_group[idx], chosen_index[idx] = find_best_focus_group(scores[idx], threshold=threshold)
                
                if C.DEBUG_MODE and scores[idx] is not None and best_focus_group[idx] is not None:
                    print(f"scores[{idx}]", scores[idx])
                    print(f"best_focus_group[{idx}]", best_focus_group[idx])
            break
        except ValueError as e:
            if "Angle too small or large" in str(e):
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
            else:
                raise e
    
    # Keep only valid focus group entries (some attempts can return None).
    best_focus_info = []
    for i in run_indices:
        group = best_focus_group[i]
        if group is None or chosen_index is None or scanline_map is None or scores is None:
            continue
        if not isinstance(group, (list, tuple)) or len(group) < 2:
            continue
        best_focus_info.append([group, chosen_index[i], scanline_map[i], scores[i]])
        if C.DEBUG_MODE:
            print("candidate best focus group", group)

    if not best_focus_info:
        print("No best focus group found")
        raise ValueError("usaf_algo.find_usaf_score: No best focus group found after all attempts")

    # Winner: highest group number, then highest element number.
    final_best_focus_info = max(best_focus_info, key=lambda x: (x[0][0], x[0][1]))

    if final_best_focus_info[3] is not None and C.DEBUG_MODE:
        print(f"Scores array for the best focus group in {image_path}: {final_best_focus_info[3]}")

    print(f"Best focus group for {image_path}: {final_best_focus_info[0][0]}, element {final_best_focus_info[0][1]}")

    # final clean up
    clean_up()

    # Return legacy outputs plus processed image used during scoring.
    return final_best_focus_info[0], final_best_focus_info[1], final_best_focus_info[2], final_best_focus_info[3], curr_image











def find_dominant_angle_window_center(classic_angle=None, sift_angle=None, yolo_angles=None, window_size_deg=30.0, step_deg=1.0):
    """
    Slide a circular window over [0, 360) and find the window position that contains
    the most candidate angles. Returns the middle angle of the best center range.
    """
    def _norm_deg(val):
        return float(val) % 360.0

    def _circ_dist_deg(a, b):
        # Minimal angular distance on a circle in degrees.
        return abs(((a - b + 180.0) % 360.0) - 180.0)

    candidates = []
    if classic_angle is not None:
        candidates.append(_norm_deg(classic_angle))
    if sift_angle is not None:
        candidates.append(_norm_deg(sift_angle))
    if yolo_angles is not None:
        candidates.extend(_norm_deg(a) for a in yolo_angles if a is not None)

    if len(candidates) == 0:
        return None

    if step_deg <= 0:
        raise ValueError("usaf_algo.find_dominant_angle_window_center: step_deg must be > 0")
    if window_size_deg <= 0:
        raise ValueError("usaf_algo.find_dominant_angle_window_center: window_size_deg must be > 0")

    centers = np.arange(0.0, 360.0, step_deg, dtype=np.float64)
    half_window = window_size_deg * 0.5

    counts = []
    total_dist = []
    for center in centers:
        in_window = [a for a in candidates if _circ_dist_deg(a, center) <= half_window + 1e-9]
        counts.append(len(in_window))
        # Tie-breaker: tighter cluster wins for same count.
        total_dist.append(sum(_circ_dist_deg(a, center) for a in in_window))

    counts = np.array(counts, dtype=np.int32)
    total_dist = np.array(total_dist, dtype=np.float64)
    max_count = int(np.max(counts))
    best_idxs = np.where(counts == max_count)[0]

    # If all best indices are isolated/fragmented, choose the one with lowest spread.
    best_idx = min(best_idxs.tolist(), key=lambda i: (total_dist[i], i))

    return _norm_deg(centers[best_idx])


def angle_to_dominant_bucket_index(angle_deg, dominant_angle_deg, bucket_size_deg=30.0):
    """
    Map an angle to one of 12 buckets on [0, 360), where bucket 0 is centered at
    dominant_angle_deg and bucket index increases counter-clockwise.
    """
    if angle_deg is None or dominant_angle_deg is None:
        return None
    if bucket_size_deg <= 0:
        raise ValueError("usaf_algo.angle_to_dominant_bucket_index: bucket_size_deg must be > 0")

    angle_deg = float(angle_deg) % 360.0
    dominant_angle_deg = float(dominant_angle_deg) % 360.0
    half_bucket = bucket_size_deg * 0.5

    shifted = (angle_deg - dominant_angle_deg + half_bucket) % 360.0
    bucket_idx = int(np.floor(shifted / bucket_size_deg)) % int(round(360.0 / bucket_size_deg))
    return bucket_idx


def bucketize_angles_around_dominant(dominant_angle, yolo_angles=None, classic_angle=None, sift_angle=None):
    """
    Return bucket index lists for yolo, classic, and sift angles using 12 dominant-
    centered buckets of size 30 degrees.
    """
    yolo_bucket_indices = []
    classic_bucket_indices = []
    sift_bucket_indices = []

    if dominant_angle is None:
        return yolo_bucket_indices, classic_bucket_indices, sift_bucket_indices

    if yolo_angles is not None:
        yolo_bucket_indices = [
            angle_to_dominant_bucket_index(a, dominant_angle, bucket_size_deg=30.0)
            for a in yolo_angles
            if a is not None
        ]

    if classic_angle is not None:
        classic_bucket_indices = [
            angle_to_dominant_bucket_index(classic_angle, dominant_angle, bucket_size_deg=30.0)
        ]

    if sift_angle is not None:
        sift_bucket_indices = [
            angle_to_dominant_bucket_index(sift_angle, dominant_angle, bucket_size_deg=30.0)
        ]

    return yolo_bucket_indices, classic_bucket_indices, sift_bucket_indices







def auto_configurator(image_path, imgsz=2048, threshold=0.3):
    final_config = None
    curr_image = cv2.imread(image_path)
    if curr_image is None:
        raise ValueError(f"usaf_algo.auto_configurator: Failed to read image from {image_path}")

    curr_image = normalize_image_contrast(curr_image)
    curr_image = np.clip(curr_image, 0, 255).astype(np.uint8)

    if not is_image_clear(curr_image, 2.0):
        raise ValueError("usaf_algo.auto_configurator: The image is too blurry for detection")

    # --------------------------------------------------------------------------------------------
    # Preprocessing and SIFT config
    # --------------------------------------------------------------------------------------------

    # Prepocessing:
    clean_img = curr_image.copy()
    gray = cv2.cvtColor(curr_image, cv2.COLOR_BGR2GRAY)
    corners = find_square_corners(gray)

    pt4_pattern_result = count_4pts_pattern(clean_img)
    C.pattern_count = len(pt4_pattern_result.boxes)
    parsed, yolo_angles, yolo_box_lengths, yolo_dir = yolo_4pt_calculation(pt4_pattern_result, clean_img)

    # show image with annotation
    if C.DEBUG_MODE:
        print(f"YOLO detected {C.pattern_count} patterns. Parsed results: {parsed}")
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

    sift_config_index = max(min(C.pattern_count - 1, 2), 0)

    # --------------------------------------------------------------------------------------------
    # Coordinate calibration
    # --------------------------------------------------------------------------------------------

    while True:
        C.SIFT_REF_IMAGE_PATH = C.SIFT_CONFIG_LIST[sift_config_index]["REF_IMAGE_PATH"]
        C.SIFT_REF_ORIGIN = C.SIFT_CONFIG_LIST[sift_config_index]["REF_ORIGIN"]  
        C.SIFT_REF_PIXELS_PER_UNIT_X = C.SIFT_CONFIG_LIST[sift_config_index]["REF_PIXELS_PER_UNIT_X"]  
        C.SIFT_REF_PIXELS_PER_UNIT_Y = C.SIFT_CONFIG_LIST[sift_config_index]["REF_PIXELS_PER_UNIT_Y"]  
        C.SIFT_ANGLE = C.SIFT_CONFIG_LIST[sift_config_index]["ANGLE"]
        corners = C.valid_squares[0].reshape(-1, 2).copy()
        corners[:, 1] = clean_img.shape[0] - corners[:, 1] - 1
        output_list = coordinate_calibration(gray, corners)

        if output_list is None:
            raise ValueError("usaf_algo.auto_configurator: Coordinate calibration failed.")

        [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner, classic_angle, sift_angle, sift_length] = output_list

        fliped = -1 if C.FLIPED_TARGET else 1
        classic_angle = classic_angle + fliped * np.pi / 2 if classic_angle is not None else None
        sift_angle = sift_angle + fliped * np.pi / 2 if sift_angle is not None else None
        if C.DEBUG_MODE:
            print("Classic angle(adjusted):", classic_angle)
            print("SIFT angle(adjusted):", sift_angle)
            print("SIFT length(adjusted):", sift_length)
    
        if len(yolo_box_lengths) == 3 and sift_config_index == 2 and sift_length is not None and (yolo_box_lengths[2] * 1.1 < sift_length < yolo_box_lengths[1] * 1.1):
            if C.DEBUG_MODE:
                print("SIFT and YOLO length mismatch detected, retrying with diff sift config...")
    
            sift_config_index = 3
            continue
        
        # convert the angles from radian to -180 - 180 degrees to 0 - 360 degrees
        classic_angle = ((classic_angle / np.pi * 180) + 360) % 360 if classic_angle is not None else None
        sift_angle = ((sift_angle / np.pi * 180) + 360) % 360 if sift_angle is not None else None
        yolo_angles = [((angle / np.pi * 180) + 360) % 360 for angle in yolo_angles] if yolo_angles is not None else None

        if (classic_angle is None or yolo_angles is None) and sift_angle is not None:
            return "classic with sift", C.FLIPED_TARGET, sift_config_index
        elif sift_angle is None and classic_angle is not None:
            return "classic", C.FLIPED_TARGET, sift_config_index
        elif sift_angle is None and classic_angle is None and final_config is None:
            if C.retry_flag == False:
                final_config = "retry"
                C.FLIPED_TARGET = not C.FLIPED_TARGET
                sift_config_index = 2
                continue
            else:
                return "classic with sift", C.FLIPED_TARGET, sift_config_index
        elif sift_angle is None and classic_angle is None:
            return "classic with sift", C.FLIPED_TARGET, sift_config_index



        case_num = len(yolo_angles) if yolo_angles is not None else 0
        type_num = None

        dominant_angle = find_dominant_angle_window_center(
            classic_angle=classic_angle,
            sift_angle=sift_angle,
            yolo_angles=yolo_angles,
            window_size_deg=30.0,
            step_deg=1.0,
        )

        yolo_bucket_indices, classic_bucket_indices, sift_bucket_indices = bucketize_angles_around_dominant(
            dominant_angle=dominant_angle,
            yolo_angles=yolo_angles,
            classic_angle=classic_angle,
            sift_angle=sift_angle,
        )

        if case_num == 1:
            type_num = 1
        elif case_num == 2 and yolo_bucket_indices is not None:
            if yolo_bucket_indices[0] == yolo_bucket_indices[1]:
                type_num = 1
            elif yolo_bucket_indices[0] != yolo_bucket_indices[1]:
                type_num = 2
        elif case_num == 3 and yolo_bucket_indices is not None:
            if yolo_bucket_indices[0] == yolo_bucket_indices[1] == yolo_bucket_indices[2]:
                type_num = 1
            elif yolo_bucket_indices[0] != yolo_bucket_indices[1] and yolo_bucket_indices[0] != yolo_bucket_indices[2] and yolo_bucket_indices[1] != yolo_bucket_indices[2]:
                type_num = 3
            else:
                # change the indice that is different to match the other two
                if yolo_bucket_indices[0] == yolo_bucket_indices[1]:
                    yolo_bucket_indices[2] = yolo_bucket_indices[0]
                elif yolo_bucket_indices[0] == yolo_bucket_indices[2]:
                    yolo_bucket_indices[1] = yolo_bucket_indices[0]
                else:
                    yolo_bucket_indices[0] = yolo_bucket_indices[1]
                type_num = 1
        
        bucket_score = [[0] for _ in range(12)]
        # collapse yolo_bucket_indices such only unique indices exist
        yolo_bucket_indices = list(set(yolo_bucket_indices or []))
        for idx in yolo_bucket_indices or []:
            bucket_score[idx][0] += 1 * C.yolo_weight[type_num - 1][case_num - 1]
            bucket_score[idx].append("yolo")
        for idx in classic_bucket_indices or []:
            bucket_score[idx][0] += 1 * C.classic_weight
            bucket_score[idx].append("classic")
        for idx in sift_bucket_indices or []:
            bucket_score[idx][0] += 1 * C.sift_weight
            bucket_score[idx].append("sift")

        # determine the dominant bucket based on the highest score
        dominant_bucket = bucket_score.index(max(bucket_score, key=lambda x: x[0])) if bucket_score else None

        if "classic" not in bucket_score[dominant_bucket] or "sift" not in bucket_score[dominant_bucket]:
            # if any bucket that contain yolo only contain yolo for all bucket in bucket_score
            if all("classic" not in bucket and "sift" not in bucket for bucket in bucket_score if "yolo" in bucket):
                if final_config is None and C.retry_flag == False:
                    final_config = "retry"
                    C.FLIPED_TARGET = not C.FLIPED_TARGET
                    sift_config_index = 2
                    continue
                else:
                    final_config = "classic with sift"
        elif "sift" in bucket_score[dominant_bucket]:
            final_config = "classic with sift"
        elif "classic" in bucket_score[dominant_bucket]:
            final_config = "classic"

        return final_config, C.FLIPED_TARGET, sift_config_index

            









def clean_up():
    C.G1 = 2
    C.initialize_score_table()
    if C.CONST_LABEL and os.path.exists(C.CROP_DIR):
        # delete pattern crop 
        shutil.rmtree(C.CROP_DIR)


def load_config(config):
    C.PT_TRANSFORM = config[0]
    C.USE_SIFT_REF_CALIBRATION = True if C.PT_TRANSFORM == "classic with sift" or C.PT_TRANSFORM == "sift" or C.PT_TRANSFORM == "elastix" or C.PT_TRANSFORM == "auto" else False 
    C.USE_ITKELASTIX_REF_CALIBRATION = True if C.PT_TRANSFORM == "elastix" else False 
    C.FLIPED_TARGET = config[1]
    C.SIFT_CONFIG_LIST[2] = C.SIFT_CONFIG_LIST[config[2]]



def score_image_routine(image_path):
    default_config = None
    usaf_result = None
    C.retry_flag = False
    try:
        if C.PT_TRANSFORM == "auto":
            default_config = [C.PT_TRANSFORM, C.FLIPED_TARGET, 1]
            img_configuration = auto_configurator(image_path, threshold=C.SCORE_THRESHOLD)
            if C.DEBUG_MODE or True:
                print("Auto Config: ", img_configuration)
            load_config(img_configuration)
            usaf_result = find_usaf_score(image_path, threshold=C.SCORE_THRESHOLD)
            load_config(default_config)
        else:
            default_config = None
            usaf_result = find_usaf_score(image_path, threshold=C.SCORE_THRESHOLD)
        
    except FileNotFoundError as e:
        print(f"File not found error: {image_path}. {e}, Retry fliped.")
        if default_config is not None:
            default_config[1] = not default_config[1]
        else:
            C.FLIPED_TARGET = not C.FLIPED_TARGET
        C.retry_flag = True
    except Exception as e:
        if "classic_warp.find_square_corners: No valid square detected in the image" in str(e):
            print(f"No valid square detected in {image_path}. Skipping this image.")
        elif "usaf_algo.find_usaf_score: The image is too blurry for detection" in str(e):
            print(f"The image {image_path} is too blurry for detection. Skipping this image.") 
        elif "usaf_algo.find_usaf_score: No best focus group found after all attempts" in str(e):
            print(f"No best focus group found for {image_path}. Skipping this image.")
        elif "sift_warp.sift_homography_with_origin:" in str(e):
            print(f"SIFT homography error {e} encountered for {image_path}. Skipping this image.")
        elif "usaf_algo.auto_configurator: Failed to read image from" in str(e):
            print(f"Failed to read image from {image_path}. Skipping this image.")
        elif "usaf_algo.auto_configurator: The image is too blurry for detection" in str(e):
            print(f"The image {image_path} is too blurry for detection. Skipping this image.")
        elif "usaf_algo.score_pattern_crops: Pattern crop classifier found unresolved at first scanned element, no valid focus score can be determined." in str(e):
            print(f"{e} encountered for {image_path}. retrying this image.")
            if default_config is not None:
                default_config[1] = not default_config[1]
            else:
                C.FLIPED_TARGET = not C.FLIPED_TARGET
            C.retry_flag = True
        elif "usaf_algo.auto_configurator: Coordinate calibration failed." in str(e):
            print(f"Coordinate calibration failed for {image_path}. Retrying with flipped target.")
            default_config[1] = not default_config[1]
            C.retry_flag = True
        else:
            print(f"Unknown error: {e}")
            raise e
    
    # final clean up
    clean_up()
    if default_config is not None:
        load_config(default_config)
    if not C.retry_flag:
        return usaf_result

    print(f"Retrying image: {image_path}")
    usaf_result = None
    
    try:
        if C.PT_TRANSFORM == "auto":
            default_config = [C.PT_TRANSFORM, C.FLIPED_TARGET, 1]
            img_configuration = auto_configurator(image_path, threshold=C.SCORE_THRESHOLD)
            if C.DEBUG_MODE or True:
                print("Auto Config: ", img_configuration)
            load_config(img_configuration)
            usaf_result = find_usaf_score(image_path, threshold=C.SCORE_THRESHOLD)
            load_config(default_config)
        else:
            default_config = None
            usaf_result = find_usaf_score(image_path, threshold=C.SCORE_THRESHOLD)
        
    except FileNotFoundError as e:
        print(f"File not found error: {image_path}. {e}, skipping this image.")
    except Exception as e:
        if "classic_warp.find_square_corners: No valid square detected in the image" in str(e):
            print(f"No valid square detected in {image_path}. Skipping this image.")
        elif "usaf_algo.find_usaf_score: The image is too blurry for detection" in str(e):
            print(f"The image {image_path} is too blurry for detection. Skipping this image.") 
        elif "usaf_algo.find_usaf_score: No best focus group found after all attempts" in str(e):
            print(f"No best focus group found for {image_path}. Skipping this image.")
        elif "sift_warp.sift_homography_with_origin:" in str(e):
            print(f"SIFT homography error {e} encountered for {image_path}. Skipping this image.")
        elif "usaf_algo.score_pattern_crops: Pattern crop classifier found unresolved at first scanned element, no valid focus score can be determined." in str(e):
            print(f"Pattern crop classifier unresolved for {image_path}. Skipping this image.")
        elif "usaf_algo.auto_configurator: Coordinate calibration failed." in str(e):
            print(f"Coordinate calibration failed for {image_path}. Skipping this image.")
        elif "usaf_algo.auto_configurator: Failed to read image from" in str(e):
            print(f"Failed to read image from {image_path}. Skipping this image.")
        elif "usaf_algo.auto_configurator: The image is too blurry for detection" in str(e):
            print(f"The image {image_path} is too blurry for detection. Skipping this image.")
        else:
            raise e

    # final clean up
    clean_up()
    if default_config is not None:
        load_config(default_config)

    return usaf_result




# for image_path in C.images:
#     score_image_routine(image_path)
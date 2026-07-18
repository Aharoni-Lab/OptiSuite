#X raise ValueError("classic_warp.find_square_corners: No valid square detected in the image.")
#X raise ValueError("elastix_warp.normalize_for_registration: Cannot normalize image with zero or negative dynamic range.")
# raise RuntimeError("elastix_warp.transformix_point: ITKElastix registration has not been performed yet.")
# raise RuntimeError("elastix_warp.setup_itkelastix_ref_mapping: Install ITKElastix with: pip install itk-elastix")
# raise RuntimeError("elastix_warp.setup_itkelastix_ref_mapping: SIFT-warped reference is empty")
# raise FileNotFoundError(f"pattern_crop.find_pattern_crop: Pattern crop not found for {image_label} {orientation} scan {scan_index}. Checked candidates: {candidates}")
# raise ValueError("pattern_crop.show_pattern_classification_results: No evaluated crops to display.")
#X raise ValueError("sift_warp.sift_homography_with_origin: image1 and image2 must not be None")
#X raise ValueError("sift_warp.sift_homography_with_origin: pixels_per_unit_x and pixels_per_unit_y must be > 0")
#X raise RuntimeError("sift_warp.sift_homography_with_origin: OpenCV SIFT is unavailable in this build (missing cv2.SIFT_create)")
#X raise RuntimeError("sift_warp.sift_homography_with_origin: Failed to extract SIFT descriptors from one or both images")
#X raise RuntimeError(f"sift_warp.sift_homography_with_origin: Not enough good SIFT matches ({len(good_matches)}), need at least {min_match_count}")
#X raise RuntimeError("sift_warp.sift_homography_with_origin: Failed to estimate homography from SIFT correspondences")
# raise ValueError("yolo_model.count_4pts_pattern: Input image is None")
# raise RuntimeError(f"yolo_model.count_4pts_pattern: Error loading model from {PT4_MODEL_PATH}: {e}")
# raise RuntimeError("yolo_model.count_4pts_pattern: YOLO returned no results")
# raise RuntimeError("yolo_model.count_4pts_pattern: YOLO returned no bounding boxes")
# raise FileNotFoundError(f"yolo_model.extract_yolo_detections: Could not read image: {curr_image}")
# raise ValueError("yolo_model.extract_yolo_detections: Invalid image array")
# raise ValueError("yolo_model.visualize_detections: No detections to visualize")
# raise RuntimeError(f"usaf_algo.coordinate_calibration: Failed to load SIFT reference image: {C.SIFT_REF_IMAGE_PATH}")
#X raise ValueError("usaf_algo.calculate_focus_scores: Input image is None.")
# raise ValueError("usaf_algo.calculate_focus_scores: Failed to find valid square after 3 attempts")
#X raise ValueError("usaf_algo.calculate_focus_scores: Large angles difference detected")
# raise ValueError("usaf_algo.find_best_focus_group: scores_list is None")
# raise ValueError(f"usaf_algo.find_usaf_score: Failed to read image from {image_path}")
#X raise ValueError("usaf_algo.find_usaf_score: The image is too blurry for detection")
#X raise ValueError("usaf_algo.find_usaf_score: No best focus group found after all attempts")
#X raise ValueError("usaf_algo.calculate_focus_scores: scanline grid misalignment detected")








     
# integrate to the UI
# one unresolved resistant
# edge image resistant
# best and reserved in between strategy
# improve yolo model























def map_ref_corners(orientation, gray, center_x, center_y, angle, side_length):
    #Seconary coordinate calibration using the reference corners
    # left and right ref corner are in standard coordinates 
    sift_angle = 0
    sift_length = 0
    TL_dir = C.prefer_dir_table[orientation][0]
    TR_dir = C.prefer_dir_table[orientation][1]
    BL_dir = C.prefer_dir_table[orientation][2]
    BR_dir = C.prefer_dir_table[orientation][3]
    if C.FLIPED_TARGET:
        TR_dir, TL_dir = TL_dir, TR_dir
        BR_dir, BL_dir = BL_dir, BR_dir
    
    if C.USE_SIFT_REF_CALIBRATION:
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

    else:

        # --------------------------------------------------------------------------------------------
        # Classic corner calculation
        # --------------------------------------------------------------------------------------------

        top_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_right_ref_coord, 1.0/5.0, TL_dir)
        top_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.top_left_ref_coord, 1.0/5.0, TR_dir)
        low_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_right_ref_coord, 1.0/5.0, BL_dir)
        low_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, C.low_left_ref_coord, 1.0/5.0, BR_dir)

    return top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner, sift_angle, sift_length





import cv2
from pathlib import Path
from . import constants as C
from .pattern_crop import find_pattern_crop, classify_pattern_resolution, show_pattern_classification_results








def score_pattern_crops(image_label="image"):
    """
    Score saved pattern crops from low to high resolution. Return the last element
    before either vertical or horizontal crop becomes unresolved.
    """
    crop_dir = Path(C.CROP_DIR)
    evaluated_crops = []
    last_resolved_result = None
    
    # Store indices as a list so we can look ahead
    scan_indices = [idx for idx in sorted(C.score_table.keys()) if idx >= 0]
    
    for i, scan_index in enumerate(scan_indices):
        group, element = C.score_table[scan_index]
        vertical_path = find_pattern_crop(crop_dir, image_label, "vertical", scan_index)
        horizontal_path = find_pattern_crop(crop_dir, image_label, "horizontal", scan_index)

        vertical_result = None
        horizontal_result = None
        vertical_img = None
        horizontal_img = None
        vertical_confidence = None
        horizontal_confidence = None
        
        if vertical_path is not None:
            vertical_img = cv2.imread(str(vertical_path))
            if vertical_img is not None:
                vertical_result, vertical_confidence = classify_pattern_resolution(vertical_img)
        if horizontal_path is not None:
            horizontal_img = cv2.imread(str(horizontal_path))
            # rotate image 90 degree clockwise
            if C.OPTIONAL_SETTING:
                horizontal_img = cv2.rotate(horizontal_img, cv2.ROTATE_90_CLOCKWISE)
            if horizontal_img is not None:
                horizontal_result, horizontal_confidence = classify_pattern_resolution(horizontal_img)

        # for visualization
        evaluated_crops.append(
            {
                "group": group,
                "element": element,
                "vertical_img": vertical_img,
                "horizontal_img": horizontal_img,
                "vertical_result": vertical_result,
                "horizontal_result": horizontal_result,
                "vertical_confidence": vertical_confidence,
                "horizontal_confidence": horizontal_confidence,
            }
        )

        # loop breaking condition
        if ((str(vertical_result).lower() == "unresolved" or str(horizontal_result).lower() == "unresolved") and C.SCORE_METHOD == "min") \
            or ((str(vertical_result).lower() == "unresolved" and str(horizontal_result).lower() == "unresolved") and (C.SCORE_METHOD == "max" or C.SCORE_METHOD == "mean")):
            
            # Look ahead to verify if the next two indices contain any unresolved patterns
            is_fluke = False
            if i + 1 < len(scan_indices):
                unresolved_in_lookahead = False
                for offset in range(1, 3):
                    if i + offset < len(scan_indices):
                        next_idx = scan_indices[i + offset]
                        
                        # Check vertical pattern of future index
                        v_path = find_pattern_crop(crop_dir, image_label, "vertical", next_idx)
                        if v_path is not None:
                            v_img = cv2.imread(str(v_path))
                            if v_img is not None:
                                v_res, _ = classify_pattern_resolution(v_img)
                                if str(v_res).lower() == "unresolved":
                                    unresolved_in_lookahead = True
                                    break
                                    
                        # Check horizontal pattern of future index
                        h_path = find_pattern_crop(crop_dir, image_label, "horizontal", next_idx)
                        if h_path is not None:
                            h_img = cv2.imread(str(h_path))
                            if C.OPTIONAL_SETTING:
                                h_img = cv2.rotate(h_img, cv2.ROTATE_90_CLOCKWISE)
                            if h_img is not None:
                                h_res, _ = classify_pattern_resolution(h_img)
                                if str(h_res).lower() == "unresolved":
                                    unresolved_in_lookahead = True
                                    break
                
                        
                # If no unresolved patterns were found in the look-ahead, treat this break as a fluke
                if not unresolved_in_lookahead:
                    is_fluke = True

            # If it's not a fluke, execute the standard termination logic
            if not is_fluke:
                if C.PATTERN_CLASSIFICATION_SHOW_PLOT:
                    show_pattern_classification_results(evaluated_crops)
                if C.DEBUG_MODE:
                    if last_resolved_result is not None:
                        print(
                            f"Pattern crop classifier best focus: "
                            f"group {last_resolved_result['group']}, element {last_resolved_result['element']}"
                        )
                    else:
                        print("Pattern crop classifier found unresolved at first scanned element")
                if last_resolved_result is None:
                    raise RuntimeError("usaf_algo.score_pattern_crops: Pattern crop classifier found unresolved at first scanned element, no valid focus score can be determined.")
                return last_resolved_result

        if (str(vertical_result).lower() == "resolved" and str(horizontal_result).lower() == "resolved" and C.SCORE_METHOD == "min") \
            or ((str(vertical_result).lower() == "resolved" or str(horizontal_result).lower() == "resolved") and (C.SCORE_METHOD == "max" or C.SCORE_METHOD == "mean")):
            last_resolved_result = {
                "group": group,
                "element": element,
                "scan_index": scan_index,
            }

    if C.DEBUG_MODE:
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
        elif scores_list[i]["score"] > scores_list[i - 1]["score"] * 1.2 or scores_list[i]["score"] < threshold:
            # If the score starts going UP, the previous index was the "bottom"
            chosen_index = min(i - 1, len(C.score_table) - 1)
            return C.score_table[chosen_index], chosen_index

    if C.FOCUS_GROUP_LAST_ABOVE_THRESHOLD:
        return C.score_table[chosen_index], chosen_index

    # If it never goes up, return first element
    print("No score goes up")
    chosen_index = len(C.score_table) - 1
    return C.score_table[chosen_index], chosen_index


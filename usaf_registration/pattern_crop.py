
import cv2
import numpy as np
import matplotlib.pyplot as plt
import math
import constants as C
from yolo_model import classify_resolution, detect_single_scanline_keypoints










def scanline_region_cropping(img, clean_img, pt_a, pt_b, curr_index):
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

    # if the box is out of bound
    # suffix = ""
    # if box_top_left[0] < 0 or box_top_left[1] < 0 or box_bottom_right[0] > clean_img.shape[1] or box_bottom_right[1] > clean_img.shape[0]:
    #     suffix = "_out_of_bounds"

    crop_x1 = max(0, box_top_left[0])
    crop_y1 = max(0, box_top_left[1])
    crop_x2 = min(clean_img.shape[1], box_bottom_right[0])
    crop_y2 = min(clean_img.shape[0], box_bottom_right[1])

    if crop_x2 > crop_x1 and crop_y2 > crop_y1:
        pattern_crop_dir = C.CROP_DIR
        pattern_crop_dir.mkdir(exist_ok=True)
        crop_img = clean_img[crop_y1:crop_y2, crop_x1:crop_x2]
        interpolation = cv2.INTER_AREA if crop_img.shape[0] > 256 or crop_img.shape[1] > 256 else cv2.INTER_CUBIC
        crop_img = cv2.resize(crop_img, (256, 256), interpolation=interpolation)
        if curr_index // 2 <= 32:
            crop_name = f"{C.current_image_label}_horizontal_scan_{curr_index // 2:03d}.png"
        else:
            crop_name = f"{C.current_image_label}_vertical_scan_{(curr_index // 2) - 33:03d}.png"
        cv2.imwrite(str(pattern_crop_dir / crop_name), crop_img)








def classify_pattern_resolution(img):
    return classify_resolution(img)


def find_pattern_crop(crop_dir, image_label, orientation, scan_index):
    candidates = [
        crop_dir / f"{image_label}_{orientation}_scan_{scan_index:03d}.png",
        crop_dir / f"{image_label}_{orientation}_scan_{scan_index}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"pattern_crop.find_pattern_crop: Pattern crop not found for {image_label} {orientation} scan {scan_index}. Checked candidates: {candidates}")


def show_pattern_classification_results(evaluated_crops):
    if not evaluated_crops:
        raise ValueError("pattern_crop.show_pattern_classification_results: No evaluated crops to display.")

    rows_per_page = max(1, int(C.PATTERN_CLASSIFICATION_ROWS_PER_PAGE))
    total_pages = math.ceil(len(evaluated_crops) / rows_per_page)

    for page_idx in range(total_pages):
        page_items = evaluated_crops[page_idx * rows_per_page:(page_idx + 1) * rows_per_page]
        rows = len(page_items)
        fig, axes = plt.subplots(
            rows,
            2,
            num=f"Pattern Classification Results {page_idx + 1}/{total_pages}",
            figsize=(9, max(3, rows * 2.4)),
            clear=True,
        )
        if rows == 1:
            axes = np.array([axes])

        fig.suptitle(f"Pattern Classification Results - Page {page_idx + 1}/{total_pages}", fontsize=12)

        for row_idx, item in enumerate(page_items):
            for col_idx, orientation in enumerate(("vertical", "horizontal")):
                ax = axes[row_idx, col_idx]
                img = item[f"{orientation}_img"]
                result = item[f"{orientation}_result"]
                if img is None:
                    ax.text(0.5, 0.5, "missing", ha="center", va="center", color="white")
                    ax.set_facecolor("black")
                else:
                    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

                confidence = item[f"{orientation}_confidence"]
                ax.set_title(f"G{item['group']} E{item['element']} {orientation}: {result} ({confidence:.2f})", fontsize=9)
                ax.axis("off")

        fig.tight_layout(rect=[0, 0, 1, 0.96])

    plt.show(block=True)






def augumented_single_scanline_detection(img, debug_text=""):
    """
    Rotate image from 0 to 345 degrees (step 15), run single-scanline KP detection,
    keep kp-pair lists with their rotated images, then return the longest scanline pair
    and its corresponding rotated image.

    Returns:
        best_kp_pair: ((x1, y1), (x2, y2)) or None
        best_rotated_img: rotated BGR image or None
        all_results: list of dicts: {"angle", "image", "kp_pairs"}
        best_angle: angle of best pair or None
    """
    if img is None or img.size == 0:
        raise ValueError("pattern_crop.augumented_single_scanline_detection: Invalid image.")

    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)

    best_kp_pair = None
    best_rotated_img = None
    best_angle = None
    best_len = -1.0

    delta_angle = 45 if C.DIAG_AUGUMENTATION else 90
    for angle in range(0, 360, delta_angle):
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        cos = abs(matrix[0, 0])
        sin = abs(matrix[0, 1])
        new_w = int(np.ceil((h * sin) + (w * cos)))
        new_h = int(np.ceil((h * cos) + (w * sin)))

        matrix[0, 2] += (new_w / 2.0) - center[0]
        matrix[1, 2] += (new_h / 2.0) - center[1]

        rotated = cv2.warpAffine(
            img,
            matrix,
            (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

        if C.DIAG_AUGUMENTATION and angle % 90 != 0:
            # Build a validity mask so we can reject keypoints that land on black padding.
            valid_mask = cv2.warpAffine(
                np.ones((h, w), dtype=np.uint8) * 255,
                matrix,
                (new_w, new_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            # center crop back to original size
            start_x = max(0, (new_w - w) // 2)
            start_y = max(0, (new_h - h) // 2)
            rotated = rotated[start_y : start_y + h, start_x : start_x + w]
            valid_mask = valid_mask[start_y : start_y + h, start_x : start_x + w]

        kp_pairs = detect_single_scanline_keypoints(rotated)

        for p1, p2 in kp_pairs:
            if C.DIAG_AUGUMENTATION and angle % 90 != 0:
                x1, y1 = int(p1[0]), int(p1[1])
                x2, y2 = int(p2[0]), int(p2[1])

                # Reject pair if either keypoint is outside bounds or on padded region.
                if (
                    x1 < 0 or x1 >= valid_mask.shape[1] or y1 < 0 or y1 >= valid_mask.shape[0] or
                    x2 < 0 or x2 >= valid_mask.shape[1] or y2 < 0 or y2 >= valid_mask.shape[0]
                ):
                    continue
                if valid_mask[y1, x1] == 0 or valid_mask[y2, x2] == 0:
                    continue

            length = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            if length > best_len:
                best_len = length
                best_kp_pair = (p1, p2)
                best_rotated_img = rotated
                best_angle = angle

    

    if best_rotated_img is not None and C.DEBUG_MODE:
        vis_img = best_rotated_img.copy()
        if best_kp_pair is not None:
            p1, p2 = best_kp_pair
            cv2.circle(vis_img, p1, 4, (0, 0, 255), -1)
            cv2.circle(vis_img, p2, 4, (0, 255, 255), -1)
            cv2.line(vis_img, p1, p2, (0, 255, 0), 2)

        plt.figure("Augmented Single Scanline Result", figsize=(8, 8))
        plt.clf()
        plt.imshow(cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB))
        if best_angle is None:
            plt.title(f"Final rotated image ({debug_text}) (no scanline detected)")
        else:
            plt.title(f"Final rotated image ({debug_text}) at {best_angle} deg")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

    if best_len <= 55.0:  # if the longest detected scanline is too short, consider it as no detection
        best_kp_pair = None
        best_rotated_img = None
        best_angle = None

    return best_kp_pair, best_rotated_img, best_angle












def verify_pattern_crops(pattern_crop_result):
    depth = C.VERIFICATION_DEPTH
    height = C.VERIFICATION_HEIGHT
    depth = max(0, depth)
    height = max(0, height)
    score_index = pattern_crop_result["scan_index"]
    # Reveal true index range for debugging, but keep it strict in production
    max_index = (len(C.score_table) - 1) - (C.G1 - 2) * 6 if C.DEBUG_MODE else len(C.score_table) - 1
    verified_index = score_index + height        # the verified score index
    verified_index = max(0, min(max_index, verified_index))
    diff_list = []

    for i in reversed(range(max(score_index - depth, 0), verified_index + 1)):
        vertical_path = find_pattern_crop(C.CROP_DIR, C.current_image_label, "vertical", i)
        horizontal_path = find_pattern_crop(C.CROP_DIR, C.current_image_label, "horizontal", i)
        vertical_img = cv2.imread(str(vertical_path))
        horizontal_img = cv2.imread(str(horizontal_path))
        if vertical_img is None or horizontal_img is None:
            raise FileNotFoundError(f"pattern_crop.verify_pattern_crops: Could not read pattern crop images for scan index {i}. Paths: {vertical_path}, {horizontal_path}")
        kp_vertical, vertical_img, _ = augumented_single_scanline_detection(vertical_img, "vertical")
        kp_horizontal, horizontal_img, _ = augumented_single_scanline_detection(horizontal_img, "horizontal")
        if vertical_img is not None:
            vertical_img = (vertical_img / 255.0).astype(np.float32)
        if horizontal_img is not None:
            horizontal_img = (horizontal_img / 255.0).astype(np.float32)

        if not kp_vertical:
            diff_vertical = None
        else:        
            mask = np.zeros(vertical_img.shape[:2], dtype=np.uint8)
            cv2.line(mask, kp_vertical[0], kp_vertical[1], 255, 2)
            # Get pixel values along the line from vertical_img
            line_pixels_vertical = vertical_img[mask > 0]
            diff_vertical = np.max(line_pixels_vertical) - np.min(line_pixels_vertical) if line_pixels_vertical.size > 0 else 0

        if not kp_horizontal:
            diff_horizontal = None
        else:
            mask = np.zeros(horizontal_img.shape[:2], dtype=np.uint8)
            cv2.line(mask, kp_horizontal[0], kp_horizontal[1], 255, 2)
            # Get pixel values along the line from horizontal_img
            line_pixels_horizontal = horizontal_img[mask > 0]
            diff_horizontal = np.max(line_pixels_horizontal) - np.min(line_pixels_horizontal) if line_pixels_horizontal.size > 0 else 0

        if C.DEBUG_MODE:
            temp_group, temp_element = C.score_table[i]
            kp_len_vertical = float(np.hypot(kp_vertical[1][0] - kp_vertical[0][0], kp_vertical[1][1] - kp_vertical[0][1])) if kp_vertical else 0
            kp_len_horizontal = float(np.hypot(kp_horizontal[1][0] - kp_horizontal[0][0], kp_horizontal[1][1] - kp_horizontal[0][1])) if kp_horizontal else 0
            print(f"Scan index {i} (Group {temp_group}, Element {temp_element}): vertical diff = {diff_vertical}, horizontal diff = {diff_horizontal}")
            print(f"    vertical kp length = {kp_len_vertical}, horizontal kp length = {kp_len_horizontal}")


        diff_list.append((diff_vertical, diff_horizontal))

    state_table = []
    if C.SCORE_METHOD == "max":
        state_table = C.max_state_table
    elif C.SCORE_METHOD == "min":
        state_table = C.min_state_table
    else:
        state_table = C.mean_state_table

    index1 = -1
    index2 = -1
    first_return_index = None
    first_jump_index = None
    curr_state = -1
    for diff in diff_list:
        if diff[0] is None:
            index1 = 2
        elif diff[0] >= C.SCORE_THRESHOLD:
            index1 = 0
        else:
            index1 = 1

        if diff[1] is None:
            index2 = 2
        elif diff[1] >= C.SCORE_THRESHOLD:
            index2 = 0
        else:
            index2 = 1

        curr_state = state_table[index1][index2]

        if curr_state == 4:
            average_diff = (diff[0] + diff[1]) / 2
            if average_diff >= C.SCORE_THRESHOLD:
                curr_state = 1
            else:
                curr_state = 2


        
        if verified_index <= score_index:
            if curr_state == 1:
                # This ensures that score only jumps up from score_index if score_index element is resolved
                if verified_index == score_index and first_jump_index is not None:
                    verified_index = first_jump_index
                    
                if first_return_index is not None and C.VERIFICATION_STRATEGY == "best":
                    verified_index = first_return_index
                else:
                    verified_index = verified_index
                break
            elif curr_state == 2:
                verified_index = verified_index - 1
                continue
            elif curr_state == 3:
                if first_return_index is None:
                    first_return_index = verified_index
                verified_index = verified_index - 1
                continue
        else:
            # the jump up index require all element between itself and score_index to be resolved
            # otherwise, it will be treated as unresolved and jump down until the first resolved element
            if curr_state == 1:
                if first_jump_index is None:
                    first_jump_index = verified_index
                verified_index = verified_index - 1
            else:
                verified_index = verified_index - 1
                first_jump_index = None


    if curr_state == 3 and first_return_index is not None and C.VERIFICATION_STRATEGY == "best":
        verified_index = first_return_index

    verified_index = max(0, min(max_index, verified_index))
    verified_group, verified_element = C.score_table[verified_index]
    verfication_result = {
        "group": verified_group,
        "element": verified_element,
        "scan_index": verified_index,
    }   

    return verfication_result

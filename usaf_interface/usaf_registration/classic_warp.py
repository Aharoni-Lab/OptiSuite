import cv2
import numpy as np
import matplotlib.pyplot as plt
import random
from . import constants as C
from .transforms import get_rotated_pt









def make_dummy_valid_square(gray):
    """
    Build a centered diamond-shaped contour so SIFT calibration still gets one
    attempt when no physical square was detected.
    """
    h, w = gray.shape[:2]
    cx = w // 2
    cy = h // 2
    radius = max(8, min(h, w) // 12)
    radius = min(radius, max(1, cx - 1), max(1, cy - 1), max(1, w - cx - 2), max(1, h - cy - 2))

    return np.array(
        [
            [[cx, cy - radius]],
            [[cx + radius, cy]],
            [[cx, cy + radius]],
            [[cx - radius, cy]],
        ],
        dtype=np.int32,
    )


def is_valid_square(approx, gray, white_threshold=250, angle_tolerance=5, side_ratio_tolerance=1.2):
    '''
    Check if the approximated polygon is a valid square with:
    - Ratio between max and min side length between 1 and 1.5
    - ~90 degree corners (perpendicular edges)
    - White interior (at least 70% of interior pixels above threshold)
    
    Returns True if all criteria are met, False otherwise.
    '''
    corners = approx.reshape(-1, 2).astype(float)
    
    # Calculate side lengths
    side_lengths = []
    for i in range(4):
        p1 = corners[i]
        p2 = corners[(i + 1) % 4]
        dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        side_lengths.append(dist)
    
    # Check side length ratio: should be between 1 and 1.5
    max_side = max(side_lengths)
    min_side = min(side_lengths)
    if min_side == 0:
        return False
    ratio = max_side / min_side
    if not (1 <= ratio <= side_ratio_tolerance):
        return False
    
    # Check corner angles (should be ~90 degrees, i.e., perpendicular edges)
    for i in range(4):
        p_prev = corners[(i - 1) % 4]
        p_curr = corners[i]
        p_next = corners[(i + 1) % 4]
        
        # Edge vectors
        e1 = p_curr - p_prev
        e2 = p_next - p_curr
        
        # Normalize vectors
        e1_norm = np.linalg.norm(e1)
        e2_norm = np.linalg.norm(e2)
        
        if e1_norm == 0 or e2_norm == 0:
            return False
            
        e1 = e1 / e1_norm
        e2 = e2 / e2_norm
        
        # Dot product of normalized vectors (should be close to 0 for perpendicular)
        dot_product = np.dot(e1, e2)
        
        # Allow tolerance: 
        # Accept angles between roughly 85° and 95°
        if abs(dot_product) > np.cos(np.radians(90 - angle_tolerance)):
            return False
    
    # Check if interior is white
    mask = np.zeros_like(gray, dtype=np.uint8)
    cv2.drawContours(mask, [approx], 0, 255, -1)
    
    interior_pixels = gray[mask > 0]
    if len(interior_pixels) == 0:
        return False
    
    white_ratio = np.sum(interior_pixels > white_threshold) / len(interior_pixels)
    
    # At least 90% of interior should be white
    if white_ratio < 0.99:
        return False
    
    return True



def find_square_corners(gray):
    '''
    find the square in the usaf target for initial coordinate calibration, 
    return the corners in standard coordinates (x, y)
    '''
    C.valid_squares = []  # Reset the list for each new image

    # RGB color of gray
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    # Multi-scale contour detection can recover squares that are weak at a single scale.
    scale_factors = [1.0, 1.5, 2.0]
    approx_polys = []  # all approximated polygons mapped to original image coordinates
    square_candidates = []

    def _bbox_iou(rect_a, rect_b):
        ax1, ay1, aw, ah = rect_a
        bx1, by1, bw, bh = rect_b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh
        inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
        inter_h = max(0, min(ay2, by2) - max(ay1, by1))
        inter = inter_w * inter_h
        if inter <= 0:
            return 0.0
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    for scale in scale_factors:
        if scale == 1.0:
            scaled_gray = gray
        else:
            interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
            scaled_gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=interp)

        # Use GaussianBlur to reduce noise before thresholding
        blurred = cv2.GaussianBlur(scaled_gray, (5, 5), 0)
        # Use Otsu's thresholding to automatically find the best light/dark split
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # # Find all contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        # Sort contours by area (largest first)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for cnt in contours:
            area_scaled = cv2.contourArea(cnt)
            if area_scaled < 500:  # Ignore tiny noise on the current scale
                continue

            peri = cv2.arcLength(cnt, True)
            # Increase the 0.02 factor if it still fails (e.g., 0.04)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

            # Map approximated polygon back to original-image coordinates for unified downstream use.
            approx_orig = np.array(approx, dtype=np.float32)
            if scale != 1.0:
                approx_orig /= scale
            approx_orig = np.round(approx_orig).astype(np.int32)
            approx_orig[:, 0, 0] = np.clip(approx_orig[:, 0, 0], 0, gray.shape[1] - 1)
            approx_orig[:, 0, 1] = np.clip(approx_orig[:, 0, 1], 0, gray.shape[0] - 1)
            approx_polys.append(approx_orig)

            # Look for 4-sided polygons that form valid squares
            if len(approx) == 4 and is_valid_square(approx, thresh):
                area_orig = area_scaled / (scale * scale)
                square_candidates.append((area_orig, approx_orig))

    # Sort all candidates by area descending so retry starts from largest square.
    square_candidates.sort(key=lambda item: item[0], reverse=True)

    # IoU-based deduplication in sorted order (keep largest in each overlap cluster).
    dedup_iou_threshold = 0.7
    deduped_candidates = []
    for area_orig, approx_orig in square_candidates:
        rect = cv2.boundingRect(approx_orig)
        duplicate = False
        for _, kept_approx in deduped_candidates:
            kept_rect = cv2.boundingRect(kept_approx)
            if _bbox_iou(rect, kept_rect) >= dedup_iou_threshold:
                duplicate = True
                break
        if not duplicate:
            deduped_candidates.append((area_orig, approx_orig))

    C.valid_squares = [approx for _, approx in deduped_candidates]
    if len(C.valid_squares) == 0 and C.USE_SIFT_REF_CALIBRATION:
        C.valid_squares = [make_dummy_valid_square(gray)]
        if C.DEBUG_MODE:
            print("No valid square detected; using dummy square for SIFT calibration.")
    best_square_corners = C.valid_squares[0] if len(C.valid_squares) > 0 else None

    if C.DEBUG_MODE:
        # Show approxPolyDP output (polygonal approximation of contours).
        approx_img = img.copy()
        for approx in approx_polys:
            color = (0, 255, 255) if len(approx) == 4 else (255, 0, 0)  # yellow for quads, blue for others
            cv2.polylines(approx_img, [approx], True, color, 2)

        max_w, max_h = 1600, 900
        h_ap, w_ap = approx_img.shape[:2]
        scale_ap = min(max_w / w_ap, max_h / h_ap, 1.0)
        if scale_ap < 1.0:
            approx_img = cv2.resize(
                approx_img,
                (int(w_ap * scale_ap), int(h_ap * scale_ap)),
                interpolation=cv2.INTER_AREA,
            )

        plt.figure("approxPolyDP", figsize=(12, 7))
        plt.clf()
        plt.imshow(cv2.cvtColor(approx_img, cv2.COLOR_BGR2RGB))
        plt.title("approxPolyDP")
        plt.axis("off")
        plt.tight_layout()
        plt.show(block=True)

    if C.DEBUG_MODE:
        # Visualize all detected valid squares and highlight the best one.
        detected_img = img.copy()
        if len(C.valid_squares) > 0:
            cv2.drawContours(detected_img, C.valid_squares, -1, (0, 255, 255), 2)  # yellow: all detected squares
            for idx, square in enumerate(C.valid_squares):
                center = np.mean(square.reshape(-1, 2), axis=0).astype(int) + random.randint(-10, 10)
                cv2.putText(detected_img, str(idx), tuple(center), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 0), 2)
        if best_square_corners is not None:
            cv2.drawContours(detected_img, [best_square_corners], -1, (0, 0, 255), 3)  # red: best square

        # Fit full image into a large window so it is not clipped on screen.
        max_w, max_h = 1600, 900
        h, w = detected_img.shape[:2]
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            show_img = cv2.resize(detected_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            show_img = detected_img

        plt.figure("Detected Squares", figsize=(12, 7))
        plt.clf()
        plt.imshow(cv2.cvtColor(show_img, cv2.COLOR_BGR2RGB))
        plt.title("Detected Squares")
        plt.axis("off")
        plt.tight_layout()
        plt.show(block=True)


    if best_square_corners is not None:
        # Create a copy because the valid squares list is by ref
        corners = best_square_corners.reshape(-1, 2).copy()

        if C.DEBUG_MODE:
            print("Detected Corners:\n", corners)
            # Draw for visual confirmation
            for (x, y) in corners:
                cv2.circle(img, (x, y), 8, (0, 255, 0), -1)
            cv2.drawContours(img, [best_square_corners], -1, (255, 0, 0), 3)
            
            plt.figure("Success")
            plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            plt.title("Success")
            plt.show()

        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        return corners
    else:
        if C.DEBUG_MODE:
            print("Square not detected. Showing thresholded image for debugging...")
            plt.figure("Debug Thresh")
            plt.imshow(thresh, cmap='gray')
            plt.title("Debug Thresh")
            plt.show()
        raise ValueError("classic_warp.find_square_corners: No valid square detected in the image.")








def bright_pixels_as_corners(region, threshold=128):
    """
    Same layout as cv2.goodFeaturesToTrack: (N, 1, 2) float32 with region-local (x, y),
    one entry per pixel whose grayscale is >= threshold. Returns None if no pixels match.
    """
    region_u8 = region if region.dtype == np.uint8 else region.astype(np.uint8)
    ys, xs = np.where(region_u8 >= threshold)
    if len(xs) == 0:
        return None
    pts = np.empty((len(xs), 1, 2), dtype=np.float32)
    pts[:, 0, 0] = xs.astype(np.float32)
    pts[:, 0, 1] = ys.astype(np.float32)
    return pts


def find_white_corner_in_region(gray, center_x, center_y, angle, side_length, region_center, region_size, prefer_dir = 0):
    """
    Find the location of a white corner on black background within a square region.
    The region is centered at region_center in usaf coordinate
    with dim of square = region size * side_length, and rotated by angle from the standard coordinate system.
    """
   
    # convert the center x and center y from standard coordinates to the screen coordinate 
    # by translating by the image height and flipping the y coordinate
    center_x = center_x
    center_y = gray.shape[0] - center_y - 1
    # Convert region center from usaf coordinates to screen coordinates
    region_center_scaled = (region_center[0] * side_length, region_center[1] * side_length)
    # translate and rotate to get screen coordinates of the region center
    flip = -1 if C.FLIPED_TARGET else 1
    region_center_img = get_rotated_pt(center_x, center_y, flip * region_center_scaled[0], -region_center_scaled[1], angle)
    #calculate the region size in pixels
    region_size_px = max(region_size * side_length, 13)

    # Extract region bounds
    x1 = int(region_center_img[0] - region_size_px)
    x2 = int(region_center_img[0] + region_size_px)
    y1 = int(region_center_img[1] - region_size_px)
    y2 = int(region_center_img[1] + region_size_px)
    
    # if the region is out of image return none
    if x2 >= gray.shape[1] or x1 < 0 or y2 >= gray.shape[0] or y1 < 0 and C.CROPED_WINDOW_RETRY:
        return None
    # Clip to image bounds
    x1 = max(0, x1)
    x2 = min(gray.shape[1], x2)
    y1 = max(0, y1)
    y2 = min(gray.shape[0], y2)
    
    region = gray[y1:y2, x1:x2]
    
    if region.size == 0:
        return None
    
    if C.CORNER_METHOD == "threshold":
        corners_shi_tomasi = bright_pixels_as_corners(region)
    else:
        # Apply Shi-Tomasi corner detection on white pixels
        corners_shi_tomasi = cv2.goodFeaturesToTrack(region.astype(np.uint8), 20, 0.001, 1)
        # Subpixel refinement if needed
        if region.shape[0] > 30 and region.shape[1] > 30 and C.SUBPIXEL:             # If the region is small, skip subpixel refinement
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
            cv2.cornerSubPix(region.astype(np.uint8), corners_shi_tomasi, (10, 10), (-1, -1), criteria)

    if corners_shi_tomasi is not None and len(corners_shi_tomasi) > 0:
        copy_corners = corners_shi_tomasi.copy()
        # Return the corner closest to the preference direction
        corner_x = corners_shi_tomasi[:, 0, 0]  # x-coordinates
        corner_y = corners_shi_tomasi[:, 0, 1]  # y-coordinates
        # print("x: ", corner_x, "y: ", corner_y)

        if prefer_dir == 0:                     #prefer center
            corner_dist = np.sqrt((corner_x - region.shape[1] / 2) ** 2 + (corner_y - region.shape[0] / 2) ** 2)
            search_idx = np.argmin(corner_dist)
        elif prefer_dir == 3:                   #prefer top
            search_idx = np.argmin(corner_y)
        elif prefer_dir == 4:                   #prefer bottom
            search_idx = np.argmax(corner_y)
        elif prefer_dir == 1:                   #prefer left
            search_idx = np.argmin(corner_x)
        elif prefer_dir == 2:                   #prefer right
            search_idx = np.argmax(corner_x)
        corner_local = corners_shi_tomasi[search_idx, 0]

        if C.DEBUG_MODE:
            print("prefer_dir: ", prefer_dir)
            # Create a BGR version of the crop for color drawing
            debug_img = cv2.cvtColor(region, cv2.COLOR_GRAY2BGR)
            i_ctr = 0
            for corner in copy_corners:
                if i_ctr != search_idx:
                    cv2.circle(debug_img, (int(corner[0][0]), int(corner[0][1])), 1, (0, 0, 255), -1)
                i_ctr += 1
                # print(f"Corner {i_ctr}: ({corner[0][0]}, {corner[0][1]})")
            cv2.circle(debug_img, (int(corner_local[0]), int(corner_local[1])), 1, (0, 200, 0), -1)
            plt.figure("Debug Region")
            plt.imshow(cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB))
            plt.title("Debug Region")
            plt.show()

        
        # Convert back to screen coordinates
        corner_img = (corner_local[0] + x1, corner_local[1] + y1)
        # convert back to standard coordinates
        corner_img = (int(corner_img[0]), int(gray.shape[0] - 1 - corner_img[1]))
        
        return corner_img
    else:
        return None



def find_target_orientation(gray, center_x, center_y, unit_vector, side_length):
    '''
    calculate the orientation of the target by comparing the average of the scanline element
    '''
    center = np.array([center_x, center_y])
    normal_vector = np.array([-unit_vector[1], unit_vector[0]])
    normal_vector = normal_vector / np.linalg.norm(normal_vector)

    # The marking of orientation are based on the orientation where
    # the top left is the top direction
    # the top right is the right direction
    # the bottom right is the bottom direction
    # the bottom left is the left direction
    scanline_length = 0.7 * side_length

    scanline_start = np.zeros((4, 2))
    scanline_start[1] = center + scanline_length * unit_vector        #right
    scanline_start[3] = center - scanline_length * unit_vector        #left
    scanline_start[0] = center + scanline_length * normal_vector      #top
    scanline_start[2] = center - scanline_length * normal_vector      #bottom
    scanline_length = 6 * side_length
    scanline_end = np.zeros((4, 2))
    scanline_end[1] = center + scanline_length * unit_vector        #right
    scanline_end[3] = center - scanline_length * unit_vector        #left
    scanline_end[0] = center + scanline_length * normal_vector      #top
    scanline_end[2] = center - scanline_length * normal_vector      #bottom

    h, w = gray.shape[:2]

    # Calculate how much we need to scale the line to hit each boundary
    for i in range(len(scanline_end)):
        pt = scanline_end[i]
        center_i = center
            
        diff = pt - center_i
        
        # Calculate how much we need to scale the line to hit each boundary
        # We only care about boundaries the line is actually crossing
        t = 1.0
        
        if pt[0] < 0:      t = min(t, -center_i[0] / diff[0])
        if pt[0] >= w:     t = min(t, (w - 1 - center_i[0]) / diff[0])
        if pt[1] < 0:      t = min(t, -center_i[1] / diff[1])
        if pt[1] >= h:     t = min(t, (h - 1 - center_i[1]) / diff[1])
        
        # Apply the single best ratio to both X and Y simultaneously
        scanline_end[i] = center_i + t * diff

    # convert to screen coordinates and int type
    scanline_start[:, 1] = gray.shape[0] - scanline_start[:, 1] - 1
    scanline_start = scanline_start.astype(int)
    scanline_end[:, 1] = gray.shape[0] - scanline_end[:, 1] - 1
    scanline_end = scanline_end.astype(int)

    if C.DEBUG_MODE:
        # Convert grayscale to BGR so we can draw in color
        img_copy = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) 

        for i in range(scanline_end.shape[0]):
            end_point = tuple(scanline_end[i])
            start_point = tuple(scanline_start[i])
            # Now (0,0,255) will actually show up as Red
            cv2.line(img_copy, start_point, end_point, (0,0,255), 4)

        plt.figure("Debug Scans", figsize=(8, 8))
        plt.imshow(cv2.cvtColor(img_copy, cv2.COLOR_BGR2RGB))
        plt.title("Debug Scans")
        plt.show()

    average = np.zeros(4)
    for i in range(scanline_end.shape[0]):
        end_point = tuple(scanline_end[i])
        start_point = tuple(scanline_start[i])
        # Create a mask for the line
        mask = np.zeros_like(gray, dtype=np.uint8)
        cv2.line(mask, start_point, end_point, 255, 4)
        # Get pixel values along the line from normalized_gray
        line_pixels = gray[mask > 0]
        # calculate average grayscale value along the line
        if line_pixels.size > 20:
            average[i] = np.mean(line_pixels)
        else:
            average[i] = 0

    # find the index of the minimum value
    min_index = np.argmin(average)
    if C.DEBUG_MODE:
        print(f"Minimum index: {min_index}")
    # return the corresponding orientation
    return min_index


def get_adjusted_top_corners_from_enclosing_rectangle(top_right_corner, top_left_corner, low_right_corner, low_left_corner):
    """
    Use all four detected reference corners to build a minimum-area enclosing rectangle,
    then select the two rectangle corners closest to the original top-right/top-left corners.
    """
    points = np.array([top_right_corner, top_left_corner, low_right_corner, low_left_corner], dtype=np.float64)

    # 1. Calculate the true center of the points (invariant under rotation)
    true_center = np.mean(points, axis=0)

    best_area = None
    best_theta = 0.0
    best_dimensions = (0.0, 0.0)  # (half_width, half_height)

    # Search orientation in [0, pi): Rectangles have 180-degree symmetry
    thetas = np.linspace(0.0, np.pi, 1440, endpoint=False)
    for theta in thetas:

        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        
        # Rotate points around the true center
        centered_pts = points - true_center
        x_rot = centered_pts[:, 0] * cos_t + centered_pts[:, 1] * sin_t
        y_rot = -centered_pts[:, 0] * sin_t + centered_pts[:, 1] * cos_t

        min_x, max_x = np.min(x_rot), np.max(x_rot)
        min_y, max_y = np.min(y_rot), np.max(y_rot)
        
        # Calculate distinct dimensions and the resulting area
        width = max_x - min_x
        height = max_y - min_y
        area = width * height

        if best_area is None or area < best_area:
            best_area = area
            best_theta = theta
            # Store the half-dimensions to construct the rectangle easily later
            best_dimensions = (width * 0.5, height * 0.5)

    half_w, half_h = best_dimensions

    # 2. Build the perfect rectangle in the rotated space centered at (0, 0)
    # The order of these points doesn't strictly matter as step 4 matches by proximity
    rect_rot = np.array([
        [-half_w, -half_h],
        [ half_w, -half_h],
        [ half_w,  half_h],
        [-half_w,  half_h],
    ], dtype=np.float64)

    # 3. Rotate the rectangle corners back and add the true center back
    cos_t = np.cos(best_theta)
    sin_t = np.sin(best_theta)
    
    rect_std = np.zeros_like(rect_rot)
    rect_std[:, 0] = rect_rot[:, 0] * cos_t - rect_rot[:, 1] * sin_t + true_center[0]
    rect_std[:, 1] = rect_rot[:, 0] * sin_t + rect_rot[:, 1] * cos_t + true_center[1]

    # 4. Match the closest corners to top_right and top_left
    tr = np.array(top_right_corner, dtype=np.float64)
    tl = np.array(top_left_corner, dtype=np.float64)
    best_pair = (0, 1)
    best_dist = None
    
    for i in range(4):
        for j in range(4):
            if i == j:
                continue
            dist = np.linalg.norm(rect_std[i] - tr) + np.linalg.norm(rect_std[j] - tl)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_pair = (i, j)

    adjusted_top_right = tuple(rect_std[best_pair[0]])
    adjusted_top_left = tuple(rect_std[best_pair[1]])
    
    return adjusted_top_right, adjusted_top_left


import cv2
import numpy as np


# Define points as (local_x, local_y) relative to the center
# Every two points (0&1, 2&3, etc.) will form one line
g2_x = -3.2
g3_x = 2.5
g4_x = -0.56
g5_x = 0.87
g6_x = 0.12
group_positions = {
    0: (g2_x, 0.35),     1: (g2_x, -0.37),
    2: (g2_x, -1.31),    3: (g2_x, -1.96),
    4: (g2_x, -2.8),    5: (g2_x, -3.40),
    
    6: (g3_x, 0.43),     7: (g3_x, 0.01),
    8: (g3_x, -0.5),    9: (g3_x, -0.88),
    10: (g3_x, -1.33),    11: (g3_x, -1.66),
    12: (g3_x, -2.08-0.05),    13: (g3_x, -2.38-0.05),
    14: (g3_x, -2.73-0.05),    15: (g3_x, -3.01-0.05),
    16: (g3_x, -3.32-0.07),    17: (g3_x, -3.57-0.07),
    
    18: (g4_x, -1.84-0.03),    19: (g4_x, -2.04-0.03),
    20: (g4_x, -2.26-0.05),    21: (g4_x, -2.44-0.05),
    22: (g4_x, -2.63-0.05),    23: (g4_x, -2.79-0.05),
    24: (g4_x, -2.97-0.05),    25: (g4_x, -3.1-0.05),
    26: (g4_x, -3.26-0.05),    27: (g4_x, -3.39-0.05),

    28: (g5_x, -1.838-0.03),    29: (g5_x, -1.944-0.03),
    30: (g5_x, -2.072-0.038),    31: (g5_x, -2.168-0.038),
    32: (g5_x, -2.277-0.04),    33: (g5_x, -2.365-0.04),
    34: (g5_x, -2.468-0.037),    35: (g5_x, -2.538-0.044),
    36: (g5_x, -2.64-0.04),    37: (g5_x, -2.696-0.04),
    38: (g5_x, -2.782-0.045),    39: (g5_x, -2.836-0.045),
    
    40: (g6_x, -2.453),    41: (g6_x, -2.49),
    42: (g6_x, -2.557),    43: (g6_x, -2.59),
    44: (g6_x, -2.648),    45: (g6_x, -2.681),
    46: (g6_x-0.003, -2.735),    47: (g6_x-0.003, -2.755),
    48: (g6_x-0.005, -2.81),    49: (g6_x-0.005, -2.83),

    50: (-3.64, 0.5),    51: (2.64, 0.5)

}




def find_square_corners(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not load image.")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Use GaussianBlur to reduce noise before thresholding
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Use Otsu's thresholding to automatically find the best light/dark split
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Find all contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # Sort contours by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    square_corners = None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500: # Ignore tiny noise
            continue
            
        peri = cv2.arcLength(cnt, True)
        # Increase the 0.02 factor if it still fails (e.g., 0.04)
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

        # Look for the first 4-sided polygon (the square should be one of the largest)
        if len(approx) == 4:
            square_corners = approx
            break

    if square_corners is not None:
        corners = square_corners.reshape(-1, 2)
        print("Detected Corners:\n", corners)

        # Draw for visual confirmation
        for (x, y) in corners:
            cv2.circle(img, (x, y), 8, (0, 255, 0), -1)
        cv2.drawContours(img, [square_corners], -1, (255, 0, 0), 3)
        
        cv2.namedWindow("Success", cv2.WINDOW_NORMAL) 
        cv2.imshow("Success", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return corners
    else:
        # Debugging: show the thresholded image if it fails
        print("Square not detected. Showing thresholded image for debugging...")
        cv2.imshow("Debug Thresh", thresh)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return None


# Draw scanlines on the image
# To find a point at a specific (local_x, local_y) inside the square:
def get_rotated_pt(cx, cy, local_x, local_y, angle):
    # Standard rotation formula
    rx = cx + local_x * np.cos(angle) - local_y * np.sin(angle)
    ry = cy + local_x * np.sin(angle) + local_y * np.cos(angle)
    return (int(rx), int(ry))


def find_white_corner_in_region(gray, center_x, center_y, angle, side_length, region_center, region_size):
    """
    Find the location of a white corner on black background within a square region.
    The region is centered at the midpoint of group_position[50] and group_position[51]
    with side length = side_length/4.
    """
    
    # Define search region centered at midpoint of position[50] and position[51]
    region_center_local = region_center
    
    # Convert to pixel coordinates (apply side_length scaling)
    region_center_scaled = (region_center_local[0] * side_length, region_center_local[1] * side_length)
    
    # Get the actual pixel position accounting for the coordinate flip
    region_center_img = get_rotated_pt(center_x, center_y, -region_center_scaled[0], -region_center_scaled[1], angle)
    region_size_px = region_size * side_length
    
    # Extract region bounds
    x1 = int(region_center_img[0] - region_size_px)
    x2 = int(region_center_img[0] + region_size_px)
    y1 = int(region_center_img[1] - region_size_px)
    y2 = int(region_center_img[1] + region_size_px)
    
    # Clip to image bounds
    x1 = max(0, x1)
    x2 = min(gray.shape[1], x2)
    y1 = max(0, y1)
    y2 = min(gray.shape[0], y2)
    
    region = gray[y1:y2, x1:x2]
    
    if region.size == 0:
        return None
    
    # Find white pixels (intensity > 200) on black background
    white_thresh = 200
    white_binary = cv2.threshold(region, white_thresh, 255, cv2.THRESH_BINARY)[1]
    
    # Apply Harris corner detection on white pixels
    corners_harris = cv2.cornerHarris(white_binary.astype(np.uint8), 2, 3, 0.04)
    corners_harris = cv2.dilate(corners_harris, None)
    
    # Find corner coordinates from Harris response
    corner_coords = np.argwhere(corners_harris > 0.01 * corners_harris.max())
    
    if len(corner_coords) > 0:
        # Return the corner closest to the center of the region
        corner_x = corner_coords[:, 1]  # x-coordinates
        corner_y = corner_coords[:, 0]  # y-coordinates
        corner_dist = np.sqrt((corner_x - region.shape[1] / 2) ** 2 + (corner_y - region.shape[0] / 2) ** 2)
        max_idx = np.argmin(corner_dist)
        corner_local = corner_coords[max_idx]
        
        # Convert back to image coordinates
        corner_img = (corner_local[1] + x1, corner_local[0] + y1)
        
        return corner_img
    else:
        return None


def calculate_focus_scores(image_path, corners):
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Find the brightest pixel
    brightest = np.max(gray)
    # Create normalized image duplicate
    normalized_gray = gray.astype(float) / brightest
    # Ensure values are between 0 and 1 (though division by max should already do this)
    normalized_gray = np.clip(normalized_gray, 0, 1)
    


    # Assume corners are [tl, tr, br, bl]
    corners = np.array(corners)
    min_x = np.min(corners[:, 0])
    max_x = np.max(corners[:, 0])
    min_y = np.min(corners[:, 1])
    max_y = np.max(corners[:, 1])
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    side_length = np.sqrt((corners[0][0] - corners[1][0])**2 + (corners[0][1] - corners[1][1])**2)  # approximate side length
    #find corner with max y
    top_corner = corners[np.argmin(corners[:, 1])]
    left_corner = corners[np.argmin(corners[:, 0])]
    right_corner = corners[np.argmax(corners[:, 0])]
    bottom_corner = corners[np.argmax(corners[:, 1])]
    #find unit vector that point from right corner to top corner
    unit_vector = (top_corner - right_corner) / np.linalg.norm(top_corner - right_corner)
    #find angle of unit vector with y axis
    angle = np.arctan2(unit_vector[1], unit_vector[0]) + np.pi / 2
    right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, group_positions[50], 1.0/5.0)
    left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, group_positions[51], 1.0/5.0)
    #recalculate angle using the right reference corner and left reference corner
    #calculate unit vector from right reference corner to left reference corner
    if right_ref_corner is not None and left_ref_corner is not None:
        ref_vector = np.array(left_ref_corner) - np.array(right_ref_corner)
        ref_unit_vector = ref_vector / np.linalg.norm(ref_vector)
        #find normal to the ref_unit_vector (rotate by 90 degrees)
        ref_normal_vector = np.array([-ref_unit_vector[1], ref_unit_vector[0]])
        #find angle of ref_normal_vector with y axis
        angle = np.arctan2(ref_normal_vector[1], ref_normal_vector[0]) + np.pi / 2
    else:
        print("Warning: Could not find reference corners. Using initial angle estimation.")

    #recalculate center_x and center_y using the right reference corner and left reference corner
    #the center should be 0.579617834395 * distance from right reference corner to left reference corner away from 
    #the left reference corner in the direction of the unit vector from left reference corner to right reference corner
    if right_ref_corner is not None and left_ref_corner is not None:
            # 1. Calculate the vector from left to right
            # Vector = Target - Source
            vec_x = right_ref_corner[0] - left_ref_corner[0]
            vec_y = right_ref_corner[1] - left_ref_corner[1]
            
            # 2. Calculate the total distance between them
            dist = np.sqrt(vec_x**2 + vec_y**2)
            
            # 3. Find the unit vector (direction only)
            if dist > 0:
                u_x = vec_x / dist
                u_y = vec_y / dist
                #calculate normal vector to the unit vector (rotate by 90 degrees)
                n_x = -u_y
                n_y = u_x
                
                # 4. Calculate the offset distance based on your ratio
                # Ratio: 0.579617834395
                offset_dist_x = 0.420382165605 * dist
                offset_dist_y = 0.15923566879 * dist * 0.5
                
                # 5. New center = Left Corner + (Direction * Offset)
                center_x = left_ref_corner[0] + (u_x * offset_dist_x) + (n_x * offset_dist_y)
                center_y = left_ref_corner[1] + (u_y * offset_dist_x) + (n_y * offset_dist_y)

    #recalculate side_length using the distance between the right reference corner and left reference corner
    if right_ref_corner is not None and left_ref_corner is not None:
        side_length = np.sqrt((right_ref_corner[0] - left_ref_corner[0])**2 + (right_ref_corner[1] - left_ref_corner[1])**2)
        side_length = 0.15923566879 * side_length * 1.007

    scores = {}

    # Iterate through the dictionary in pairs
    # range(0, len, 2) gives us 0, 2, 4...
    for i in range(0, len(group_positions), 2):
        # Get the raw local coordinates (tuples)
        raw_a = group_positions[i]
        raw_b = group_positions[i+1]

        # Correct way: Multiply the individual elements of the tuple by side_length/10
        # This scales the local coordinates
        scale = side_length
        loc_a = (raw_a[0] * scale, raw_a[1] * scale)
        loc_b = (raw_b[0] * scale, raw_b[1] * scale)

        # Convert to global rotated image coordinates
        # x were fliped b/c the usaf target is fliped
        # y were fliped b/c the screen coordinate system
        pt_a = get_rotated_pt(center_x, center_y, -loc_a[0], -loc_a[1], angle)
        pt_b = get_rotated_pt(center_x, center_y, -loc_b[0], -loc_b[1], angle)

        # Create a mask for the line
        mask = np.zeros_like(gray, dtype=np.uint8)
        cv2.line(mask, pt_a, pt_b, 255, 4)
        
        # Get pixel values along the line from normalized_gray
        line_pixels = normalized_gray[mask > 0]
        
        if len(line_pixels) > 0:
            brightest = np.max(line_pixels)
            darkest = np.min(line_pixels)
            diff = brightest - darkest
            score = diff if diff > 0.2 else 0
        else:
            score = 0
        
        group = i // 2
        scores[group] = score

        # Draw the line on the image
        cv2.line(img, pt_a, pt_b, (0, 0, 255), 4) 
        

    # Display the result
    cv2.circle(img, right_ref_corner, 8, (255, 0, 255), -1)  # magenta for right reference corner
    cv2.circle(img, left_ref_corner, 8, (255, 255, 0), -1)  # cyan for left reference corner
    #draw region of interest for reference corner
    right_region_size_px = int((1.0/5.0) * side_length)
    left_region_size_px = int((1.0/5.0) * side_length)
    #region centered at the transformed and rotated group_position[50] and group_position[51] coordinates
    #cast to int for cv2.rectangle
    right_scaled_pt = (int(group_positions[50][0] * side_length), int(group_positions[50][1] * side_length))
    left_scaled_pt = (int(group_positions[51][0] * side_length), int(group_positions[51][1] * side_length))
    right_rotated_pt = get_rotated_pt(center_x, center_y, -right_scaled_pt[0], -right_scaled_pt[1], angle)
    left_rotated_pt = get_rotated_pt(center_x, center_y, -left_scaled_pt[0], -left_scaled_pt[1], angle)
    cv2.rectangle(img, (int(right_rotated_pt[0] - right_region_size_px), int(right_rotated_pt[1] - right_region_size_px)),                  (int(right_rotated_pt[0] + right_region_size_px), int(right_rotated_pt[1] + right_region_size_px)), (255, 0, 255), 2)
    cv2.rectangle(img, (int(left_rotated_pt[0] - left_region_size_px), int(left_rotated_pt[1] - left_region_size_px)),                  (int(left_rotated_pt[0] + left_region_size_px), int(left_rotated_pt[1] + left_region_size_px)), (255, 255, 0), 2)
    
    #mark the center of the square with a blue circle
    cv2.circle(img, (int(center_x), int(center_y)), 8, (255, 0, 0), -1)  # blue for center of the square
    
    
    cv2.namedWindow("Scanlines", cv2.WINDOW_NORMAL)
    cv2.imshow("Scanlines", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return scores


def find_best_focus_group(scores_list):
    # We need at least 2 scores to compare
    if len(scores_list) < 2:
        return 0

    for i in range(1, len(scores_list)):
        # If the score starts going UP, the previous index was the "bottom"
        if scores_list[i] > scores_list[i-1] * 1.1 or scores_list[i] < 0.2:
            return i - 1
            
    # If it never goes up, the last element is the minimum
    return len(scores_list) - 1



# Process images
images = [
    'af_Z61_670_175208_20260227_175208.png',
    'af_Z62_070_183718_20260227_183719.png',
    'af_Z61_870_175210_20260227_175210.png'
]




for image_path in images:
    corners = find_square_corners(image_path)
    if corners is not None:
        # Calculate focus scores
        scores = calculate_focus_scores(image_path, corners)
        if scores is not None:
            print(f"Scores for {image_path}: {scores}")
        else:
            print(f"Failed to calculate scores for {image_path}")

        # find the index in the scores where the descending order of scores changes to ascending order, 
        # that is the index of the best focus group
        scores_list = [scores[i] for i in range(len(scores))]
        best_focus_group = find_best_focus_group(scores_list)
        print(f"Best focus group for {image_path}: {best_focus_group}")

    else:
        print(f"No square detected for {image_path}")
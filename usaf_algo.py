import cv2
import numpy as np



#------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Coordinate Definitions:
# usaf coordinate system: origin is the center of the square in usaf target, axis align with edge of square and 1.0 unit = side length of the square
#                         negative y axis point toward center of the target, and positive x axis point toward the group with higher group number
# standard coordinate system: origin at the bottom left corner of the image, positive y axis point upward, positive x axis point rightward, unit in pixel
# screen coordinate system: origin at the top left corner of the image, positive y axis point downward, positive x axis point rightward, unit in pixel
#------------------------------------------------------------------------------------------------------------------------------------------------------------------



#anchor coordinate for performing secondary coordinate calibration
#debug const
DEBUG_MODE = False
PREVIEW_MODE = True
left_ref_coord = (2.64, 0.5)
right_ref_coord = (-3.64, 0.5)

# Process images
images = [
    'af_Z61_670_175208_20260227_175208.png',
    'af_Z62_070_183718_20260227_183719.png',
    'af_Z61_870_175210_20260227_175210.png'
]

# scanline definition in usaf coordinate
# Define points as (local_x, local_y) relative to the center of the square, in units of side_length
# Every two points (0&1, 2&3, etc.) will form one line segment for scoring
g2_x = -3.2
g3_x = 2.5
g4_x = -0.56
g5_x = 0.87
g6_x = 0.11
group_positions = {
    
    0: (g2_x, 0.35),            1: (g2_x, -0.37),
    2: (g2_x, -1.31),           3: (g2_x, -1.96),
    4: (g2_x, -2.8),            5: (g2_x, -3.40),
    
    6: (g3_x, 0.43),            7: (g3_x, 0.01),
    8: (g3_x, -0.5),            9: (g3_x, -0.88),
    10: (g3_x, -1.37),          11: (g3_x, -1.70),
    12: (g3_x, -2.08-0.05),     13: (g3_x, -2.38-0.05),
    14: (g3_x, -2.73-0.05),     15: (g3_x, -3.01-0.05),
    16: (g3_x, -3.32-0.07),     17: (g3_x, -3.57-0.07),
    
    18: (0.79, -3.15-0.057),    19: (0.79, -3.37-0.057),
    20: (g4_x, -1.84-0.03),     21: (g4_x, -2.04-0.03),
    22: (g4_x, -2.26-0.05),     23: (g4_x, -2.44-0.05),
    24: (g4_x, -2.63-0.05),     25: (g4_x, -2.79-0.05),
    26: (g4_x, -2.97-0.05),     27: (g4_x, -3.1-0.05),
    28: (g4_x, -3.26-0.05),     29: (g4_x, -3.39-0.05),

    30: (g5_x, -1.838-0.03),    31: (g5_x, -1.944-0.03),
    32: (g5_x, -2.072-0.038),   33: (g5_x, -2.168-0.038),
    34: (g5_x, -2.277-0.04),    35: (g5_x, -2.365-0.04),
    36: (g5_x, -2.468-0.037),   37: (g5_x, -2.538-0.044),
    38: (g5_x, -2.64-0.04),     39: (g5_x, -2.696-0.04),
    40: (g5_x, -2.782-0.045),   41: (g5_x, -2.836-0.045),
    
    42: (0.44, -2.78-0.01),     43: (0.44, -2.82-0.01),
    44: (g6_x, -2.453),         45: (g6_x, -2.49),
    46: (g6_x, -2.557),         47: (g6_x, -2.59),
    48: (g6_x, -2.648),         49: (g6_x, -2.681),
    50: (g6_x-0.003, -2.735),   51: (g6_x-0.003, -2.755),
    52: (g6_x-0.005, -2.81),    53: (g6_x-0.005, -2.83),
}

#score table to covert score to group and element number
score_table = {
    0: [2,2],
    1: [2,3],
    2: [2,4],
    3: [3,1],
    4: [3,2],
    5: [3,3],
    6: [3,4],
    7: [3,5],
    8: [3,6],
    9: [4,1],
    10: [4,2],
    11: [4,3],
    12: [4,4],
    13: [4,5],
    14: [4,6],
    15: [5,1],
    16: [5,2],
    17: [5,3],
    18: [5,4],
    19: [5,5],
    20: [5,6],
    21: [6,1],
    22: [6,2],
    23: [6,3],
    24: [6,4],
    25: [6,5],
    26: [6,6]
}



def find_square_corners(gray):
    '''
    find the square in the usaf target for initial coordinate calibration, 
    return the corners in standard coordinates (x, y)
    '''

    # RGB color of gray
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
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

        if DEBUG_MODE:
            print("Detected Corners:\n", corners)
            # Draw for visual confirmation
            for (x, y) in corners:
                cv2.circle(img, (x, y), 8, (0, 255, 0), -1)
            cv2.drawContours(img, [square_corners], -1, (255, 0, 0), 3)
            
            cv2.namedWindow("Success", cv2.WINDOW_NORMAL) 
            cv2.imshow("Success", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        return corners
    else:
        # Debugging: show the thresholded image if it fails
        print("Square not detected. Showing thresholded image for debugging...")
        cv2.imshow("Debug Thresh", thresh)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return None



def get_rotated_pt(cx, cy, local_x, local_y, angle):
    '''
    find a rotated point at a certain angle and distance from a center point
    '''

    # Standard rotation formula
    rx = cx + local_x * np.cos(angle) - local_y * np.sin(angle)
    ry = cy + local_x * np.sin(angle) + local_y * np.cos(angle)
    return (int(rx), int(ry))



def find_white_corner_in_region(gray, center_x, center_y, angle, side_length, region_center, region_size):
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
    # translate and rotate
    region_center_img = get_rotated_pt(center_x, center_y, -region_center_scaled[0], -region_center_scaled[1], angle)
    #calculate the region size in pixels
    region_size_px = region_size * side_length

    if DEBUG_MODE:
        # Debug: Draw the region on the image
        debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(debug_img, (int(region_center_img[0] - region_size_px), int(region_center_img[1] - region_size_px)),                   (int(region_center_img[0] + region_size_px), int(region_center_img[1] + region_size_px)), (0, 255, 0), 2)
        cv2.circle(debug_img, region_center_img, 5, (0, 0, 255), -1)
        cv2.namedWindow("Debug Region", cv2.WINDOW_NORMAL)
        cv2.imshow("Debug Region", debug_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

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
        
        # Convert back to screen coordinates
        corner_img = (corner_local[1] + x1, corner_local[0] + y1)
        # convert back to standard coordinates
        corner_img = (corner_img[0], gray.shape[0] - 1 - corner_img[1])
        
        return corner_img
    else:
        return None



def find_target_orientation(gray, center_x, center_y, unit_vector, side_length):
    '''
    calculate the orientation of the target by comparing the average of the scanline element
    '''
    normal_vector = np.array([-unit_vector[1], unit_vector[0]])
    normal_vector = normal_vector / np.linalg.norm(normal_vector)

    # The marking of orientation are based on the orientation where
    # the top left is the top direction
    # the top right is the right direction
    # the bottom right is the bottom direction
    # the bottom left is the left direction
    scanline_length = 0.7 * side_length
    scanline_start = np.zeros((4, 2))
    scanline_start[1] = (center_x + scanline_length * unit_vector[0], center_y + scanline_length * unit_vector[1])        #right
    scanline_start[3] = (center_x - scanline_length * unit_vector[0], center_y - scanline_length * unit_vector[1])        #left
    scanline_start[0] = (center_x + scanline_length * normal_vector[0], center_y + scanline_length * normal_vector[1])    #top
    scanline_start[2] = (center_x - scanline_length * normal_vector[0], center_y - scanline_length * normal_vector[1])    #bottom
    scanline_length = 6 * side_length
    scanline_end = np.zeros((4, 2))
    scanline_end[1] = (center_x + scanline_length * unit_vector[0], center_y + scanline_length * unit_vector[1])        #right
    scanline_end[3] = (center_x - scanline_length * unit_vector[0], center_y - scanline_length * unit_vector[1])        #left
    scanline_end[0] = (center_x + scanline_length * normal_vector[0], center_y + scanline_length * normal_vector[1])    #top
    scanline_end[2] = (center_x - scanline_length * normal_vector[0], center_y - scanline_length * normal_vector[1])    #bottom

    h, w = gray.shape[:2]
    center = np.array([center_x, center_y])

    # Calculate how much we need to scale the line to hit each boundary
    for i in range(len(scanline_end)):
        pt = scanline_end[i]
        diff = pt - center
        
        # Calculate how much we need to scale the line to hit each boundary
        # We only care about boundaries the line is actually crossing
        t = 1.0
        
        if pt[0] < 0:      t = min(t, -center[0] / diff[0])
        if pt[0] >= w:     t = min(t, (w - 1 - center[0]) / diff[0])
        if pt[1] < 0:      t = min(t, -center[1] / diff[1])
        if pt[1] >= h:     t = min(t, (h - 1 - center[1]) / diff[1])
        
        # Apply the single best ratio to both X and Y simultaneously
        scanline_end[i] = center + t * diff

    # convert to screen coordinates and int type
    scanline_start[:, 1] = gray.shape[0] - scanline_start[:, 1] - 1
    scanline_start = scanline_start.astype(int)
    scanline_end[:, 1] = gray.shape[0] - scanline_end[:, 1] - 1
    scanline_end = scanline_end.astype(int)

    if DEBUG_MODE:
        window_name = "Scans"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 800)

        # Convert grayscale to BGR so we can draw in color
        img_copy = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) 

        for i in range(scanline_end.shape[0]):
            end_point = tuple(scanline_end[i])
            start_point = tuple(scanline_start[i])
            # Now (0,0,255) will actually show up as Red
            cv2.line(img_copy, start_point, end_point, (0,0,255), 4)

        cv2.imshow(window_name, img_copy)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    average = np.zeros(4)
    for i in range(scanline_end.shape[0]):
        end_point = tuple(scanline_end[i])
        start_point = tuple(scanline_start[i])
        # Create a mask for the line
        mask = np.zeros_like(gray, dtype=np.uint8)
        cv2.line(mask, start_point, end_point, 255, 4)
        cv2.line(mask, start_point, end_point, 255, 4)
        # Get pixel values along the line from normalized_gray
        line_pixels = gray[mask > 0]
        # calculate average grayscale value along the line
        average[i] = np.mean(line_pixels)

    # find the index of the minimum value
    min_index = np.argmin(average)
    if DEBUG_MODE:
        print(f"Minimum index: {min_index}")
    # return the corresponding orientation
    return min_index



def coordinate_calibration(gray, corners):
    '''
    Calibrates the coordinate system using the corners of the square
    '''
    # Initial coordinate calibration using the corners of the square
    corners = np.array(corners)
    min_x = np.min(corners[:, 0])
    max_x = np.max(corners[:, 0])
    min_y = np.min(corners[:, 1])
    max_y = np.max(corners[:, 1])
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    side_length = np.sqrt((corners[0][0] - corners[1][0])**2 + (corners[0][1] - corners[1][1])**2)  # approximate side length
    top_corner = corners[np.argmax(corners[:, 1])]
    left_corner = corners[np.argmin(corners[:, 0])]
    right_corner = corners[np.argmax(corners[:, 0])]
    bottom_corner = corners[np.argmin(corners[:, 1])]
    #find unit vector that point from left corner to top corner
    unit_vector = (top_corner - left_corner) / np.linalg.norm(top_corner - left_corner)
    #find angle of unit vector with y axis, negate because the screen coordinate system is flipped
    angle = -np.arctan2(unit_vector[1], unit_vector[0])



    # find orientation of the target
    orientation = find_target_orientation(gray, center_x, center_y, unit_vector, side_length)
    angle = angle + orientation * np.pi / 2



    #Seconary coordinate calibration using the reference corners
    # left and right ref corner are in standard coordinates 
    right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, right_ref_coord, 1.0/5.0)
    left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, left_ref_coord, 1.0/5.0)
    ref_vector = np.array(right_ref_corner) - np.array(left_ref_corner)
    ref_unit_vector = ref_vector / np.linalg.norm(ref_vector)
    ref_normal_vector = np.array([-ref_unit_vector[1], ref_unit_vector[0]])
    dist = np.sqrt(ref_vector[0]**2 + ref_vector[1]**2)
    #recalculate angle using the right reference corner and left reference corner
    if right_ref_corner is not None and left_ref_corner is not None:
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

        if DEBUG_MODE:
            print(f"Angle: {angle / np.pi * 180}")

        #recalculate center_x and center_y using the right reference corner and left reference corner
        #the center should be 0.579617834395 * distance from right reference corner to left reference corner away from 
        #the left reference corner in the direction of the unit vector from left reference corner to right reference corner
        if dist > 0:
            # Calculate the offset distance in usaf axis but standard scale based on ratio
            sum_length = left_ref_coord[0] + np.abs(right_ref_coord[0])
            offset_dist_x = left_ref_coord[0] * dist / sum_length
            offset_dist_y = 1.00 * dist * 0.5 / sum_length
            center_x = left_ref_corner[0] + (ref_unit_vector[0] * offset_dist_x) - (ref_normal_vector[0] * offset_dist_y)
            center_y = left_ref_corner[1] + (ref_unit_vector[1] * offset_dist_x) - (ref_normal_vector[1] * offset_dist_y)
            # convert from standard coordinate back to screen coordinates
            center_y = gray.shape[0] - 1 - center_y

            #recalculate side_length using the distance between the right reference corner and left reference corner
            # evil magic scaling factor 1.007
            side_length = 1.00 * dist * 1.007 / sum_length

        return [center_x, center_y, angle, side_length, right_ref_corner, left_ref_corner]
    else:
        print("Warning: Could not find reference corners. Using initial angle estimation.")
        return None



def calculate_focus_scores(image_path):
    '''
    Calculate the focus scores for each group element based on the defined scanlines and the detected corners for coordinate calibration.
    Return a ordered dictionary of scores for each group element, where the key is the group element number and the value is the focus score.
    '''
    img = cv2.imread(image_path)
    if img is None:
        return None
    
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
    [center_x, center_y, angle, side_length, right_ref_corner, left_ref_corner] = coordinate_calibration(gray, corners)

    scores = {}
    # Iterate through the dictionary in pairs
    # range(0, len, 2) gives us 0, 2, 4...
    for i in range(0, len(group_positions), 2):
        # Get the raw usaf coordinates (tuples)
        raw_a = group_positions[i]
        raw_b = group_positions[i+1]

        # This scales the usaf coordinates to pixel scale
        scale = side_length
        loc_a = (raw_a[0] * scale, raw_a[1] * scale)
        loc_b = (raw_b[0] * scale, raw_b[1] * scale)

        # Convert from pixel usaf coordinate to screen coordinate
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

        scores[i // 2] = score
        # Draw the line on the image
        cv2.line(img, pt_a, pt_b, (0, 0, 255), 4) 
        


    if PREVIEW_MODE:
        # Display the result
        # convert the right reference corner and left reference corner from standard to screen coordinates
        right_ref_corner = (right_ref_corner[0], gray.shape[0] - right_ref_corner[1] - 1)
        left_ref_corner = (left_ref_corner[0], gray.shape[0] - left_ref_corner[1] - 1)
        cv2.circle(img, right_ref_corner, 8, (255, 0, 255), -1)  # magenta for right reference corner
        cv2.circle(img, left_ref_corner, 8, (255, 255, 0), -1)  # cyan for left reference corner
        # calculate region dimension and draw the region 
        right_region_size_px = int((1.0/5.0) * side_length)
        left_region_size_px = int((1.0/5.0) * side_length)
        # convert the right reference corner and left reference corner from usaf to screen coordinates, then draw the region around them,
        # cast to int for cv2.rectangle
        right_scaled_pt = (int(right_ref_coord[0] * side_length), int(right_ref_coord[1] * side_length))
        left_scaled_pt = (int(left_ref_coord[0] * side_length), int(left_ref_coord[1] * side_length))
        right_rotated_pt = get_rotated_pt(center_x, center_y, -right_scaled_pt[0], -right_scaled_pt[1], angle)
        left_rotated_pt = get_rotated_pt(center_x, center_y, -left_scaled_pt[0], -left_scaled_pt[1], angle)
        cv2.rectangle(img, (int(right_rotated_pt[0] - right_region_size_px), int(right_rotated_pt[1] - right_region_size_px)),                  (int(right_rotated_pt[0] + right_region_size_px), int(right_rotated_pt[1] + right_region_size_px)), (255, 0, 255), 2)
        cv2.rectangle(img, (int(left_rotated_pt[0] - left_region_size_px), int(left_rotated_pt[1] - left_region_size_px)),                  (int(left_rotated_pt[0] + left_region_size_px), int(left_rotated_pt[1] + left_region_size_px)), (255, 255, 0), 2)
        # mark the center of the square with a blue circle
        cv2.circle(img, (int(center_x), int(center_y)), 8, (255, 0, 0), -1)  # blue for center of the square
        
        cv2.namedWindow("Scanlines", cv2.WINDOW_NORMAL)
        cv2.imshow("Scanlines", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


    
    return scores



def find_best_focus_group(scores_list):
    '''
    Find the index in the scores where the descending order of scores changes to ascending order,
    or where the score drops below a certain threshold (e.g., 0.2), which indicates the best focus group.
    Return the corresponding group and element number from the score table.
    '''
    # We need at least 2 scores to compare
    if len(scores_list) < 2:
        print("Not enough scores to compare")
        return None

    for i in range(1, len(scores_list)):
        # If the score starts going UP, the previous index was the "bottom"
        if scores_list[i] > scores_list[i-1] * 1.1 or scores_list[i] < 0.2:
            # Return the score of the last group before it went up or dropped too low
            return score_table[i-1]  
        
    # If it never goes up, return first element
    print("No score goes up")
    return score_table[26]



def find_usaf_score(image_path):
    '''
    Find the usaf focus score for a given image path, which is the best focus group number 
    based on the defined scanlines and the detected corners for coordinate calibration.
    input: image path
    output: best focus group number and element number
    '''

    # Calculate focus scores
    scores = calculate_focus_scores(image_path)
    if scores is not None and DEBUG_MODE:
        print(f"Scores for {image_path}: {scores}")

    # find the index in the scores where the descending order of scores changes to ascending order, 
    # that is the index of the best focus group
    scores_list = [scores[i] for i in range(len(scores))]
    best_focus_group = find_best_focus_group(scores_list)
    print(f"Best focus group for {image_path}: {best_focus_group[0]}, element {best_focus_group[1]}")
    return best_focus_group





for image_path in images:
    find_usaf_score(image_path)
    
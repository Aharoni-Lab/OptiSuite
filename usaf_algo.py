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
DEBUG_MODE = True
PREVIEW_MODE = True
FLIPED_TARGET = False
#toggle subpixel refinement best for large target
SUBPIXEL = True
#first group number
G1 = 2


left_ref_coord = (2.64, 0.5)
right_ref_coord = (-3.64, 0.5)


# Global list to store all valid square polygons found during corner detection
valid_squares = []
retry_count = 0

# Process images
images = [
    # 'test_image_g4e4.png',
    # 'test_image_g6e6_copy.png',
    # 'test_image_g5e4.png',
    # 'test_image_g3e6.png',
    # 'test_image_g3e6_(1).png',
    # 'test_image_g6e1.png',
     'SingleWell.png'
    # 'harvardSetup_filterOnCube.bmp',
    # 'Image0001.bmp'
]

# scanline definition in usaf coordinate
# Define points as (local_x, local_y) relative to the center of the square, in units of side_length
# Every two points (0&1, 2&3, etc.) will form one line segment for scoring
g2_x = -3.2
g3_x = 2.5
g4_x = -0.56
g5_x = 0.87
g6_x = 0.112
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
    48: (g6_x, -2.654),         49: (g6_x, -2.681),
    50: (g6_x-0.003, -2.735),   51: (g6_x-0.003, -2.755),
    52: (g6_x-0.005, -2.812),    53: (g6_x-0.005, -2.83),
}

#score table to covert score to group and element number
score_table = {
    0: [G1,2],
    1: [G1,3],
    2: [G1,4],
    3: [G1+1,1],
    4: [G1+1,2],
    5: [G1+1,3],
    6: [G1+1,4],
    7: [G1+1,5],
    8: [G1+1,6],
    9: [G1+2,1],
    10: [G1+2,2],
    11: [G1+2,3],
    12: [G1+2,4],
    13: [G1+2,5],
    14: [G1+2,6],
    15: [G1+3,1],
    16: [G1+3,2],
    17: [G1+3,3],
    18: [G1+3,4],
    19: [G1+3,5],
    20: [G1+3,6],
    21: [G1+4,1],
    22: [G1+4,2],
    23: [G1+4,3],
    24: [G1+4,4],
    25: [G1+4,5],
    26: [G1+4,6]
}



def is_valid_square(approx, gray, white_threshold=200, angle_tolerance=5, side_ratio_tolerance=1.1):
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
    
    # At least 70% of interior should be white
    if white_ratio < 0.7:
        return False
    
    return True



def find_square_corners(gray):
    '''
    find the square in the usaf target for initial coordinate calibration, 
    return the corners in standard coordinates (x, y)
    '''

    global valid_squares
    valid_squares = []  # Reset the list for each new image

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

    best_square_corners = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500: # Ignore tiny noise
            continue
            
        peri = cv2.arcLength(cnt, True)
        # Increase the 0.02 factor if it still fails (e.g., 0.04)
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

        # Look for 4-sided polygons that form valid squares
        if len(approx) == 4:
            # Check if this polygon meets the square criteria
            if is_valid_square(approx, gray):
                valid_squares.append(approx)  # Store in global list
                
                # Keep track of the largest valid square
                if area > best_area:
                    best_area = area
                    best_square_corners = approx

    if best_square_corners is not None:
        # Create a copy because the valid squares list is by ref
        corners = best_square_corners.reshape(-1, 2).copy()

        if DEBUG_MODE:
            print("Detected Corners:\n", corners)
            # Draw for visual confirmation
            for (x, y) in corners:
                cv2.circle(img, (x, y), 8, (0, 255, 0), -1)
            cv2.drawContours(img, [best_square_corners], -1, (255, 0, 0), 3)
            
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
    flip = -1 if FLIPED_TARGET else 1
    region_center_img = get_rotated_pt(center_x, center_y, flip * region_center_scaled[0], -region_center_scaled[1], angle)
    #calculate the region size in pixels
    region_size_px = max(region_size * side_length, 13)

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
    
    # Apply Shi-Tomasi corner detection on white pixels
    corners_shi_tomasi = cv2.goodFeaturesToTrack(region.astype(np.uint8), 20, 0.01, 4)
    # Subpixel refinement if needed
    if region.shape[0] > 30 and region.shape[1] > 30 and SUBPIXEL:             # If the region is small, skip subpixel refinement
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
        cv2.cornerSubPix(region.astype(np.uint8), corners_shi_tomasi, (10, 10), (-1, -1), criteria)
    copy_corners = corners_shi_tomasi.copy()

    if len(corners_shi_tomasi) > 0:
        # Return the corner closest to the preference direction
        corner_x = corners_shi_tomasi[:, 0, 0]  # x-coordinates
        corner_y = corners_shi_tomasi[:, 0, 1]  # y-coordinates
        print("x: ", corner_x, "y: ", corner_y)

        if prefer_dir == 0:                     #prefer center
            corner_dist = np.sqrt((corner_x - region.shape[1] / 2) ** 2 + (corner_y - region.shape[0] / 2) ** 2)
            search_idx = np.argmin(corner_dist)
        elif prefer_dir == 3:                   #prefer top
            search_idx = np.argmin(corner_y)
        elif prefer_dir == 7:                   #prefer bottom
            search_idx = np.argmax(corner_y)
        elif prefer_dir == 1:                   #prefer left
            search_idx = np.argmin(corner_x)
        elif prefer_dir == 5:                   #prefer right
            search_idx = np.argmax(corner_x)
        corner_local = corners_shi_tomasi[search_idx, 0]
        print("index: ", search_idx, "corner: ", corner_local)

        if DEBUG_MODE:
            print("prefer_dir: ", prefer_dir)
            # Create a BGR version of the crop for color drawing
            debug_img = cv2.cvtColor(region, cv2.COLOR_GRAY2BGR)
            i_ctr = 0
            for corner in copy_corners:
                if i_ctr != search_idx:
                    cv2.circle(debug_img, (int(corner[0][0]), int(corner[0][1])), 1, (0, 0, 255), -1)
                i_ctr += 1
                print(f"Corner {i_ctr}: ({corner[0][0]}, {corner[0][1]})")
            cv2.circle(debug_img, (int(corner_local[0]), int(corner_local[1])), 1, (0, 200, 0), -1)
            cv2.namedWindow("Debug Region", cv2.WINDOW_NORMAL)
            cv2.imshow("Debug Region", debug_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        
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

    if DEBUG_MODE:
        # Convert grayscale to BGR so we can draw in color
        img_copy = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) 

        for i in range(scanline_end.shape[0]):
            end_point = tuple(scanline_end[i])
            start_point = tuple(scanline_start[i])
            # Now (0,0,255) will actually show up as Red
            cv2.line(img_copy, start_point, end_point, (0,0,255), 4)

        cv2.namedWindow("Scans", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Scans", 800, 800)
        cv2.imshow("Scans", img_copy)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

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
    side_length = np.linalg.norm(corners[0] - corners[1])
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
    flip = -1 if FLIPED_TARGET else 1
    right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, right_ref_coord, 1.0/5.0, ((orientation) * 2 + 2 - flip) % 8)
    left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, left_ref_coord, 1.0/5.0, ((orientation) * 2 + 2 + flip) % 8)

    if right_ref_corner is not None and left_ref_corner is not None:
        ref_vector = np.array(right_ref_corner) - np.array(left_ref_corner)
        ref_unit_vector = ref_vector / np.linalg.norm(ref_vector)
        flip = 1 if FLIPED_TARGET else -1
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
        return None



def calculate_focus_scores(image_path):
    '''
    Calculate the focus scores for each group element based on the defined scanlines and the detected corners for coordinate calibration.
    Return a ordered dictionary of scores for each group element, where the key is the group element number and the value is the focus score.
    '''
    img = cv2.imread(image_path)
    if img is None:
        return None
    
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

    # Coordinate calibration
    global retry_count
    retry_count = 0
    retry_condition = False
    scores = {}

    while retry_count < valid_squares.__len__():
        scores = {}  # reset scores before retrying
        img = clean_img.copy()
        retry_condition = False

        corners = valid_squares[retry_count].reshape(-1, 2)
        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        output_list = coordinate_calibration(gray, corners)

        if output_list is None:
            retry_count = retry_count + 1
            if DEBUG_MODE:
                print(f"Retrying coordinate calibration with next best square... Attempt {retry_count}")
            continue

        [center_x, center_y, angle, side_length, right_ref_corner, left_ref_corner] = output_list

        

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
            flip = -1 if FLIPED_TARGET else 1
            pt_a = get_rotated_pt(center_x, center_y, flip * loc_a[0], -loc_a[1], angle)
            pt_b = get_rotated_pt(center_x, center_y, flip * loc_b[0], -loc_b[1], angle)

            #if the pts fall outside the image, retry with the next best square
            if pt_a[0] < 0 or pt_a[0] >= gray.shape[1] or pt_a[1] < 0 or pt_a[1] >= gray.shape[0] or \
            pt_b[0] < 0 or pt_b[0] >= gray.shape[1] or pt_b[1] < 0 or pt_b[1] >= gray.shape[0]:
                retry_condition = True
                break

            # Create a mask for the line
            mask = np.zeros_like(gray, dtype=np.uint8)
            cv2.line(mask, pt_a, pt_b, 255, 4)
            # Get pixel values along the line from normalized_gray
            line_pixels = normalized_gray[mask > 0]
            
            if len(line_pixels) > 0:
                brightest = np.max(line_pixels)
                darkest = np.min(line_pixels)
                diff = brightest - darkest
                score = diff
            else:
                score = 0

            scores[i // 2] = score
            # Draw the line on the image
            cv2.line(img, pt_a, pt_b, (0, 0, 255), 4)

        if not retry_condition:
            break

        retry_count = retry_count + 1
        if DEBUG_MODE:
            print(f"Found out image scanline, Retrying with next best square... Attempt {retry_count}")

    if retry_count == valid_squares.__len__():
        print(f"Failed to find valid square after {retry_count} attempts")
        scores = {}  # reset scores
        raise Exception("Failed to find valid square for coordinate calibration")
    


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
        flip = -1 if FLIPED_TARGET else 1
        right_rotated_pt = get_rotated_pt(center_x, center_y, flip * right_scaled_pt[0], -right_scaled_pt[1], angle)
        left_rotated_pt = get_rotated_pt(center_x, center_y, flip * left_scaled_pt[0], -left_scaled_pt[1], angle)
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
    try:
        scores = calculate_focus_scores(image_path)
    except Exception as e:
        print(f"Failed to calculate focus scores for {image_path}: {e}")
        return None
    
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
    
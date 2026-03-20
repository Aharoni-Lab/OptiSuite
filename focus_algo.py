import cv2
import numpy as np


# Define points as (local_x, local_y) relative to the center
# Every two points (0&1, 2&3, etc.) will form one line
g2_x = -3.5
g3_x = 2.5
group_positions = {
    0: (g2_x, 0.5),     1: (g2_x, -0.5),
    2: (g2_x, -1.2),    3: (g2_x, -2.1),
    4: (g2_x, -2.7),    5: (g2_x, -3.5),
    
    6: (g3_x, 0.5),     7: (g3_x, -0.1),
    8: (g3_x, -0.4),    9: (g3_x, -1),
    10: (g3_x, -1.2),    11: (g3_x, -1.8),
    12: (g3_x, -2.0),    13: (g3_x, -2.5),
    14: (g3_x, -2.65),    15: (g3_x, -3.1),
    16: (g3_x, -3.25),    17: (g3_x, -3.65),
    
    # 18: (g2_x, -2.7),    19: (g2_x, -3.5),
    # 20: (g2_x, -2.7),    21: (g2_x, -3.5),
    # 22: (g2_x, -2.7),    23: (g2_x, -3.5),
    # 24: (g2_x, -2.7),    25: (g2_x, -3.5),
    # 26: (g2_x, -2.7),    27: (g2_x, -3.5),
    # 28: (g2_x, -2.7),    29: (g2_x, -3.5),
    
    # 30: (g2_x, -2.7),    31: (g2_x, -3.5),
    # 32: (g2_x, -2.7),    33: (g2_x, -3.5),
    # 34: (g2_x, -2.7),    35: (g2_x, -3.5),
    # 36: (g2_x, -2.7),    37: (g2_x, -3.5),
    # 38: (g2_x, -2.7),    39: (g2_x, -3.5),
    # 40: (g2_x, -2.7),    41: (g2_x, -3.5),
    
    # 42: (g2_x, -2.7),    43: (g2_x, -3.5),
    # 44: (g2_x, -2.7),    45: (g2_x, -3.5),
    # 46: (g2_x, -2.7),    47: (g2_x, -3.5),
    # 48: (g2_x, -2.7),    49: (g2_x, -3.5),
    # 50: (g2_x, -2.7),    51: (g2_x, -3.5),
    # 52: (g2_x, -2.7),    53: (g2_x, -3.5),
    
    # 54: (g2_x, -2.7),    55: (g2_x, -3.5),
    # 56: (g2_x, -2.7),    57: (g2_x, -3.5),
    # 58: (g2_x, -2.7),    59: (g2_x, -3.5),
    # 60: (g2_x, -2.7),    61: (g2_x, -3.5),
    # 62: (g2_x, -2.7),    63: (g2_x, -3.5),
    # 64: (g2_x, -2.7),    65: (g2_x, -3.5),

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
        cv2.line(mask, pt_a, pt_b, 255, 2)
        
        # Get pixel values along the line from normalized_gray
        line_pixels = normalized_gray[mask > 0]
        
        if len(line_pixels) > 0:
            brightest = np.max(line_pixels)
            darkest = np.min(line_pixels)
            diff = brightest - darkest
            score = 1 if diff > 0.2 else 0
        else:
            score = 0
        
        group = i // 2
        scores[group] = score

        # Draw the line on the image
        cv2.line(img, pt_a, pt_b, (0, 0, 255), 2) 
        

    # Display the result
    cv2.namedWindow("Scanlines", cv2.WINDOW_NORMAL)
    cv2.imshow("Scanlines", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    scores = {}
    return scores

# Process images
images = [
    'screenshots/autofocus/run_68b219a484_20260227/cam1/af_Z62_070_183718_20260227_183719.png',
    'af_z59_880_cam1_VEN-505-36U3M-M01_20260227_163955.png'
]

for image_path in images:
    corners = find_square_corners(image_path)
    if corners is not None:
        scores = calculate_focus_scores(image_path, corners)
        if scores is not None:
            print(f"Scores for {image_path}: {scores}")
        else:
            print(f"Failed to calculate scores for {image_path}")
    else:
        print(f"No square detected for {image_path}")
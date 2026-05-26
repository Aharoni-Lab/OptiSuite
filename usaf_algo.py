import cv2
import numpy as np
import math
import matplotlib.pyplot as plt
from pathlib import Path
from yolo_model import extract_yolo_detections, visualize_detections, classify_number, count_4pts_pattern
from scipy.signal import savgol_filter
import random



#------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Coordinate Definitions:
# usaf coordinate system: origin is the center of the square in usaf target, axis align with edge of square and 1.0 unit = side length of the square
#                         negative y axis point toward center of the target, and positive x axis point toward the group with higher group number
# standard coordinate system: origin at the bottom left corner of the image, positive y axis point upward, positive x axis point rightward, unit in pixel
# screen coordinate system: origin at the top left corner of the image, positive y axis point downward, positive x axis point rightward, unit in pixel
#------------------------------------------------------------------------------------------------------------------------------------------------------------------



#debug const
DEBUG_MODE = False              # debug log + photo
PREVIEW_MODE = False             # overview photo
YOLO_DETECT = False              # yolo detection
GRADIENT_MIN = False
GRADIENT_PLOT_ENABLE = False       # visualize selected scanline intensity + gradient
GRADIENT_PLOT_GROUP = 6            # group to inspect when GRADIENT_PLOT_ENABLE is True
GRADIENT_PLOT_ELEMENT = 5          # element to inspect when GRADIENT_PLOT_ENABLE is True
GRADIENT_PLOT_ORIENTATION = "both" # "vertical", "horizontal", "both"
FLIPED_TARGET = True           # true if target is fliped
G1 = 2                          # first group number

SUBPIXEL = True                 # subpixel refinement for corner detection best for large target
RETRY_OUTER = False              # if only inner corner detected, expand the scanline to outer target
RETRY_OFF_IMAGE = False         # if any scanline goes out of image, retry with next best square
AUTO_ADJUST = False             # shorten the scanline until the color on the two point are white (above ADJUST_THRESH)
ADJUST_THRESH = 0.7             # white threshold, between 0 and 1 of the normalzed grayscale value
FOUR_KP = False                  # use four reference corners to calibrate the target

CORNER_METHOD = "threshold"     # "threshold", "default", method to detect the corner
SCORE_METHOD = "mean"           # "mean", "min", "max", "raw", method to merge the score from horizational and vertical scanlines
CROPED_WINDOW_RETRY = False     # if the corner detection window is off image, retry with next best square

INITIAL_ANGLE = 0

#anchor coordinate for performing secondary coordinate calibration
top_left_ref_coord = (2.64, 0.5)
top_right_ref_coord = (-3.64, 0.5)
low_left_ref_coord = (2.39,-5.89)
low_right_ref_coord = (-3.57,-5.88)

zoom_box_coord = (0.27,-2.668)
squ_scan_coord1 = (0.3, 0.6)
squ_scan_coord2 = (0.3,-2.6)

left_num_coord1 = (-2.43, 1.03)
right_num_coord1 = (1.92, 1.05)
left_num_coord2 = (-0.35, -1.72)
right_num_coord2 = (0.72, -1.73)
left_num_coord3 = (0.148, -2.416)
right_num_coord3 = (0.426, -2.411)


# Global list to store all valid square polygons found during corner detection
valid_squares = []
retry_count = 0

# Process images
images = [
    'test_img/test_image_new.png',
    # 'test_img/test_image_g4e4.png',
    # 'test_img/test_image_g5e4.png',
    # 'test_img/af_Z59_370_183653_20260227_183653.png',
    # 'test_img/test_image_g3e6.png'
    # 'test_img/image.png',
    #'test_img/test_image_new.png'
    # 'test_img/image_g67only.png'
    # 'test_img/test_image_g6e6.png'
    # 'test_img/af_z59_880_cam1_VEN-505-36U3M-M01_20260227_163955.png',
    # 'test_img/Image0001.bmp',
    # 'test_img/Screenshot_2026-05-06_085659.png'
]

# scanline definition in usaf coordinate
# Define points as (local_x, local_y) relative to the center of the square, in units of side_length
# Every two points (0&1, 2&3, etc.) will form one line segment for scoring
g2_x = -3.2
g3_x = 2.5
g4_x = -0.56
g5_x = 0.87
g6_x = 0.112

g6y_scale = 1.027
g5y_scale = 1.023
g4y_scale = 1.026
g3y_scale = 1.03
g2y_scale = 1.03

g6x_scale = 0.922
g5x_scale = 1.00
g4x_scale = 1.13
g3x_scale = 1.015
g2x_scale = 1.06

g7x_offset = -0.01
g7y_offset = -0.08
g7y_scale = 1.019

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

    54: (0.3997 + g7x_offset, (-2.3382 + g7y_offset) * g7y_scale),                            55: (0.4274 + g7x_offset, (-2.3384 + g7y_offset) * g7y_scale),
    56: (0.4097 + g7x_offset, (-2.3914 + g7y_offset) * g7y_scale),                            57: (0.4337 + g7x_offset, (-2.3912 + g7y_offset) * g7y_scale),
    58: (0.4158 + g7x_offset, (-2.4394 + g7y_offset) * g7y_scale),                            59: (0.438 + g7x_offset, (-2.4398 + g7y_offset) * g7y_scale),
    60: (0.4226 + g7x_offset, (-2.4828 + g7y_offset) * g7y_scale),                            61: (0.443 + g7x_offset, (-2.4832 + g7y_offset) * g7y_scale),
    62: (0.4294 + g7x_offset, (-2.522 + g7y_offset) * g7y_scale),                             63: (0.4462 + g7x_offset, (-2.5223 + g7y_offset) * g7y_scale),
    64: (0.4352 + g7x_offset, (-2.557 + g7y_offset) * g7y_scale),                             65: (0.4493 + g7x_offset, (-2.557 + g7y_offset) * g7y_scale),







    66: (-2.05 * g2x_scale, -0.003 * g2y_scale),      67: (-1.26 * g2x_scale, 0.005 * g2y_scale),
    68: (-2.19 * g2x_scale, -1.625 * g2y_scale),     69: (-1.51 * g2x_scale, -1.617 * g2y_scale),
    70: (-2.33 * g2x_scale, -3.04 * g2y_scale),      71: (-1.71 * g2x_scale, -3.046 * g2y_scale),

    72: (1.3 * g3x_scale, 0.2 * g3y_scale),          73: (1.75 * g3x_scale, 0.2 * g3y_scale),
    74: (1.435 * g3x_scale, -0.707 * g3y_scale),     75: (1.835 * g3x_scale, -0.707 * g3y_scale),
    76: (1.563 * g3x_scale, -1.498 * g3y_scale),     77: (1.92 * g3x_scale, -1.496 * g3y_scale),
    78: (1.68 * g3x_scale, -2.218 * g3y_scale),      79: (1.99 * g3x_scale, -2.213 * g3y_scale),
    80: (1.775 * g3x_scale, -2.85 * g3y_scale),      81: (2.062 * g3x_scale, -2.85 * g3y_scale),
    82: (1.867 * g3x_scale, -3.42 * g3y_scale),      83: (2.118 * g3x_scale, -3.422 * g3y_scale),

    84: (0.218 * g4x_scale, -3.234 * g4y_scale),     85: (0.444 * g4x_scale, -3.227 * g4y_scale),
    86: (-0.258 * g4x_scale, -1.929 * g4y_scale),    87: (-0.056 * g4x_scale, -1.931 * g4y_scale),
    88: (-0.289 * g4x_scale, -2.331 * g4y_scale),    89: (-0.112 * g4x_scale, -2.333 * g4y_scale),
    90: (-0.329 * g4x_scale, -2.692 * g4y_scale),    91: (-0.16 * g4x_scale, -2.691 * g4y_scale),
    92: (-0.351 * g4x_scale, -3.007 * g4y_scale),    93: (-0.211 * g4x_scale, -3.005 * g4y_scale),
    94: (-0.38 * g4x_scale, -3.29 * g4y_scale),      95: (-0.253 * g4x_scale, -3.289 * g4y_scale),

    96: (0.583 * g5x_scale, -1.8684 * g5y_scale),    97: (0.7 * g5x_scale, -1.87 * g5y_scale),
    98: (0.6256 * g5x_scale, -2.0996 * g5y_scale),   99: (0.72 * g5x_scale, -2.1 * g5y_scale),
    100: (0.65 * g5x_scale, -2.3 * g5y_scale),       101: (0.74 * g5x_scale, -2.3 * g5y_scale),
    102: (0.68 * g5x_scale, -2.48 * g5y_scale),      103: (0.76 * g5x_scale, -2.48 * g5y_scale),
    104: (0.71 * g5x_scale, -2.64 * g5y_scale),      105: (0.78 * g5x_scale, -2.64 * g5y_scale),
    106: (0.7355 * g5x_scale, -2.7845 * g5y_scale),  107: (0.785 * g5x_scale, -2.786 * g5y_scale),

    108: (0.336 * g6x_scale, -2.731 * g6y_scale),    109: (0.390 * g6x_scale, -2.7295 * g6y_scale),
    110: (0.198 * g6x_scale, -2.4046 * g6y_scale),   111: (0.2464 * g6x_scale, -2.4054 * g6y_scale),
    112: (0.1885 * g6x_scale, -2.506 * g6y_scale),   113: (0.2324 * g6x_scale, -2.507 * g6y_scale),
    114: (0.1796 * g6x_scale, -2.5945 * g6y_scale),  115: (0.2195 * g6x_scale, -2.5933 * g6y_scale),
    116: (0.173 * g6x_scale, -2.6736 * g6y_scale),   117: (0.208 * g6x_scale, -2.6738 * g6y_scale),
    118: (0.166 * g6x_scale, -2.744 * g6y_scale),    119: (0.1975 * g6x_scale, -2.7446 * g6y_scale),

    120: (0.4615 + g7x_offset, (-2.3234 + g7y_offset) * g7y_scale),                           121: (0.461 + g7x_offset, (-2.352 + g7y_offset) * g7y_scale),
    122: (0.4615 + g7x_offset, (-2.3808 + g7y_offset) * g7y_scale),                           123: (0.4618 + g7x_offset, (-2.404 + g7y_offset) * g7y_scale),
    124: (0.4654 + g7x_offset, (-2.4287 + g7y_offset) * g7y_scale),                           125: (0.464 + g7x_offset, (-2.451 + g7y_offset) * g7y_scale),
    126: (0.466 + g7x_offset, (-2.474 + g7y_offset) * g7y_scale),                             127: (0.4662 + g7x_offset, (-2.492 + g7y_offset) * g7y_scale),
    128: (0.468 + g7x_offset, (-2.515 + g7y_offset) * g7y_scale),                             129: (0.467 + g7x_offset, (-2.53 + g7y_offset) * g7y_scale),
    130: (0.47 + g7x_offset, (-2.55 + g7y_offset) * g7y_scale),                               131: (0.4705 + g7x_offset, (-2.5622 + g7y_offset) * g7y_scale),
    
}



#score table to covert score to group and element number
score_table = {}
def initialize_score_table():
    global score_table
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
        26: [G1+4,6],
        27: [G1+5,1],
        28: [G1+5,2],
        29: [G1+5,3],
        30: [G1+5,4],
        31: [G1+5,5],
        32: [G1+5,6]
    }
initialize_score_table()


prefer_dir_table =  [
                    [1, 3, 4, 2], 
                    [3, 2, 1, 4],
                    [2, 4, 3, 1],
                    [4, 1, 2, 3] 
                    ]


def usaf_lp_per_mm(group: int, element: int) -> float:
    return float(2 ** (group + (element - 1) / 6.0))



def usaf_resolution_mm(group: int, element: int) -> float:
    return float(1.0 / (2.0 * usaf_lp_per_mm(group, element)))



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

    global valid_squares
    valid_squares = []  # Reset the list for each new image

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
        # Find all contours
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

    valid_squares = [approx for _, approx in deduped_candidates]
    best_square_corners = valid_squares[0] if len(valid_squares) > 0 else None

    if DEBUG_MODE:
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

    if DEBUG_MODE:
        # Visualize all detected valid squares and highlight the best one.
        detected_img = img.copy()
        if len(valid_squares) > 0:
            cv2.drawContours(detected_img, valid_squares, -1, (0, 255, 255), 2)  # yellow: all detected squares
            for idx, square in enumerate(valid_squares):
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

        if DEBUG_MODE:
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
        if DEBUG_MODE:
            print("Square not detected. Showing thresholded image for debugging...")
            plt.figure("Debug Thresh")
            plt.imshow(gray, cmap='gray')
            plt.title("Debug Thresh")
            plt.show()
        return None



def get_rotated_pt(cx, cy, local_x, local_y, angle):
    '''
    find a rotated point at a certain angle and distance from a center point
    '''

    # Standard rotation formula
    rx = cx + local_x * np.cos(angle) - local_y * np.sin(angle)
    ry = cy + local_x * np.sin(angle) + local_y * np.cos(angle)
    return (int(rx), int(ry))



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
    flip = -1 if FLIPED_TARGET else 1
    region_center_img = get_rotated_pt(center_x, center_y, flip * region_center_scaled[0], -region_center_scaled[1], angle)
    #calculate the region size in pixels
    region_size_px = max(region_size * side_length, 13)

    # Extract region bounds
    x1 = int(region_center_img[0] - region_size_px)
    x2 = int(region_center_img[0] + region_size_px)
    y1 = int(region_center_img[1] - region_size_px)
    y2 = int(region_center_img[1] + region_size_px)
    
    # if the region is out of image return none
    if x2 >= gray.shape[1] or x1 < 0 or y2 >= gray.shape[0] or y1 < 0 and CROPED_WINDOW_RETRY:
        return None
    # Clip to image bounds
    x1 = max(0, x1)
    x2 = min(gray.shape[1], x2)
    y1 = max(0, y1)
    y2 = min(gray.shape[0], y2)
    
    region = gray[y1:y2, x1:x2]
    
    if region.size == 0:
        return None
    
    if CORNER_METHOD == "threshold":
        corners_shi_tomasi = bright_pixels_as_corners(region)
    else:
        # Apply Shi-Tomasi corner detection on white pixels
        corners_shi_tomasi = cv2.goodFeaturesToTrack(region.astype(np.uint8), 20, 0.001, 1)
        # Subpixel refinement if needed
        if region.shape[0] > 30 and region.shape[1] > 30 and SUBPIXEL:             # If the region is small, skip subpixel refinement
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

        if DEBUG_MODE:
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

    if DEBUG_MODE:
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
    if DEBUG_MODE:
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


def coordinate_calibration(gray, corners):
    '''
    Calibrates the coordinate system using the corners of the square
    '''


    # if any corner is on the edge of the image, return None to trigger retry with next best square
    for corner in corners:
        if corner[0] <= 0 or corner[0] >= gray.shape[1] - 1 or corner[1] <= 0 or corner[1] >= gray.shape[0] - 1:
            if DEBUG_MODE:
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

    if 0.9 * np.pi / 2 < np.abs(angle) or 0.1 * np.pi / 2 > np.abs(angle):
        raise ValueError("Angle too small or large, retrying with rotation...")

    # find orientation of the target
    orientation = find_target_orientation(gray, center_x, center_y, unit_vector, side_length)
    angle = angle + orientation * np.pi / 2



    #Seconary coordinate calibration using the reference corners
    # left and right ref corner are in standard coordinates 
    TL_dir = prefer_dir_table[orientation][0]
    TR_dir = prefer_dir_table[orientation][1]
    BL_dir = prefer_dir_table[orientation][2]
    BR_dir = prefer_dir_table[orientation][3]
    if FLIPED_TARGET:
        TR_dir, TL_dir = TL_dir, TR_dir
        BR_dir, BL_dir = BL_dir, BR_dir
    
    top_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, top_right_ref_coord, 1.0/5.0, TL_dir)
    top_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, top_left_ref_coord, 1.0/5.0, TR_dir)
    low_right_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, low_right_ref_coord, 1.0/5.0, BL_dir)
    low_left_ref_corner = find_white_corner_in_region(gray, center_x, center_y, angle, side_length, low_left_ref_coord, 1.0/5.0, BR_dir)


    if top_right_ref_corner is not None and top_left_ref_corner is not None and low_right_ref_corner is not None and low_left_ref_corner is not None and FOUR_KP == True:
        adjusted_top_right, adjusted_top_left = get_adjusted_top_corners_from_enclosing_rectangle(
            top_right_ref_corner,
            top_left_ref_corner,
            low_right_ref_corner,
            low_left_ref_corner,
        )

        ref_vector = np.array(adjusted_top_right) - np.array(adjusted_top_left)
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
            sum_length = top_left_ref_coord[0] + np.abs(top_right_ref_coord[0])
            offset_dist_x = top_left_ref_coord[0] * dist / sum_length
            offset_dist_y = 1.00 * dist * 0.5 / sum_length
            center_x = adjusted_top_left[0] + (ref_unit_vector[0] * offset_dist_x) - (ref_normal_vector[0] * offset_dist_y)
            center_y = adjusted_top_left[1] + (ref_unit_vector[1] * offset_dist_x) - (ref_normal_vector[1] * offset_dist_y)
            # convert from standard coordinate back to screen coordinates
            center_y = gray.shape[0] - 1 - center_y

            #recalculate side_length using the distance between the right reference corner and left reference corner
            # evil magic scaling factor 1.007
            side_length = 1.00 * dist * 1.007 / sum_length

        return [center_x, center_y, angle, side_length, adjusted_top_right, adjusted_top_left, low_right_ref_corner, low_left_ref_corner]
    elif top_right_ref_corner is not None and top_left_ref_corner is not None and FOUR_KP == False:
        ref_vector = np.array(top_right_ref_corner) - np.array(top_left_ref_corner)
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
            sum_length = top_left_ref_coord[0] + np.abs(top_right_ref_coord[0])
            offset_dist_x = top_left_ref_coord[0] * dist / sum_length
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



def point_in_bbox(point, bbox):
    x, y = point
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2

def near_proximity(point, length, bbox):
    center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    distance = np.sqrt((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2)
    return distance <= length * 1.2

def find_replacement_keypoints(pt_a, pt_b, yolo_detections):
    '''
    Check if a point falls within any YOLO bounding box and return replacement keypoints if found.
    If a match is found, remove the detection from the list.
    
    Args:
        pt_a: First point as tuple (x, y) in screen coordinates
        pt_b: Second point as tuple (x, y) in screen coordinates
        yolo_detections: List of dict with 'bbox' and 'keypoints' keys
    
    Returns:
        tuple: (replacement_point_a, replacement_point_b) or (None, None) if no match
    '''
    mid_pt = ((pt_a[0] + pt_b[0]) // 2, (pt_a[1] + pt_b[1]) // 2)
    scan_length = int(np.linalg.norm(np.array(pt_a) - np.array(pt_b)))
    for detection_idx, detection in enumerate(yolo_detections):
        bbox = detection['bbox']
        keypoints = detection['keypoints']
        
        if point_in_bbox(mid_pt, bbox):
            # Return the 2 keypoints for this detection
            if len(keypoints) >= 2:
                del yolo_detections[detection_idx]
                return keypoints[0], keypoints[1]
            elif len(keypoints) == 1:
                del yolo_detections[detection_idx]
                return None, None
        elif near_proximity(mid_pt, scan_length, bbox):
            # If the point is near the bbox, we can also consider it a match (optional)
            if len(keypoints) >= 2:
                del yolo_detections[detection_idx]
                return keypoints[0], keypoints[1]
            elif len(keypoints) == 1:
                del yolo_detections[detection_idx]
                return None, None
    
    return None, None


def apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray, increment=None, max_cum=None):
    '''
    Apply point adjustment algorithm to move points toward white regions.
    
    Args:
        pt_a: First point as numpy array
        pt_b: Second point as numpy array
        normalized_gray: Normalized grayscale image
        increment: Step size (default: 0.04 * initial_distance)
        max_cum: Maximum cumulative movement (default: 0.5 * initial_distance)
    
    Returns:
        tuple: (adjusted_pt_a, adjusted_pt_b) as tuples of ints
    '''
    pt_a = np.array(pt_a, dtype=float)
    pt_b = np.array(pt_b, dtype=float)
    
    initial_d = np.linalg.norm(pt_a - pt_b)
    if increment is None:
        increment = 0.04 * initial_d
    if max_cum is None:
        max_cum = 0.8 * initial_d
    
    cum = 0
    threshold = ADJUST_THRESH
    
    while cum < max_cum and AUTO_ADJUST:
        x1 = int(round(pt_a[0]))
        y1 = int(round(pt_a[1]))
        x2 = int(round(pt_b[0]))
        y2 = int(round(pt_b[1]))
        
        color_a = normalized_gray[y1, x1] if 0 <= x1 < normalized_gray.shape[1] and 0 <= y1 < normalized_gray.shape[0] else 0
        color_b = normalized_gray[y2, x2] if 0 <= x2 < normalized_gray.shape[1] and 0 <= y2 < normalized_gray.shape[0] else 0
        
        if color_a > threshold and color_b > threshold:
            break
        
        delta = pt_b - pt_a
        dist_ab = np.linalg.norm(delta)
        
        if dist_ab > 0:
            direction = delta / dist_ab
            if color_a <= threshold:
                pt_a = pt_a + direction * increment
                cum += increment
            if color_b <= threshold:
                pt_b = pt_b - direction * increment
                cum += increment
    
    return (int(round(pt_a[0])), int(round(pt_a[1]))), (int(round(pt_b[0])), int(round(pt_b[1])))



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
    if DEBUG_MODE:
        print("blurry score: ", score)
    return score >= threshold


def extend_line(pt_a: tuple[int, int], pt_b: tuple[int, int], extend_length: float = 1.0) -> tuple[tuple[int, int], tuple[int, int]]:
    """
    Extends the line segment AB in both directions by a specified number of pixels.
    """
    a = np.array(pt_a, dtype=np.float32)
    b = np.array(pt_b, dtype=np.float32)
    direction = b - a
    length = np.linalg.norm(direction)
    if length == 0:
        return a, b
    unit_vector = direction / length
    # 4. Extend the points
    # Move A 'backward' and B 'forward' along the unit vector
    new_a = a - (unit_vector * extend_length * length)
    new_b = b + (unit_vector * extend_length * length)
    # convert back to tuple
    new_a = (int(new_a[0]), int(new_a[1]))
    new_b = (int(new_b[0]), int(new_b[1]))
    return new_a, new_b


def scanline_jmp(
    gray,
    squ_scan_pt1,
    squ_scan_pt2,
    sample_count=100,
    extend_fraction=None,
    savgol_window=15,
    savgol_polyorder=3,
    deriv_eps=0.0001,
    refine_radius=2,
):
    """
    Sample pixels along squ_scan_pt1 -> squ_scan_pt2 (screen coordinates, same as sample_line_profile).

    Smooth the profile and count local maxima (peaks) via derivative zero-crossings from positive to
    negative, matching the pattern used for local minima in the GRADIENT_MIN scanline scoring block.

    Returns:
        has_three_peaks: True if exactly three separated peaks are found.
        peak_count: number of peaks after merging adjacent indices.
        peak_screen_pts: (N, 2) float array of (x, y) screen coords per peak, for plotting.
        peak_indices: 1D indices along the sampled profile (same order as peak_screen_pts).
        line_pixels: raw sampled intensities along the scanline.
    """
    pt_a, pt_b = squ_scan_pt1, squ_scan_pt2
    if extend_fraction is not None:
        pt_a, pt_b = extend_line(pt_a, pt_b, extend_length=extend_fraction)

    coords, line_pixels = sample_line_profile(gray, pt_a, pt_b, sample_count=sample_count)
    empty_pts = np.empty((0, 2), dtype=np.float64)
    empty_idx = np.array([], dtype=np.int64)
    if len(line_pixels) < 3:
        return False, 0, empty_pts, empty_idx, line_pixels

    n = len(line_pixels)
    wl = min(int(savgol_window), n)
    if wl % 2 == 0:
        wl -= 1
    if wl < 5:
        smooth_pixels = line_pixels.astype(np.float64, copy=False)
    else:
        po = min(int(savgol_polyorder), wl - 1)
        smooth_pixels = savgol_filter(line_pixels, window_length=wl, polyorder=max(1, po))

    dy = np.gradient(smooth_pixels)
    # Peaks: derivative crosses from positive to negative (opposite of local minima in GRADIENT_MIN).
    is_peak = (dy[:-1] > deriv_eps) | (dy[1:] < -deriv_eps)
    peak_indices = np.where(is_peak)[0]

    if len(peak_indices) > 1:
        diffs = np.diff(peak_indices)
        keep = np.concatenate(([True], diffs > 1))
        filtered = peak_indices[keep]
    else:
        filtered = peak_indices

    peak_count = int(len(filtered))
    if peak_count == 0:
        return False, 0, empty_pts, empty_idx, line_pixels

    # Refine each peak to the local maximum on the smoothed profile, then map index -> screen (x, y).
    refined = []
    for idx in filtered:
        lo = max(0, int(idx) - refine_radius)
        hi = min(n, int(idx) + refine_radius + 1)
        refined.append(lo + int(np.argmax(smooth_pixels[lo:hi])))
    refined = np.asarray(refined, dtype=np.int64)
    peak_screen_pts = coords[refined].astype(np.float64)

    return peak_count == 3, peak_count, peak_screen_pts, refined, line_pixels


def usaf2screen(pt, center_x, center_y, angle, side_length):
    # This scales the usaf coordinates to pixel scale
    scale = side_length
    loc = (pt[0] * scale, pt[1] * scale)

    # Convert from pixel usaf coordinate to screen coordinate
    # x were fliped b/c the usaf target is fliped
    # y were fliped b/c the screen coordinate system
    flip = -1 if FLIPED_TARGET else 1
    pt_a = get_rotated_pt(center_x, center_y, flip * loc[0], -loc[1], angle)
    return pt_a


def classify_left_right_numbers(img, left_number_pt, right_number_pt, num_box_offset):
    def crop_number(number_pt):
        y1, y2 = int(number_pt[1] - num_box_offset), int(number_pt[1] + num_box_offset)
        x1, x2 = int(number_pt[0] - num_box_offset), int(number_pt[0] + num_box_offset)

        if x1 < 0 or y1 < 0 or x2 > img.shape[1] or y2 > img.shape[0]:
            return None

        #mirror the image horizontally if FLIPED_TARGET is True
        if FLIPED_TARGET:
            img_final = cv2.flip(img, 1)

        return img_final[y1:y2, x1:x2]

    def classify_crop(crop):
        if crop is None:
            return -1

        result = classify_number(crop)
        predict_index = result.probs.top1
        return result.names[predict_index]

    left_crop = crop_number(left_number_pt)
    right_crop = crop_number(right_number_pt)

    return classify_crop(left_crop), classify_crop(right_crop)






def calculate_focus_scores(curr_image, yolo_detections=None, retry_instance = 0):
    '''
    Calculate the focus scores for each group element based on the defined scanlines and the detected corners for coordinate calibration.
    If YOLO detections are provided, replace scanline endpoints that fall within YOLO bounding boxes with YOLO keypoints.
    
    Args:
        curr_image: BGR image array (same format as cv2.imread)
        yolo_detections: Optional list of YOLO detections with 'bbox' and 'keypoints' keys
    
    Return a ordered dictionary of scores for each group element, where the key is the group element number and the value is the focus score.
    '''
    global G1
    global INITIAL_ANGLE
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
    global retry_count
    retry_count = 0
    retry_condition = False
    retry_origin = False
    scores = {}

    while retry_count < valid_squares.__len__():
        scanlines = {}
        scores = {}  # reset scores before retrying
        img = clean_img.copy()
        retry_condition = False

        corners = valid_squares[retry_count].reshape(-1, 2).copy()
        corners[:, 1] = img.shape[0] - corners[:, 1] - 1
        output_list = coordinate_calibration(gray, corners)

        if output_list is None:
            retry_count = retry_count + 1
            if DEBUG_MODE:
                print(f"Retrying coordinate calibration with next best square... Attempt {retry_count}")
            continue

        [center_x, center_y, angle, side_length, top_right_ref_corner, top_left_ref_corner, low_right_ref_corner, low_left_ref_corner] = output_list



        # get the outer coordinate from the center coordinate
        if retry_count == 1 and not retry_origin and RETRY_OUTER:
            flip = -1 if FLIPED_TARGET else 1
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
        for i in range(0, len(group_positions), 2):
            yolo_repl = False
            local_min = False

            # Get the raw usaf coordinates (tuples)
            raw_a = group_positions[i]
            raw_b = group_positions[i+1]

            # Convert from pixel usaf coordinate to screen coordinate
            pt_a = usaf2screen(raw_a, center_x, center_y, angle, side_length)
            pt_b = usaf2screen(raw_b, center_x, center_y, angle, side_length)

            # if the pts fall outside the image, retry with the next best square
            if (pt_a[0] < 0 or pt_a[0] >= gray.shape[1] or pt_a[1] < 0 or pt_a[1] >= gray.shape[0] or \
            pt_b[0] < 0 or pt_b[0] >= gray.shape[1] or pt_b[1] < 0 or pt_b[1] >= gray.shape[0]) and RETRY_OFF_IMAGE:
                retry_condition = True
                break

            # point adjustment algorithm:
            # Adjust points until both are white
            pt_a_adj, pt_b_adj = apply_point_adjustment_algorithm(pt_a, pt_b, normalized_gray)
            pt_a, pt_b = pt_a_adj, pt_b_adj

            # ====== YOLO INTEGRATION: Check and replace points if they fall within YOLO bounding boxes ======
            if yolo_detections is not None and len(yolo_detections) > 0 and YOLO_DETECT:
                repl_a, repl_b = find_replacement_keypoints(pt_a, pt_b, yolo_detections)
                if repl_a is not None:
                    pt_a, pt_b = apply_point_adjustment_algorithm(repl_a, repl_b, normalized_gray)
                    yolo_repl = True

            # Create a mask for the line
            mask = np.zeros_like(gray, dtype=np.uint8)
            cv2.line(mask, pt_a, pt_b, 255, 2)
            # Get pixel values along the line from normalized_gray
            line_pixels = normalized_gray[mask > 0]

            if len(line_pixels) > 0:
                brightest = np.max(line_pixels)
                darkest = np.min(line_pixels)
                diff = brightest - darkest
                score = diff                    
            else:
                score = 0



            if GRADIENT_MIN:
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

                    if GRADIENT_PLOT_ENABLE:
                        scan_idx = i // 2
                        unique_count = len(score_table)
                        base_idx = scan_idx % unique_count
                        orientation = "vertical" if scan_idx < unique_count else "horizontal"
                        group, element = score_table[base_idx]
                        group_match = GRADIENT_PLOT_GROUP is None or group == GRADIENT_PLOT_GROUP
                        element_match = GRADIENT_PLOT_ELEMENT is None or element == GRADIENT_PLOT_ELEMENT
                        orient_match = GRADIENT_PLOT_ORIENTATION in ("both", orientation)

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
                retry_count = retry_count + 1
                retry_instance = retry_instance - 1
                continue


        if retry_origin == False:
            retry_count = retry_count + 1
        
        if DEBUG_MODE:
            print(f"Found out image scanline, Retrying with next best square... Attempt {retry_count}")

    if retry_count == valid_squares.__len__():
        if DEBUG_MODE:
            print(f"Failed to find valid square after {retry_count} attempts")
        scores = {}  # reset scores
        return None, None

    if yolo_detections is not None and len(yolo_detections) > 15:
        misalignment_handling(clean_detection, clean_img.copy(), normalized_gray)

    if initial_retry_instance != 0 and not (0.9 * INITIAL_ANGLE < np.abs(angle) < 1.1 * INITIAL_ANGLE):
        if DEBUG_MODE:
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
        pattern_count = len(pt4_pattern_result.boxes)
        G1 = 8 - pattern_count * 2 + retry_count * 2
        if DEBUG_MODE:
            print("G1 is: ", G1)
        if G1 > 6:
            return None, None
        initialize_score_table()
        # show image with annotation
        if DEBUG_MODE:
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

    zoom_box_pt = usaf2screen(zoom_box_coord, center_x, center_y, angle, side_length)
    zoom_box_offset = 80
    # Crop the image around the zoom box
    zoom_box_img = clean_img[int(zoom_box_pt[1] - zoom_box_offset):int(zoom_box_pt[1] + zoom_box_offset), int(zoom_box_pt[0] - zoom_box_offset):int(zoom_box_pt[0] + zoom_box_offset)]


    if PREVIEW_MODE:
        # Display the result
        # convert the right reference corner and left reference corner from standard to screen coordinates
        top_right_ref_corner = (int(top_right_ref_corner[0]), int(gray.shape[0] - top_right_ref_corner[1] - 1))
        top_left_ref_corner = (int(top_left_ref_corner[0]), int(gray.shape[0] - top_left_ref_corner[1] - 1))
        cv2.circle(img, top_right_ref_corner, 2, (255, 0, 255), -1)  # magenta for right reference corner
        cv2.circle(img, top_left_ref_corner, 2, (255, 255, 0), -1)  # cyan for left reference corner


        if FOUR_KP == True:
            low_right_ref_corner = (int(low_right_ref_corner[0]), int(gray.shape[0] - low_right_ref_corner[1] - 1))
            low_left_ref_corner = (int(low_left_ref_corner[0]), int(gray.shape[0] - low_left_ref_corner[1] - 1))
            cv2.circle(img, low_right_ref_corner, 2, (255, 0, 255), -1)  # magenta for right reference corner
            cv2.circle(img, low_left_ref_corner, 2, (255, 255, 0), -1)  # cyan for left reference corner


        # calculate region dimension and draw the region 
        right_region_size_px = int((1.0/5.0) * side_length)
        left_region_size_px = int((1.0/5.0) * side_length)
        # convert the right reference corner and left reference corner from usaf to screen coordinates, then draw the region around them,
        # cast to int for cv2.rectangle
        right_rotated_pt = usaf2screen(top_right_ref_coord, center_x, center_y, angle, side_length)
        left_rotated_pt = usaf2screen(top_left_ref_coord, center_x, center_y, angle, side_length)
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
        
        if SCORE_METHOD == "mean":
            temp_score = (vert_score + horiz_score) / 2.0
        elif SCORE_METHOD == "max":
            temp_score = max(vert_score, horiz_score)
        elif SCORE_METHOD == "min":
            temp_score = min(vert_score, horiz_score)
        else:
            temp_score = vert_score
        
        final_score[i] = {"score": float(temp_score), "type": temp_type}

        group, element = score_table[i]
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
            INITIAL_ANGLE = np.abs(angle)

    return final_score, scanline_map



def find_best_focus_group(scores_list, threshold=0.2):
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
        return score_table[chosen_index], chosen_index

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
        chosen_index = len(score_table) - 1
        return score_table[chosen_index], chosen_index
    
    for i in range(last_index, len(scores_list)):     
        # If the score starts going UP, the previous index was the "bottom"
        if scores_list[i]["score"] > scores_list[i-1]["score"] * 1.1 or scores_list[i]["score"] < threshold:
            # Return the score of the last group before it went up or dropped too low
            chosen_index = min(i-1, len(score_table) - 1)
            return score_table[chosen_index], chosen_index
    
    # If it never goes up, return first element
    print("No score goes up")
    chosen_index = len(score_table) - 1
    return score_table[chosen_index], chosen_index



def find_usaf_score(image_path, imgsz=2048, threshold=0.2):
    '''
    Find the usaf focus score for a given image path, which is the best focus group number 
    based on the defined scanlines and the detected corners for coordinate calibration.
    
    Args:
        image_path: Path to the image
        imgsz: Image size for YOLO inference
    
    Returns:
        Tuple of (group_number, element_number) indicating best focus group
    '''
    global G1
    curr_image = cv2.imread(image_path)
    if curr_image is None:
        return None

    if not is_image_clear(curr_image, 4):
        print("The image is too blurry for detection")
        return None
    
    while True:
        yolo_detections = None
        if YOLO_DETECT:
            yolo_detections, _result, _img = extract_yolo_detections(curr_image, imgsz=imgsz)
        if PREVIEW_MODE and YOLO_DETECT:
            visualize_detections(_img, _result, yolo_detections)
        # Calculate focus scores
        scores = {}
        scanline_map = {}
        best_focus_group = {}
        chosen_index = {}
        try:
            scores[0], scanline_map[0] = calculate_focus_scores(curr_image, yolo_detections, 0)
            best_focus_group[0], chosen_index[0] = find_best_focus_group(scores[0], threshold=threshold)
            if DEBUG_MODE:
                print("best_focus_group[0]", best_focus_group[0])

            scores[1], scanline_map[1] = calculate_focus_scores(curr_image, yolo_detections, 1)
            best_focus_group[1], chosen_index[1] = find_best_focus_group(scores[1], threshold=threshold)
            if DEBUG_MODE:
                print("best_focus_group[1]", best_focus_group[1])

            scores[2], scanline_map[2] = calculate_focus_scores(curr_image, yolo_detections, 2)
            best_focus_group[2], chosen_index[2] = find_best_focus_group(scores[2], threshold=threshold)
            if DEBUG_MODE:
                print("best_focus_group[2]",best_focus_group[2])
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
    for i in range(3):
        group = best_focus_group[i]
        if group is None:
            continue
        if not isinstance(group, (list, tuple)) or len(group) < 2:
            continue
        best_focus_info.append([group, chosen_index[i], scanline_map[i], scores[i]])
        if DEBUG_MODE:
            print("candidate best focus group", group)

    if not best_focus_info:
        print("No best focus group found")
        return None

    # Winner: highest group number, then highest element number.
    final_best_focus_info = max(best_focus_info, key=lambda x: (x[0][0], x[0][1]))

    if final_best_focus_info[3] is not None and DEBUG_MODE:
        print(f"Scores for {image_path}: {final_best_focus_info[3]}")

    print(f"Best focus group for {image_path}: {final_best_focus_info[0][0]}, element {final_best_focus_info[0][1]}")

    G1 = 2
    initialize_score_table()

    # Return legacy outputs plus processed image used during scoring.
    return final_best_focus_info[0], final_best_focus_info[1], final_best_focus_info[2], final_best_focus_info[3], curr_image


# for image_path in images:
#     find_usaf_score(image_path)

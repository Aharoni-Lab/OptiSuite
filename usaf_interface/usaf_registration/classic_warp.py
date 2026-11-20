"""The big white square of the USAF target: sets self.C.valid_squares (largest first).
Nested matching uses its size to scale the photo to template density."""
import random

import cv2
import matplotlib.pyplot as plt
import numpy as np


def make_dummy_valid_square(self, gray):
    """
    Centred diamond-shaped contour, used as the square when none was detected so the
    whole-photo SIFT match still gets one attempt.
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


def is_valid_square(self, approx, gray, white_threshold=250, angle_tolerance=5, side_ratio_tolerance=1.2):
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



def find_square_corners(self, gray):
    '''
    find the square in the usaf target for initial coordinate calibration, 
    return the corners in standard coordinates (x, y)
    '''
    self.C.valid_squares = []  # Reset the list for each new image

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
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # On dark, blurry photos the Otsu cut sits low and the square's glow merges with the bars
        # next to it; brighter cuts (fractions of the brightest level) separate it again.
        top = float(np.percentile(blurred, 99.5))
        cuts = [otsu] + [cv2.threshold(blurred, f * top, 255, cv2.THRESH_BINARY)[1] for f in (0.5, 0.65, 0.8)]
        # all contours of every cut, largest first
        contours = [(cnt, thresh) for thresh in cuts
                    for cnt in cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]]
        contours.sort(key=lambda ct: cv2.contourArea(ct[0]), reverse=True)

        for cnt, thresh in contours:
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
            if len(approx) == 4 and self.is_valid_square(approx, thresh):
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

    self.C.valid_squares = [approx for _, approx in deduped_candidates]
    best_square_corners = self.C.valid_squares[0] if len(self.C.valid_squares) > 0 else None

    if self.C.DEBUG_MODE:
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

    if self.C.DEBUG_MODE:
        # Visualize all detected valid squares and highlight the best one.
        detected_img = img.copy()
        if len(self.C.valid_squares) > 0:
            cv2.drawContours(detected_img, self.C.valid_squares, -1, (0, 255, 255), 2)  # yellow: all detected squares
            for idx, square in enumerate(self.C.valid_squares):
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

        if self.C.DEBUG_MODE:
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
        if self.C.DEBUG_MODE:
            print("Square not detected. Showing thresholded image for debugging...")
            plt.figure("Debug Thresh")
            plt.imshow(thresh, cmap='gray')
            plt.title("Debug Thresh")
            plt.show()
        raise ValueError("classic_warp.find_square_corners: No valid square detected in the image.")

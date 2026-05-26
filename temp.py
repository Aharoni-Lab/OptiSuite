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

    approx_polys = []
    best_square_corners = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500: # Ignore tiny noise
            continue
            
        peri = cv2.arcLength(cnt, True)
        # Increase the 0.02 factor if it still fails (e.g., 0.04)
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
        approx_polys.append(approx)

        # Look for 4-sided polygons that form valid squares
        if len(approx) == 4:
            # Check if this polygon meets the square criteria
            if is_valid_square(approx, thresh):
                valid_squares.append(approx)  # Store in global list
                
                # Keep track of the largest valid square
                if area > best_area:
                    best_area = area
                    best_square_corners = approx

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
        plt.show(block=False)
        plt.pause(0.001)

    if DEBUG_MODE:
        # Visualize all detected valid squares and highlight the best one.
        detected_img = img.copy()
        if len(valid_squares) > 0:
            cv2.drawContours(detected_img, valid_squares, -1, (0, 255, 255), 2)  # yellow: all detected squares
            for idx, square in enumerate(valid_squares):
                center = np.mean(square.reshape(-1, 2), axis=0).astype(int)
                cv2.putText(detected_img, str(idx), tuple(center), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
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
        plt.show(block=False)
        plt.pause(0.001)

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
            plt.imshow(thresh, cmap='gray')
            plt.title("Debug Thresh")
            plt.show()
        return None
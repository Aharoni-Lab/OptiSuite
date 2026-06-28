
import numpy as np
import constants as C





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
    def point_in_bbox(point, bbox):
        x, y = point
        x1, y1, x2, y2 = bbox
        return x1 <= x <= x2 and y1 <= y <= y2

    def near_proximity(point, length, bbox):
        center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        distance = np.sqrt((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2)
        return distance <= length * 1.2

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
    threshold = C.ADJUST_THRESH
    
    while cum < max_cum and C.AUTO_ADJUST:
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

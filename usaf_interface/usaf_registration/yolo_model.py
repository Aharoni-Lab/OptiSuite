from pathlib import Path
import cv2
from ultralytics import YOLO
import numpy as np
import matplotlib.pyplot as plt
from .transforms import yolo2screen


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models/best23.pt"
NUM_MODEL_PATH = BASE_DIR / "models/best_num_classify.pt"
# RES_MODEL_PATH = BASE_DIR / "models/resolution_cls_model2.pt"
RES_MODEL_PATH = BASE_DIR / "models/pattern_classify_v2_thresh_0.2.pt"
# RES_MODEL_PATH = BASE_DIR / "models/0.2_threshold_classification.pt"
# PT4_MODEL_PATH = BASE_DIR / "models/best_4p_4_focused.pt"
PT4_MODEL_PATH = BASE_DIR / "models/4p_detect_ultra_pro_max.pt"
SINGLE_SCANLINE_MODEL_PATH = BASE_DIR / "models/single_pattern_scanline_v2.pt"








def classify_resolution(self, img):
    img = cv2.resize(img, (256, 256))
    model = self.get_yolo_model(RES_MODEL_PATH)
    results = model(img, verbose=False)
    result = results[0]
    if result.probs is None:
        return "unresolved", 0.0
    # return result and it confidence score for the top class
    return result.names[result.probs.top1], float(result.probs.top1conf.item())


def count_4pts_pattern(self, img):
    # Safety Check 1: Make sure the image actually exists
    if img is None:
        raise ValueError("yolo_model.count_4pts_pattern: Input image is None")
        
    input_config = True

    if input_config:
        # Letterbox to 1280x1280: scale longest side to 1280, then pad the shorter side.
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            raise ValueError("yolo_model.count_4pts_pattern: Input image has invalid dimensions")

        scale = 1280.0 / max(h, w)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_w = 1280 - new_w
        pad_h = 1280 - new_h
        left = pad_w // 2
        right = pad_w - left
        top = pad_h // 2
        bottom = pad_h - top
        img = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    else:
        img = cv2.resize(img, (1280, 1280))

    # Safety Check 2: Ensure model path is valid
    try:
        model = self.get_yolo_model(PT4_MODEL_PATH)
    except Exception as e:
        raise RuntimeError(f"yolo_model.count_4pts_pattern: Error loading model from {PT4_MODEL_PATH}: {e}")
        
    if input_config:
        results = model(img, imgsz=1280, iou=0.3, conf=0.30)
    else:
        results = model(img, imgsz=640, iou=0.3, conf=0.25)
    
    # Safety Check 3: Check what YOLO actually returned
    if not results or len(results) == 0:
        raise RuntimeError("yolo_model.count_4pts_pattern: YOLO returned no results")
        
    # YOLO returns a list of Results objects (one per image). 
    # We grab the first image's results.
    first_result = results[0]
    
    if first_result.boxes is None:
        raise RuntimeError("yolo_model.count_4pts_pattern: YOLO returned no bounding boxes")

    return first_result
    









def yolo_4pt_calculation(self, pt4_pattern_result):
    """
    Mirror direction from the 4-point pattern keypoints: per box, whether kp0 -> kp3 run clockwise
    around the box centre; the box with the most keypoint confidence decides. Sets
    self.C.FLIPED_TARGET (nested matching still tries the mirror if layer 1 fails).
    Returns the direction (True = clockwise / flipped) or None if no box had 2+ keypoints.
    """
    if pt4_pattern_result is None:
        raise ValueError("yolo_model.yolo_4pt_calculation: Input result is None")
    kps = pt4_pattern_result.keypoints
    if pt4_pattern_result.boxes is None or len(pt4_pattern_result.boxes) == 0 or kps is None or kps.xy is None:
        return None
    boxes = pt4_pattern_result.boxes.xyxy.cpu().numpy()
    xy = kps.xy.cpu().numpy()
    conf = kps.conf.cpu().numpy() if kps.conf is not None else None

    directions = []   # [clockwise, total keypoint confidence]
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        if i >= len(xy):
            break
        pts, total_conf = [], 0.0
        for k, (kx, ky) in enumerate(xy[i]):
            if np.isnan(kx) or np.isnan(ky):
                continue
            pts.append((kx, ky))
            c = float(conf[i][k]) if conf is not None and k < len(conf[i]) else 0.0
            total_conf += c if c >= 0.2 else 0.0
        if len(pts) < 2:
            continue
        # screen y-down -> y-up before measuring the turn
        rel = np.array(pts, dtype=np.float64) - [(x1 + x2) / 2.0, (y1 + y2) / 2.0]
        rel[:, 1] *= -1.0
        total_delta = float(np.sum(np.diff(np.unwrap(np.arctan2(rel[:, 1], rel[:, 0])))))
        if abs(total_delta) < 1e-12:
            # degenerate: first non-zero local turn decides
            clockwise = False
            for j in range(len(rel) - 1):
                cross_z = rel[j, 0] * rel[j + 1, 1] - rel[j, 1] * rel[j + 1, 0]
                if abs(cross_z) > 1e-12:
                    clockwise = cross_z < 0
                    break
        else:
            clockwise = total_delta < 0
        directions.append([bool(clockwise), total_conf])

    if self.C.DEBUG_MODE:
        print(f"Direction flags (clockwise=True): {directions}")
    if not directions:
        return None
    yolo_dir = max(directions, key=lambda x: x[1])[0]
    self.C.FLIPED_TARGET = yolo_dir
    return yolo_dir









def get_yolo_model(self, model_path):
    model_path = str(model_path)
    if model_path not in self.C._MODEL_CACHE:
        self.C._MODEL_CACHE[model_path] = YOLO(str(model_path))
    return self.C._MODEL_CACHE[model_path]


def extract_yolo_detections(self, curr_image, model_path = MODEL_PATH, imgsz=2048):
    """
    Extract YOLO detections including bounding boxes and keypoints for each detected object.

    Args:
        curr_image: BGR numpy array, or a path string/Path (loaded internally).
    
    Returns:
        Tuple of:
        - detections: List of dicts with keys 'bbox' and 'keypoints'
            - 'bbox': (x1, y1, x2, y2) in pixel coordinates
            - 'keypoints': List of (x, y) tuples representing keypoints for the detection
        - result: YOLO result object
        - img: Original image
    """
    model = self.get_yolo_model(model_path)
    if isinstance(curr_image, (str, Path)):
        img = cv2.imread(str(curr_image))
        if img is None:
            raise FileNotFoundError(f"yolo_model.extract_yolo_detections: Could not read image: {curr_image}")
        source = str(curr_image)
    else:
        img = curr_image
        if img is None or img.size == 0:
            raise ValueError("yolo_model.extract_yolo_detections: Invalid image array")
        source = img

    results = model(source, imgsz=imgsz, iou=0.5, conf=0.25)
    result = results[0]
    
    detections = []
    
    # Extract bounding boxes and keypoints from YOLO results
    if result.boxes is not None:
        boxes = result.boxes.xyxy.cpu().numpy()  # Get bounding boxes in (x1, y1, x2, y2) format

        # Check if keypoints are available
        if result.keypoints is not None and result.keypoints.xy is not None:
            keypoints_data = result.keypoints.xy.cpu().numpy()  # Shape: (num_detections, num_keypoints, 2)



            # remove boxes if the aspect ration is 2:1 or 1:2 or more extreme
            filtered_boxes = []
            filter_keypoints = []
            for i, box in enumerate(boxes):  # Iterate over the bounding boxes:
                x1, y1, x2, y2 = box
                w = x2 - x1
                h = y2 - y1
                aspect_ratio = w / h if h > 0 else 0
                if 0.66 <= aspect_ratio <= 1.5:
                    filtered_boxes.append(box)
                    filter_keypoints.append(keypoints_data[i])
            boxes = np.array(filtered_boxes)
            keypoints_data = np.array(filter_keypoints)


            
            for i, bbox in enumerate(boxes):
                x1, y1, x2, y2 = bbox
                # Get the 2 keypoints for this detection (take first 2 keypoints)
                # or the keypoints with highest confidence
                keypoints = keypoints_data[i]
                delta = 5

                kp1_in = (x1-delta <= keypoints[0][0] <= x2+delta and y1-delta <= keypoints[0][1] <= y2+delta)
                kp2_in = (x1-delta <= keypoints[1][0] <= x2+delta and y1-delta <= keypoints[1][1] <= y2+delta)
                # Filter out invalid keypoints (usually marked with NaN or zero confidence)
                # filter keypoints that are outside the bounding box
                valid_keypoints = []
                if kp1_in or kp2_in:
                    for kpt in keypoints:
                        if not np.isnan(kpt[0]) and not np.isnan(kpt[1]):
                            valid_keypoints.append(tuple(kpt.astype(int)))
                        
                    # If we have keypoints, use them; otherwise none
                    selected_keypoints = [None, None]
                    if len(valid_keypoints) >= 2:
                        selected_keypoints = valid_keypoints[:2]
                        
                    detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'keypoints': selected_keypoints
                    })
        else:
            # No keypoints available, use bbox centers as fallback
            for bbox in boxes:
                x1, y1, x2, y2 = bbox
                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'keypoints': [None, None]  # No keypoints available
                })
    
    return detections, result, img


def visualize_detections(self, img, result = None, detections = None):
    """
    Visualize YOLO detections with bounding boxes and keypoints.
    """

    img_vis = img.copy()

    if detections is None or len(detections) == 0:
        raise ValueError("yolo_model.visualize_detections: No detections to visualize")
    
    # Draw bounding boxes and keypoints
    for detection in detections:
        bbox = detection['bbox']
        keypoints = detection['keypoints']
        
        # Draw bounding box
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img_vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
        
        # Draw keypoints
        for i, (kx, ky) in enumerate(keypoints):
            cv2.circle(img_vis, (int(kx), int(ky)), 1, (0, 0, 255), -1)
            # cv2.putText(img_vis, f"K{i}", (int(kx)+5, int(ky)-5), 
            #            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
    plt.figure(figsize=(10, 8))
    plt.imshow(cv2.cvtColor(img_vis, cv2.COLOR_BGR2RGB))
    plt.title("Custom Keypoint Visualization")
    plt.axis("off")  # Hide the axes
    plt.tight_layout()
    plt.show()
    
    return img_vis


def detect_single_scanline_keypoints(self, image, imgsz=256, conf=0.10, iou=0.5):
    """
    Run SINGLE_SCANLINE_MODEL_PATH (keypoint model) on an image and return detected keypoints.

    Args:
        image: BGR numpy array, or a path string/Path.
        imgsz: YOLO inference image size.
        conf: Confidence threshold.
        iou: IOU threshold.

    Returns:
        List of (x, y) integer keypoint coordinates.
    """
    model = self.get_yolo_model(SINGLE_SCANLINE_MODEL_PATH)

    if isinstance(image, (str, Path)):
        img = cv2.imread(str(image))
        if img is None:
            raise FileNotFoundError(f"yolo_model.detect_single_scanline_keypoints: Could not read image: {image}")
        source = str(image)
    else:
        img = image
        if img is None or img.size == 0:
            raise ValueError("yolo_model.detect_single_scanline_keypoints: Invalid image array")
        source = img

    results = model(source, imgsz=imgsz, conf=conf, iou=iou, verbose=False)
    if not results:
        return []

    result = results[0]
    keypoints = []

    if result.keypoints is not None and result.keypoints.xy is not None:
        keypoints_xy = result.keypoints.xy.cpu().numpy()
        for det_points in keypoints_xy:
            kp1, kp2 = det_points[:2]  # Take first 2 keypoints
            if np.isnan(kp1[0]) or np.isnan(kp1[1]) or np.isnan(kp2[0]) or np.isnan(kp2[1]):
                continue
            kp1, kp2 = (int(round(float(kp1[0]))), int(round(float(kp1[1])))), (int(round(float(kp2[0]))), int(round(float(kp2[1]))))
            keypoints.append((kp1, kp2))

    if self.C.DEBUG_MODE and False:
        img_vis = img.copy()
        for p1, p2 in keypoints:
            cv2.circle(img_vis, p1, 4, (0, 0, 255), -1)
            cv2.circle(img_vis, p2, 4, (0, 255, 255), -1)
            cv2.line(img_vis, p1, p2, (0, 255, 0), 1)

        plt.figure("Single Scanline KP Debug", figsize=(8, 8))
        plt.clf()
        plt.imshow(cv2.cvtColor(img_vis, cv2.COLOR_BGR2RGB))
        plt.title(f"Detected keypoints: {len(keypoints)}")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

    return keypoints
from pathlib import Path
import cv2
from ultralytics import YOLO
import numpy as np
import matplotlib.pyplot as plt
import constants as C
from transforms import yolo2screen

_MODEL_CACHE = {}
MODEL_PATH = Path("./models/best23.pt")
NUM_MODEL_PATH = Path("./models/best_num_classify.pt")
# RES_MODEL_PATH = Path("./models/resolution_cls_model2.pt")
RES_MODEL_PATH = Path("./models/pattern_classify_v2_thresh_0.2.pt")
# RES_MODEL_PATH = Path("./models/0.2_threshold_classification.pt")
# PT4_MODEL_PATH = Path("./models/best_4p_4_focused.pt")
PT4_MODEL_PATH = Path("./models/4p_detect_ultra_pro_max.pt")
SINGLE_SCANLINE_MODEL_PATH = Path("./models/single_pattern_scanline_v2.pt")








def classify_resolution(img):
    img = cv2.resize(img, (256, 256))
    model = get_yolo_model(RES_MODEL_PATH)
    results = model(img, verbose=False)
    result = results[0]
    if result.probs is None:
        return "unresolved", 0.0
    # return result and it confidence score for the top class
    return result.names[result.probs.top1], float(result.probs.top1conf.item())


def count_4pts_pattern(img):
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
        model = YOLO(PT4_MODEL_PATH)
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
    









def yolo_4pt_calculation(pt4_pattern_result, img):
    # extract the detected keypoints from the YOLO result
    if pt4_pattern_result is None:
        raise ValueError("yolo_model.yolo_4pt_calculation: Input result is None")

    if pt4_pattern_result.boxes is None or len(pt4_pattern_result.boxes) == 0:
        return []
    
    fliped = -1 if C.FLIPED_TARGET else 1
    canonical_kps = np.array(
        [
            [1.0 * fliped, 0.0 * fliped],
            [0.0, 0.0],
            [0.0, 1.0],
            [1.0 * fliped, 1.0 * fliped],
        ],
        dtype=np.float64,
    )

    # [box1, box2, ...] where box is (box1_x1, box1_y1, box1_x2, box1_y2)
    boxes_xyxy = pt4_pattern_result.boxes.xyxy.cpu().numpy()
    # [box1_kps, box2_kps, ...] where box_kps is [[kp1_x, kp1_y], [kp2_x, kp2_y], ...]
    keypoints_xy = None
    # [box1_kps_conf, box2_kps_conf, ...] where box_kps_conf is [kp1_conf, kp2_conf, ...]
    keypoints_conf = None
    if pt4_pattern_result.keypoints is not None and pt4_pattern_result.keypoints.xy is not None:
        keypoints_xy = pt4_pattern_result.keypoints.xy.cpu().numpy()
        if pt4_pattern_result.keypoints.conf is not None:
            keypoints_conf = pt4_pattern_result.keypoints.conf.cpu().numpy()



    # Parse YOLO results format
    # [
    #     {
    #         "top_left": (int(box1_x1), int(round(float(box1_y1)))),
    #         "bottom_right": (int(box1_x2), int(box1_y2)),
    #         "keypoints": [
    #                         {
    #                             "idx": 0,
    #                             "xy": (int(kp1_x), int(kp1_y)),
    #                             "conf": float(kp1_conf) or None
    #                         },
    #                         ... 
    #                      ],
    #         "kp23_vector": (int(kp23_x), int(kp23_y)),
    #     }, 
    #     ...
    # ]
    parsed = []
    yolo_angles = []
    box_lengths = []
    directions = []
    yolo_dir = None
    for det_idx, box in enumerate(boxes_xyxy):
        box = [(box[0], box[1]), (box[2], box[3])]
        [x1, y1], [x2, y2] = yolo2screen(box, img)
        box_length = np.linalg.norm(np.array((x2, y2)) - np.array((x1, y1)))
        if box_length != 0:
            box_lengths.append(box_length)
        item = {
            "top_left": (int(round(float(x1))), int(round(float(y1)))),
            "bottom_right": (int(round(float(x2))), int(round(float(y2)))),
            "keypoints": [],
            "kp23_vector": None,
            "kp23_angle": None,
            "kp23_length": None,
        }

        if keypoints_xy is not None and det_idx < len(keypoints_xy):
            for kp_idx, (kx, ky) in enumerate(keypoints_xy[det_idx]):
                if np.isnan(kx) or np.isnan(ky):
                    continue
                kx, ky = yolo2screen([(kx, ky)], img)[0]
                kp_conf = None
                if keypoints_conf is not None and det_idx < len(keypoints_conf) and kp_idx < len(keypoints_conf[det_idx]):
                    kp_conf = float(keypoints_conf[det_idx][kp_idx])
                    if kp_conf < 0.2:  # Filter out low confidence keypoints
                        kp_conf = None

                item["keypoints"].append(
                    {
                        "idx": kp_idx,
                        "xy": (int(round(float(kx))), int(round(float(ky)))),
                        "conf": kp_conf,
                    }
                )

        # For boxes with >1 keypoint, determine if index-order motion around box center
        # is clockwise (True) or counterclockwise (False).
        if len(item["keypoints"]) >= 2:
            ordered_kps = sorted(item["keypoints"], key=lambda kp: kp["idx"])
            center = np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=np.float64)
            pts = np.array([kp["xy"] for kp in ordered_kps], dtype=np.float64)

            # Convert screen y-down to y-up before computing angular direction.
            rel = pts - center
            rel[:, 1] *= -1.0
            angles = np.arctan2(rel[:, 1], rel[:, 0])
            unwrapped = np.unwrap(angles)
            total_delta = float(np.sum(np.diff(unwrapped)))

            if abs(total_delta) < 1e-12:
                # Degenerate fallback: first non-zero local turn decides direction.
                is_clockwise = False
                for i in range(len(rel) - 1):
                    cross_z = rel[i, 0] * rel[i + 1, 1] - rel[i, 1] * rel[i + 1, 0]
                    if abs(cross_z) > 1e-12:
                        is_clockwise = cross_z < 0
                        break
            else:
                # in screen coordinate True = clockwise, False = counterclockwise
                is_clockwise = total_delta < 0

            yolo_dir = bool(is_clockwise)
            total_conf = sum(kp["conf"] for kp in ordered_kps if kp["conf"] is not None)
            directions.append([bool(is_clockwise), total_conf])

            if not C.retry_flag:
                # Canonical ordered square points for kp0..kp3.
                C.FLIPED_TARGET = yolo_dir
                fliped = -1 if C.FLIPED_TARGET else 1
                canonical_kps = np.array(
                    [
                        [1.0 * fliped, 0.0 * fliped],
                        [0.0, 0.0],
                        [0.0, 1.0],
                        [1.0 * fliped, 1.0 * fliped],
                    ],
                    dtype=np.float64,
                )

        # Reconstruct vector kp2-kp3 from any 2 valid keypoints (conf is not None)
        # assuming keypoints are ordered and lie on a perfect square.
        valid_kps = [
            (kp["idx"], kp) for kp in item["keypoints"] if kp.get("conf") is not None
        ]
        if len(valid_kps) >= 2:
            # Prefer the two highest-confidence keypoints.
            idx_a, kp_a = valid_kps[0]
            idx_b, kp_b = valid_kps[1]

            p_a = np.array(kp_a["xy"], dtype=np.float64)
            p_b = np.array(kp_b["xy"], dtype=np.float64)
            u_a = canonical_kps[idx_a]
            u_b = canonical_kps[idx_b]

            du = u_b - u_a
            dp = p_b - p_a
            du_norm = np.linalg.norm(du)
            dp_norm = np.linalg.norm(dp)

            if du_norm > 1e-9 and dp_norm > 1e-9:
                angle_u = float(np.arctan2(du[1], du[0]))
                angle_p = float(np.arctan2(dp[1], dp[0]))
                theta = angle_p - angle_u
                scale = dp_norm / du_norm

                cos_t = float(np.cos(theta))
                sin_t = float(np.sin(theta))
                rot = np.array([[cos_t, -sin_t], [sin_t, cos_t]], dtype=np.float64)

                # target vector is kp2 - kp3 in canonical index space.
                v23_canonical = canonical_kps[1] - canonical_kps[2]
                v23 = scale * (rot @ v23_canonical)
                item["kp23_vector"] = (float(v23[0]), float(v23[1]))
        
        if item["kp23_vector"] is not None:
            kp23_angle = np.arctan2(item["kp23_vector"][1], item["kp23_vector"][0])
            kp23_length = np.linalg.norm(item["kp23_vector"])
            item["kp23_angle"] = float(kp23_angle)
            item["kp23_length"] = float(kp23_length)
            yolo_angles.append(kp23_angle)

        parsed.append(item)

    yolo_angles = [angle for angle in yolo_angles if angle is not None]
    # Sort angles by size, largest first
    yolo_angles = sorted(yolo_angles, reverse=True)

    # Sort boxes by length, largest first
    box_lengths = sorted(box_lengths, reverse=True)
    if C.DEBUG_MODE:
        print(f"Sorted yolo angles: {yolo_angles}")
        print(f"Sorted box lengths: {box_lengths}")
        print(f"Direction flags (clockwise=True): {directions}")

    yolo_dir = None
    if directions is None:
        yolo_dir = None
    else:
        # take the highest confidence direction
        yolo_dir = max(directions, key=lambda x: x[1])[0]

    if yolo_dir is not None and not C.retry_flag:
        C.FLIPED_TARGET = yolo_dir

    if C.DEBUG_MODE and img is not None:
        vis = img.copy()
        color_map = [(0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0)]

        for item in parsed:
            x1, y1 = item["top_left"]
            x2, y2 = item["bottom_right"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

            kp_map = {}
            for kp in item["keypoints"]:
                idx = kp.get("idx", -1)
                kx, ky = kp["xy"]
                conf = kp.get("conf")
                kp_map[idx] = (kx, ky)
                color = color_map[idx % len(color_map)] if idx != -1 else (128, 128, 128)
                cv2.circle(vis, (int(kx), int(ky)), 4, color, -1)
                label = f"k{idx}" if conf is None else f"k{idx}:{conf:.2f}"
                cv2.putText(vis, label, (int(kx) + 5, int(ky) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            v23 = item.get("kp23_vector")
            if v23 is not None:
                v = np.array(v23, dtype=np.float64)
                origin = np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=np.float64)

                end = origin + v
                p0 = (int(round(float(origin[0]))), int(round(float(origin[1]))))
                p1 = (int(round(float(end[0]))), int(round(float(end[1]))))
                cv2.arrowedLine(vis, p0, p1, (255, 0, 255), 2, tipLength=0.1)
                cv2.putText(vis, "kp23", (p0[0] + 5, p0[1] + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        plt.figure("YOLO 4pt keypoints", figsize=(10, 8))
        plt.clf()
        plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        plt.title("YOLO 4pt keypoints and reconstructed kp2-kp3 vector")
        plt.axis("off")
        plt.tight_layout()
        plt.show(block=True)

    return parsed, yolo_angles, box_lengths, yolo_dir









def get_yolo_model(model_path):
    model_path = str(model_path)
    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = YOLO(model_path)
    return _MODEL_CACHE[model_path]


def extract_yolo_detections(curr_image, model_path = MODEL_PATH, imgsz=2048):
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
    model = get_yolo_model(model_path)
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


def visualize_detections(img, result = None, detections = None):
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


def detect_single_scanline_keypoints(image, imgsz=256, conf=0.10, iou=0.5):
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
    model = get_yolo_model(SINGLE_SCANLINE_MODEL_PATH)

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

    if C.DEBUG_MODE and False:
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
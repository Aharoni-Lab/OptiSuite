from pathlib import Path
import cv2
from ultralytics import YOLO
import numpy as np
import matplotlib.pyplot as plt

_MODEL_CACHE = {}
MODEL_PATH = Path("./models/best21.pt")


def get_yolo_model(model_path):
    model_path = str(model_path)
    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = YOLO(model_path)
    return _MODEL_CACHE[model_path]


def extract_yolo_detections(image_path, model_path = MODEL_PATH, imgsz=2048):
    """
    Extract YOLO detections including bounding boxes and keypoints for each detected object.
    
    Returns:
        Tuple of:
        - detections: List of dicts with keys 'bbox' and 'keypoints'
            - 'bbox': (x1, y1, x2, y2) in pixel coordinates
            - 'keypoints': List of (x, y) tuples representing keypoints for the detection
        - result: YOLO result object
        - img: Original image
    """
    model = get_yolo_model(model_path)
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    
    results = model(str(image_path), imgsz=imgsz)
    result = results[0]
    
    detections = []
    
    # Extract bounding boxes and keypoints from YOLO results
    if result.boxes is not None:
        boxes = result.boxes.xyxy.cpu().numpy()  # Get bounding boxes in (x1, y1, x2, y2) format
        
        # Check if keypoints are available
        if result.keypoints is not None and result.keypoints.xy is not None:
            keypoints_data = result.keypoints.xy.cpu().numpy()  # Shape: (num_detections, num_keypoints, 2)
            
            for i, bbox in enumerate(boxes):
                x1, y1, x2, y2 = bbox
                # Get the 2 keypoints for this detection (take first 2 keypoints)
                # or the keypoints with highest confidence
                keypoints = keypoints_data[i]
                
                # Filter out invalid keypoints (usually marked with NaN or zero confidence)
                valid_keypoints = []
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
    #  show YOLO overlay if available
    if result is not None and False:
        annotated = result.plot(font_size=1, line_width=1)
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)

        plt.figure(figsize=(10, 8))
        plt.imshow(cv2.cvtColor(annotated_rgb, cv2.COLOR_BGR2RGB))
        plt.title("Custom Keypoint Visualization")
        plt.axis("off")  # Hide the axes
        plt.tight_layout()
        plt.show()
        return annotated_rgb

    img_vis = img.copy()

    if detections is None or len(detections) == 0:
        return img_vis
    
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


def main():
    model_path = MODEL_PATH
    if not model_path.exists():
        raise FileNotFoundError("Could not find trained YOLOv8 model at runs/detect/train/weights/best.pt or best.pt")

    test_dir = Path("test")
    if not test_dir.exists():
        raise FileNotFoundError(f"Test folder not found: {test_dir}")

    image_files = sorted(test_dir.glob("*.*"))
    if not image_files:
        raise FileNotFoundError(f"No images found in {test_dir}")

    image_path = image_files[0]
    print(f"Using image: {image_path}")

    # Extract YOLO detections
    detections, result, img = extract_yolo_detections(image_path, model_path, imgsz=2048)
    
    print(f"\nDetected {len(detections)} objects")
    for i, det in enumerate(detections):
        print(f"  Object {i}: bbox={det['bbox']}, keypoints={det['keypoints']}")
    
    # Visualize
    img_vis = visualize_detections(img, result, detections)

#main()
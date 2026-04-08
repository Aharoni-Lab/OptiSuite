from pathlib import Path
import cv2
from ultralytics import YOLO
import numpy as np
import matplotlib.pyplot as plt


def extract_yolo_detections(image_path, model_path, imgsz=2048):
    """
    Extract YOLO detections including bounding boxes and keypoints for each detected object.
    
    Args:
        image_path (str/Path): Path to the image
        model_path (str/Path): Path to the YOLO model
        imgsz (int): Image size for YOLO inference
    
    Returns:
        Tuple of:
        - detections: List of dicts with keys 'bbox' and 'keypoints'
            - 'bbox': (x1, y1, x2, y2) in pixel coordinates
            - 'keypoints': List of (x, y) tuples representing keypoints for the detection
        - result: YOLO result object
        - img: Original image
    """
    model = YOLO(str(model_path))
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
                
                # If we have keypoints, use them; otherwise use bbox corners
                if len(valid_keypoints) >= 2:
                    selected_keypoints = valid_keypoints[:2]
                else:
                    # Use center and one corner as fallback
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    selected_keypoints = [
                        (int(center_x), int(center_y)),
                        (int(x2), int(y2))
                    ]
                
                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'keypoints': selected_keypoints
                })
        else:
            # No keypoints available, use bbox centers as fallback
            for bbox in boxes:
                x1, y1, x2, y2 = bbox
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                corner_x, corner_y = x2, y2
                
                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'keypoints': [
                        (int(center_x), int(center_y)),
                        (int(corner_x), int(corner_y))
                    ]
                })
    
    return detections, result, img


def visualize_detections(img, detections, result=None):
    """
    Visualize YOLO detections with bounding boxes and keypoints.
    """
    img_vis = img.copy()
    
    # Draw bounding boxes and keypoints
    for detection in detections:
        bbox = detection['bbox']
        keypoints = detection['keypoints']
        
        # Draw bounding box
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img_vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw keypoints
        for i, (kx, ky) in enumerate(keypoints):
            cv2.circle(img_vis, (int(kx), int(ky)), 5, (0, 0, 255), -1)
            cv2.putText(img_vis, f"K{i}", (int(kx)+5, int(ky)-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    # Also show YOLO overlay if available
    if result is not None:
        annotated = result.plot(font_size=10, line_width=1)
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        return img_vis, annotated_rgb
    
    return img_vis, None


def main():
    model_path = Path("models\\best7.pt")
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
    img_vis, annotated_rgb = visualize_detections(img, detections, result)
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(cv2.cvtColor(img_vis, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Custom Keypoint Visualization")
    axes[0].axis("off")
    
    if annotated_rgb is not None:
        axes[1].imshow(annotated_rgb)
        axes[1].set_title("YOLO Result")
        axes[1].axis("off")
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
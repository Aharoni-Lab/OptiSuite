from pathlib import Path
import cv2
from ultralytics import YOLO

import matplotlib.pyplot as plt

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

    model = YOLO(str(model_path))
    results = model(str(image_path), imgsz=2048)
    result = results[0]

    # make the label smaller and box thinner
    annotated = result.plot(font_size=10, line_width=1)
    annotated = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(12, 8))
    plt.imshow(annotated)
    plt.axis("off")
    plt.title(f"YOLOv8 result: {image_path.name}")
    plt.show()

if __name__ == "__main__":
    main()
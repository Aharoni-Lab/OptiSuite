
import cv2
import numpy as np
import matplotlib.pyplot as plt
import math
import constants as C
from yolo_model import classify_resolution







def classify_pattern_resolution(img):
    return classify_resolution(img)


def find_pattern_crop(crop_dir, image_label, orientation, scan_index):
    candidates = [
        crop_dir / f"{image_label}_{orientation}_scan_{scan_index:03d}.png",
        crop_dir / f"{image_label}_{orientation}_scan_{scan_index}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def show_pattern_classification_results(evaluated_crops):
    if not evaluated_crops:
        return

    rows_per_page = max(1, int(C.PATTERN_CLASSIFICATION_ROWS_PER_PAGE))
    total_pages = math.ceil(len(evaluated_crops) / rows_per_page)

    for page_idx in range(total_pages):
        page_items = evaluated_crops[page_idx * rows_per_page:(page_idx + 1) * rows_per_page]
        rows = len(page_items)
        fig, axes = plt.subplots(
            rows,
            2,
            num=f"Pattern Classification Results {page_idx + 1}/{total_pages}",
            figsize=(9, max(3, rows * 2.4)),
            clear=True,
        )
        if rows == 1:
            axes = np.array([axes])

        fig.suptitle(f"Pattern Classification Results - Page {page_idx + 1}/{total_pages}", fontsize=12)

        for row_idx, item in enumerate(page_items):
            for col_idx, orientation in enumerate(("vertical", "horizontal")):
                ax = axes[row_idx, col_idx]
                img = item[f"{orientation}_img"]
                result = item[f"{orientation}_result"]
                if img is None:
                    ax.text(0.5, 0.5, "missing", ha="center", va="center", color="white")
                    ax.set_facecolor("black")
                else:
                    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

                ax.set_title(f"G{item['group']} E{item['element']} {orientation}: {result}", fontsize=9)
                ax.axis("off")

        fig.tight_layout(rect=[0, 0, 1, 0.96])

    plt.show(block=True)


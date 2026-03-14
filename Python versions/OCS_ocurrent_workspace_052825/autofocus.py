from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
#PIL is Python Imaging Library, for image processing
from PIL import Image


MetricName = Literal["laplacian_var", "tenengrad", "brenner"]


@dataclass(frozen=True)
class FocusResult:
    path: Path
    score: float


def _iter_candidate_images(root: Path) -> Iterable[Path]:
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _pick_two_images(root: Path) -> list[Path]:
    candidates = list(_iter_candidate_images(root))
    if len(candidates) < 2:
        raise SystemExit(
            f"Expected at least 2 images in {root.resolve()}, found {len(candidates)}. "
            f"Pass explicit image paths: python autofocus.py img1.png img2.png"
        )
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:2]


def _load_grayscale(path: Path, max_size: int | None) -> np.ndarray:
    # Returns float32 grayscale in [0, 1].
    img = Image.open(path)
    img = img.convert("L")
    if max_size and max(img.size) > max_size:
        img.thumbnail((max_size, max_size), resample=Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr


def _center_crop_fraction(gray: np.ndarray, fraction: float) -> np.ndarray:
    if not (0.0 < fraction <= 1.0):
        raise ValueError("--roi must be in (0, 1].")
    if fraction >= 1.0:
        return gray
    h, w = gray.shape[:2]
    ch = max(1, int(round(h * fraction)))
    cw = max(1, int(round(w * fraction)))
    y0 = (h - ch) // 2
    x0 = (w - cw) // 2
    return gray[y0 : y0 + ch, x0 : x0 + cw]


def _conv3x3_reflect(gray: np.ndarray, k: np.ndarray) -> np.ndarray:
    # Minimal 2D convolution for 3x3 kernels using reflect padding.
    if k.shape != (3, 3):
        raise ValueError("Kernel must be 3x3.")
    p = np.pad(gray, ((1, 1), (1, 1)), mode="reflect")
    out = (
        k[0, 0] * p[0:-2, 0:-2]
        + k[0, 1] * p[0:-2, 1:-1]
        + k[0, 2] * p[0:-2, 2:]
        + k[1, 0] * p[1:-1, 0:-2]
        + k[1, 1] * p[1:-1, 1:-1]
        + k[1, 2] * p[1:-1, 2:]
        + k[2, 0] * p[2:, 0:-2]
        + k[2, 1] * p[2:, 1:-1]
        + k[2, 2] * p[2:, 2:]
    )
    return out


def focus_laplacian_variance(gray: np.ndarray) -> float:
    # Variance of Laplacian: higher => sharper (more high-frequency content).
    k = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    lap = _conv3x3_reflect(gray, k)
    return float(lap.var())


def focus_tenengrad(gray: np.ndarray) -> float:
    # Tenengrad: mean squared gradient magnitude (Sobel).
    kx = np.array([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], dtype=np.float32)
    ky = np.array([[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]], dtype=np.float32)
    gx = _conv3x3_reflect(gray, kx)
    gy = _conv3x3_reflect(gray, ky)
    g2 = gx * gx + gy * gy
    return float(g2.mean())


def focus_brenner(gray: np.ndarray) -> float:
    # Brenner gradient: sum of squared differences with 2-pixel shift.
    if gray.shape[1] < 3:
        return 0.0
    d = gray[:, 2:] - gray[:, :-2]
    return float((d * d).mean())


def focus_score(gray: np.ndarray, metric: MetricName) -> float:
    if metric == "laplacian_var":
        return focus_laplacian_variance(gray)
    if metric == "tenengrad":
        return focus_tenengrad(gray)
    if metric == "brenner":
        return focus_brenner(gray)
    raise ValueError(f"Unknown metric: {metric}")


def score_image(path: Path, metric: MetricName, roi: float, max_size: int | None) -> FocusResult:
    gray = _load_grayscale(path, max_size=max_size)
    gray = _center_crop_fraction(gray, roi)
    score = focus_score(gray, metric=metric)
    return FocusResult(path=path, score=score)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare microscope images and pick the most in-focus one (higher focus score wins)."
    )
    p.add_argument(
        "images",
        nargs="*",
        help="Two image paths to compare. If omitted, uses the 2 most recently modified images in the current folder.",
    )
    p.add_argument(
        "--metric",
        choices=["laplacian_var", "tenengrad", "brenner"],
        default="laplacian_var",
        help="Focus metric to use (default: laplacian_var).",
    )
    p.add_argument(
        "--roi",
        type=float,
        default=0.8,
        help="Center crop fraction in (0,1] to reduce edge/vignetting effects (default: 0.8).",
    )
    p.add_argument(
        "--max-size",
        type=int,
        default=1024,
        help="Downscale so longest side <= this for speed (default: 1024). Use 0 to disable.",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Score all images in the current folder (prints sorted list).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    metric: MetricName = args.metric
    roi: float = float(args.roi)
    max_size: int | None = None if int(args.max_size) <= 0 else int(args.max_size)

    cwd = Path(os.getcwd())

    if args.all:
        paths = list(_iter_candidate_images(cwd))
        if not paths:
            raise SystemExit(f"No images found in {cwd.resolve()}")
        results = [score_image(p, metric=metric, roi=roi, max_size=max_size) for p in paths]
        results.sort(key=lambda r: r.score, reverse=True)
        for r in results:
            print(f"{r.score:.6g}\t{r.path.name}")
        print(f"\nMost in-focus: {results[0].path.name}")
        return 0

    if args.images:
        paths = [Path(x) for x in args.images]
    else:
        paths = _pick_two_images(cwd)

    if len(paths) != 2:
        raise SystemExit(f"Expected exactly 2 images (or use --all). Got {len(paths)}.")

    r1 = score_image(paths[0], metric=metric, roi=roi, max_size=max_size)
    r2 = score_image(paths[1], metric=metric, roi=roi, max_size=max_size)

    print(f"{r1.path.name}: {r1.score:.6g}")
    print(f"{r2.path.name}: {r2.score:.6g}")

    winner = r1 if r1.score >= r2.score else r2
    print(f"\nIn focus: {winner.path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


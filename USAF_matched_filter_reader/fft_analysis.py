#!/usr/bin/env python3
"""
2-D Fourier transform of a USAF target image (synthetic or measured).

Outputs (next to the image, or in --out-dir):
  <stem>_fft.png        log-magnitude spectrum (DC at centre), 8-bit
  <stem>_fft_plot.png   spectrum + radially averaged spectrum + fx / fy axis profiles,
                        with USAF group frequencies marked when the pixel size is known
  <stem>_fft_radial.csv radially averaged spectrum

Pixel size is taken from --pixel-size, or from the generator's JSON sidecar
(<stem>.json with "pixel_size_um"); otherwise frequencies are in cycles/px.
Large images are block-averaged down to --max-size before the FFT.

Usage:
    python fft_analysis.py output/USAF1951_G2-G7_0.5um_px.png
    python fft_analysis.py output/USAF-Test-1.png --pixel-size 1.1
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import fft as sfft

Image.MAX_IMAGE_PIXELS = None


def load_gray(path: Path) -> np.ndarray:
    a = np.asarray(Image.open(path))
    if a.ndim == 3:
        a = a.astype(np.float64)
        a = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return a.astype(np.float64)


def block_mean(a: np.ndarray, b: int) -> np.ndarray:
    if b <= 1:
        return a
    H, W = (a.shape[0] // b) * b, (a.shape[1] // b) * b
    return a[:H, :W].reshape(H // b, b, W // b, b).mean(axis=(1, 3))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--pixel-size", type=float, default=None, help="object-space pixel size in µm")
    ap.add_argument("--max-size", type=int, default=4096, help="bin image down so the long side <= this")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    img = load_gray(args.image)
    px = args.pixel_size
    sidecar = args.image.with_suffix(".json")
    if px is None and sidecar.exists():
        try:
            px = float(json.loads(sidecar.read_text())["pixel_size_um"])
        except (KeyError, ValueError, json.JSONDecodeError):
            px = None

    b = int(np.ceil(max(img.shape) / args.max_size))
    img = block_mean(img, b)
    if px is not None:
        px *= b
    H, W = img.shape

    # remove DC, apply 2-D Hann window to suppress edge leakage
    win = np.outer(np.hanning(H), np.hanning(W))
    F = sfft.fftshift(sfft.fft2((img - img.mean()) * win, workers=-1))
    mag = np.abs(F)
    logmag = np.log10(mag + mag.max() * 1e-9)

    # frequency axes in cycles/px, converted to lp/mm when pixel size is known
    fy = sfft.fftshift(sfft.fftfreq(H))
    fx = sfft.fftshift(sfft.fftfreq(W))
    to_lpmm = (1000.0 / px) if px else 1.0
    unit = "lp/mm" if px else "cycles/px"

    # radial average (isotropic frequency in cycles/px)
    FY, FX = np.meshgrid(fy, fx, indexing="ij")
    fr = np.hypot(FX, FY)
    nb = min(H, W) // 2
    edges = np.linspace(0, 0.5, nb + 1)
    idx = np.clip(np.digitize(fr.ravel(), edges) - 1, 0, nb - 1)
    valid = fr.ravel() <= 0.5
    sums = np.bincount(idx[valid], weights=mag.ravel()[valid] ** 2, minlength=nb)
    cnts = np.bincount(idx[valid], minlength=nb)
    radial = np.sqrt(sums / np.maximum(cnts, 1))
    fcent = 0.5 * (edges[:-1] + edges[1:])

    # profiles along the fx and fy axes (bars put their energy there), ±2-bin band
    cy, cx = H // 2, W // 2
    prof_x = mag[cy - 2:cy + 3, cx:].mean(axis=0)
    prof_y = mag[cy:, cx - 2:cx + 3].mean(axis=1)

    out_dir = args.out_dir or args.image.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem

    lo, hi = np.percentile(logmag, [1, 99.95])
    Image.fromarray((np.clip((logmag - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)).save(
        out_dir / f"{stem}_fft.png")

    with open(out_dir / f"{stem}_fft_radial.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow([f"frequency_{unit.replace('/', '_per_')}", "amplitude"])
        for f, a in zip(fcent * to_lpmm, radial):
            wr.writerow([f"{f:.6g}", f"{a:.6g}"])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 3, figsize=(17, 5.2))
    ext = [fx[0] * to_lpmm, fx[-1] * to_lpmm, fy[-1] * to_lpmm, fy[0] * to_lpmm]
    axs[0].imshow(logmag, cmap="magma", vmin=lo, vmax=hi, extent=ext)
    axs[0].set_title("log10 |FFT| (Hann-windowed)")
    axs[0].set_xlabel(f"fx [{unit}]")
    axs[0].set_ylabel(f"fy [{unit}]")

    axs[1].loglog(fcent[1:] * to_lpmm, radial[1:], lw=1)
    axs[1].set_title("Radially averaged spectrum")
    axs[2].loglog(fx[cx + 1:] * to_lpmm, prof_x[1:], lw=1, label="along fx (vertical bars)")
    axs[2].loglog(fy[cy + 1:] * to_lpmm, prof_y[1:], lw=1, label="along fy (horizontal bars)")
    axs[2].set_title("Axis profiles")
    axs[2].legend(loc="lower left", fontsize=8)
    for ax in axs[1:]:
        ax.set_xlabel(f"frequency [{unit}]")
        ax.set_ylabel("amplitude")
        ax.grid(True, which="both", alpha=0.25)
        if px:
            nyq = 0.5 * to_lpmm
            for g in range(-2, 10):
                f = 2.0 ** g
                if fcent[1] * to_lpmm < f < nyq:
                    ax.axvline(f, color="tab:green", alpha=0.35, lw=0.8)
                    ax.text(f, ax.get_ylim()[1], f" G{g}", color="tab:green", fontsize=7, va="top")
            ax.axvline(nyq, color="tab:red", ls="--", lw=0.8)
    fig.suptitle(f"{args.image.name}  ({W}x{H} px after {b}x binning"
                 + (f", {px:.3g} µm/px)" if px else ", pixel size unknown)"))
    fig.tight_layout()
    fig.savefig(out_dir / f"{stem}_fft_plot.png", dpi=130)
    print(f"Saved {out_dir / (stem + '_fft.png')}, {stem}_fft_plot.png, {stem}_fft_radial.csv")


if __name__ == "__main__":
    main()

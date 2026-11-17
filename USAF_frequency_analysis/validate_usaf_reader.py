#!/usr/bin/env python3
"""
Validate usaf_reader against simulated microscope images with known ground truth.

For each case the synthetic slide is rendered, cropped to a microscope-like field
of view around the central groups, rotated (90° + a small angle) and mirrored,
blurred with a Gaussian PSF, integrated onto camera pixels, given vignetting, a
black offset and noise. The true Michelson contrast of every element follows
analytically from the PSF (3 bars ⊗ Gaussian ⊗ pixel box), so the reader's
identification, contrast and resolution-limit answer can be checked exactly.

Usage:  python validate_usaf_reader.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.special import erf

sys.path.insert(0, str(Path(__file__).parent))
import generate_usaf_target as gen          # noqa: E402
import usaf_reader as rd                    # noqa: E402

RENDER_PX = 0.5      # µm, fine render
BIN = 2              # camera pixel = RENDER_PX * BIN


def true_contrast(w: float, sigma: float, pix: float, gain: float, offset: float) -> float:
    """Michelson contrast of 3 bright bars (width w, gaps w) after Gaussian PSF and pixel box."""
    def level(x0: float) -> float:
        # average over the pixel box of the Gaussian-blurred bar indicator
        xs = x0 + np.linspace(-pix / 2, pix / 2, 41)
        v = np.zeros_like(xs)
        for c in (-2 * w, 0.0, 2 * w):
            a, b = c - w / 2, c + w / 2
            if sigma > 0:
                v += 0.5 * (erf((b - xs) / (math.sqrt(2) * sigma)) - erf((a - xs) / (math.sqrt(2) * sigma)))
            else:
                v += ((xs >= a) & (xs < b)).astype(float)
        return float(v.mean())
    ib = np.mean([level(c) for c in (-2 * w, 0.0, 2 * w)])
    ig = np.mean([level(c) for c in (-w, w)])
    return (gain * (ib - ig)) / (gain * (ib + ig) + 2 * offset)


def simulate(sigma_um: float, rot_small: float, mirror: bool, rot90: int, seed: int = 0):
    block = gen.build_target(2, 7)
    # field of view: 2.2 mm square centred on the pair (4,5)
    sq4 = next(r for g, r in block.squares if g == 4)
    cx, cy = (sq4.x0 + sq4.x1) / 2, (sq4.y0 + sq4.y1) / 2 + 250
    fov = 2200.0
    crop = gen.Block(width=fov, height=fov)
    crop.place(block, -(cx - fov / 2), -(cy - fov / 2))
    chrome, _ = gen.render(crop, RENDER_PX, 0.0)

    if rot_small:
        chrome = ndimage.rotate(chrome, rot_small, reshape=False, order=1, mode="constant")
    chrome = ndimage.gaussian_filter(chrome, sigma_um / RENDER_PX)
    H, W = (chrome.shape[0] // BIN) * BIN, (chrome.shape[1] // BIN) * BIN
    img = chrome[:H, :W].reshape(H // BIN, BIN, W // BIN, BIN).mean(axis=(1, 3))

    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    r2 = ((xx - img.shape[1] / 2) ** 2 + (yy - img.shape[0] / 2) ** 2) / (0.5 * max(img.shape)) ** 2
    gain_map = 1.0 - 0.3 * r2
    offset = 0.06
    img = gain_map * img + offset
    rng = np.random.default_rng(seed)
    img = img + rng.normal(0, 0.008, img.shape)

    if mirror:
        img = img[:, ::-1]
    img = np.rot90(img, rot90)
    return img, offset


def run_case(name: str, sigma: float, rot_small: float, mirror: bool, rot90: int,
             pixel_hint: float | None, group_hint: int | None, dark: bool = False,
             thr: float = 0.2) -> bool:
    pix = RENDER_PX * BIN
    img, offset = simulate(sigma, rot_small, mirror, rot90)
    dark_frame = None
    if dark:
        # camera dark frame: the same offset plus independent read noise, light blocked
        dark_frame = offset + np.random.default_rng(1).normal(0, 0.008, img.shape)
    res = rd.analyze(img, contrast=thr, pixel_size=pixel_hint, group_hint=group_hint, verbose=False,
                     dark_frame=dark_frame)

    errs, rows_out = [], []
    for r in res["elements"]:
        w = r["line_width_um"]
        # gain at the element (vignetting) - use measured position in the transformed frame
        pts = np.array(r["polygon_H_px"] + r["polygon_V_px"])
        x, y = pts.mean(0)
        r2 = ((x - img.shape[1] / 2) ** 2 + (y - img.shape[0] / 2) ** 2) / (0.5 * max(img.shape)) ** 2
        ct = true_contrast(w, sigma, pix, 1.0 - 0.3 * r2, offset - res["black_level"])
        if not r["undersampled"]:
            errs.append(max(abs(r["contrast_H"] - ct), abs(r["contrast_V"] - ct)))
        rows_out.append((r["group"], r["element"], r["detected"], ct, r["contrast_H"], r["contrast_V"]))

    # first-fail rule, coarse -> fine, stepping over one isolated failure (as the reader does)
    seq = sorted(rows_out, key=lambda t: 6 * t[0] + t[1])
    ok_t = [ct >= thr and 2 * rd.line_width_um_k(6 * g + e - 1) / pix >= 2 for g, e, _, ct, _, _ in seq]
    true_lim, skips = None, 0
    for i, (g, e, *_rest) in enumerate(seq):
        if ok_t[i]:
            true_lim = (g, e)
        elif skips < 1 and i + 1 < len(seq) and ok_t[i + 1]:
            skips += 1
        else:
            break
    got = (res["result"]["group"], res["result"]["element"]) if res["result"] else None
    px_err = res["pixel_size_um_fitted"] / pix - 1

    ok = (got == true_lim) and max(errs) < 0.05 and abs(px_err) < 0.01
    print(f"\n=== {name}: σ={sigma} µm, rot {rot90 * 90}°+{rot_small}°, mirror={mirror}, "
          f"pixel hint={pixel_hint}, group hint={group_hint}, dark frame={dark}")
    print(f"  identification: {res['identification']}")
    print(f"  pixel size fitted {res['pixel_size_um_fitted']:.4f} µm (true {pix}, err {100 * px_err:+.2f} %)")
    print(f"  elements measured: {len(rows_out)} ({sum(1 for r in rows_out if r[2])} detected); "
          f"max |contrast error| {max(errs):.3f}, mean {np.mean(errs):.3f}")
    print(f"  limit @ {100 * thr:.0f}%: reader {got}  truth {true_lim}  -> {'OK' if ok else 'MISMATCH'}")
    for g, e, det, ct, ch, cv in rows_out:
        if abs(ch - ct) > 0.05 or abs(cv - ct) > 0.05:
            print(f"    large error G{g}E{e} det={det}: true {ct:.3f}  H {ch:.3f}  V {cv:.3f}")
    return ok


def main() -> None:
    cases = [
        ("A  sharp-ish, pixel hint 30% off", 1.2, 3.0, True, 1, 1.3, None),
        ("B  blurred, group hint", 2.5, -2.0, False, 3, None, 4),
        ("C  blurred, no hint at all", 2.0, 0.0, True, 2, None, None),
        ("D  as C, with a dark frame", 2.0, 0.0, True, 2, None, None, True),
    ]
    results = [run_case(*c) for c in cases]
    print(f"\n{sum(results)}/{len(results)} cases passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

"""
Simulated STIMscope-like USAF images with exact ground truth.

Geometry copies the labelled images in the repo: groups 2-7 in view, target mirrored and
tilted ~30 deg, 2.4 um camera pixels, 2592 x 1944 px, 8-bit, bright bars on dark.
Optics: Gaussian PSF (sigma), plus a constant stray-light floor, read noise.
Truth: Michelson contrast of every element from the analytic model
       (3 bars (x) Gaussian (x) rotated square pixel), measured on the raw image;
       limit = last element before the first one below 20 % (coarse -> fine).
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.special import erf

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2]))
import generate_usaf_target as gen

OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "images/synthetic"); OUT.mkdir(parents=True, exist_ok=True)
REN = 1.2; BIN = 2; PIX = REN * BIN          # 2.4 um camera pixels
W_PX, H_PX = 2592, 1944
GAIN, FLOOR, NOISE = 200.0, 12.0, 1.5         # 8-bit counts

block = gen.build_target(2, 7)
sq4 = next(r for g, r in block.squares if g == 4)
C0 = np.array([(sq4.x0 + sq4.x1) / 2, (sq4.y0 + sq4.y1) / 2])


def lw(k): return 500.0 / 2 ** (k / 6)


def true_contrast(w, sigma, theta_deg):
    # pixel footprint projected on the bar normal: average over a rotated square pixel
    t = math.radians(theta_deg)
    g = (np.arange(15) + 0.5) / 15 - 0.5
    U, V = np.meshgrid(g * PIX, g * PIX)
    proj = (U * math.cos(t) + V * math.sin(t)).ravel()
    def level(x0):
        xs = x0 + proj
        v = np.zeros_like(xs)
        for c in (-2 * w, 0.0, 2 * w):
            a, b = c - w / 2, c + w / 2
            v += 0.5 * (erf((b - xs) / (math.sqrt(2) * sigma)) - erf((a - xs) / (math.sqrt(2) * sigma)))
        return float(v.mean())
    ib = np.mean([level(c) for c in (-2 * w, 0.0, 2 * w)])
    ig = np.mean([level(c) for c in (-w, w)])
    return (GAIN * (ib - ig)) / (GAIN * (ib + ig) + 2 * FLOOR)


def make(name, sigma, angle, mirror, shift=(0.0, 0.0), seed=0):
    fov = np.array([W_PX, H_PX]) * PIX * 1.45           # margin so rotation leaves no empty corners
    c = C0 + np.array([0.0, 900.0]) + np.array(shift)
    crop = gen.Block(width=fov[0], height=fov[1])
    crop.place(block, -(c[0] - fov[0] / 2), -(c[1] - fov[1] / 2))
    chrome, _ = gen.render(crop, REN, 0.0)
    chrome = ndimage.rotate(chrome, angle, reshape=False, order=1, mode="constant")
    chrome = ndimage.gaussian_filter(chrome, sigma / REN)
    cy, cx = chrome.shape[0] // 2, chrome.shape[1] // 2
    h, w = H_PX * BIN, W_PX * BIN
    chrome = chrome[cy - h // 2: cy - h // 2 + h, cx - w // 2: cx - w // 2 + w]
    img = chrome.reshape(H_PX, BIN, W_PX, BIN).mean(axis=(1, 3))
    rng = np.random.default_rng(seed)
    img = np.clip(np.rint(FLOOR + GAIN * img + rng.normal(0, NOISE, img.shape)), 0, 255).astype(np.uint8)
    if mirror:
        img = img[:, ::-1]
    Image.fromarray(img).save(OUT / f"{name}.png")

    # linear interpolation in the rotation adds a little blur: var ~ REN^2/6
    s_eff = math.sqrt(sigma ** 2 + REN ** 2 / 6)
    rows, lim, stopped = [], None, False
    for k in range(12, 48):
        gg, e = divmod(k, 6); e += 1
        ct = true_contrast(lw(k), s_eff, angle)
        ok = ct >= 0.2 and 2 * lw(k) / PIX >= 2
        rows.append({"group": gg, "element": e, "k": k, "contrast": round(ct, 4), "passes": bool(ok)})
        if not stopped:
            if ok: lim = (gg, e)
            else: stopped = True
    truth = {"image": f"{name}.png", "sigma_um": sigma, "sigma_eff_um": round(s_eff, 3), "angle_deg": angle,
             "mirrored": mirror, "pixel_um": PIX, "truth_limit": lim, "elements": rows}
    (OUT / f"{name}.json").write_text(json.dumps(truth, indent=1))
    print(name, "sigma", sigma, "truth", lim)


if __name__ == "__main__":
    sigmas = [2.0, 3.0, 4.0, 5.5, 7.0, 9.0]
    for i, s in enumerate(sigmas):
        make(f"synA_s{s}", s, -28.0, True, seed=i)
        make(f"synB_s{s}", s, -34.0, True, shift=(-300.0, 250.0), seed=10 + i)
    for i, s in enumerate([2.0, 4.0, 7.0]):
        make(f"synC_s{s}", s, 12.0, False, shift=(200.0, -150.0), seed=20 + i)

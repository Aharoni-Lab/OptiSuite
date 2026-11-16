#!/usr/bin/env python3
"""
Read a microscope image of a 1951 USAF target: find every bar element, identify
its group/element, measure its contrast, and report the finest element that
meets a requested contrast (default 20 %).

Why not a global FFT?
    A global spectrum mixes all 36 elements (plus digits, square, illumination)
    and loses *where* each frequency came from, so it cannot say which element
    still has 20 % contrast. Instead we use local, matched-frequency analysis:

Pipeline
    1. Orientation  - dominant edge angle (structure of gradients, folded mod 90°);
                      the image is de-rotated so bars are axis-aligned.
                      90° rotations and mirroring need no special handling.
    2. Detection    - matched filter: normalised cross-correlation (NCC) with an
                      ideal 3-bar template over a log-spaced bank of line widths
                      (image pyramid keeps it fast). NCC is contrast-invariant,
                      so low-contrast but real elements are still found.
    3. Refinement   - each hit is refined in position and line width (sub-pixel).
    4. Scale lattice- USAF line widths form an exact lattice: w ∝ 2^(-k/6),
                      k = 6·group + element - 1. Fitting the lattice phase to all
                      hits gives every hit's *relative* index exactly, without
                      knowing the pixel size.
    5. Pairing      - a real element has a horizontal- AND a vertical-line set of
                      equal width ~7 w apart; unpaired hits (digits etc.) are dropped.
    6. Identification
                    - the slide layout puts consecutive elements next to each
                      other in a column, except at three places per 2-group
                      period (element 1 of every group, element 2 of even
                      groups). Matching where the "column breaks" occur fixes
                      k modulo 12. The remaining 2-group ambiguity (the layout is
                      self-similar ×4) is resolved by an approximate pixel size
                      (good to within ×/÷2), a group hint, or - as a last resort -
                      by assuming the finest groups on the slide are visible.
    7. Prediction   - elements too blurred (or too small) to detect are located from
                      the slide geometry: each column is a geometric series, and each
                      group pair is a 1/4-scale copy of the pair two groups coarser.
                      Tiny detections (< ~3 px line width, where width alone can't
                      tell neighbouring elements apart) are re-checked against these
                      predicted positions. So the contrast fall-off past the
                      resolution limit is measured, not assumed.
    8. Contrast     - per bar set, a profile across the bars (averaged over the
                      central 60 % of the bar length) gives
                        Michelson contrast  C = (I_bar - I_gap)/(I_bar + I_gap)
                      using the 3 bar centres and 2 inner gaps (signed: negative =
                      contrast reversal / spurious resolution), and a lock-in
                      (least-squares sine fit at the known frequency) modulation.
                      An element passes when both orientations reach the threshold.

Usage
    python usaf_reader.py image.png                         # 20 % threshold
    python usaf_reader.py image.png --contrast 0.3 --pixel-size 1.1
    python usaf_reader.py image.png --magnification 10 --camera-pixel 3.45
    python usaf_reader.py image.png --coarsest-group 4      # biggest group you can see

Outputs (in --out-dir, default: <image folder>/usaf_results/):
    <stem>_usaf.json     everything, incl. per-element contrast and bounding boxes
    <stem>_usaf.csv      per-element table
    <stem>_overlay.png   detections drawn on the image (green pass, red fail)
    <stem>_ctf.png       contrast vs spatial frequency (CTF) with the threshold
    <stem>_scanlines.png raw centre scan line (pixel values) vs. the reader's profile, per bar set
    <stem>_scanlines.csv the scan-line and profile values behind that plot
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.spatial import cKDTree

Image.MAX_IMAGE_PIXELS = None

# USAF k index: k = 6*group + element - 1 ; slide spans group -2 .. 7
K_MIN, K_MAX = 6 * -2 + 0, 6 * 7 + 5
HV_DIST = (5.0, 9.5)        # centre distance between H and V sets of one element, in w
ADJ_DIST = 12.5             # consecutive elements closer than this (in w) are column neighbours


def lp_per_mm_k(k: int) -> float:
    return 2.0 ** (k / 6.0)


def line_width_um_k(k: int) -> float:
    return 500.0 / lp_per_mm_k(k)


def k_to_ge(k: int) -> tuple[int, int]:
    return k // 6, k % 6 + 1


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_gray(path: Path) -> np.ndarray:
    a = np.asarray(Image.open(path))
    if a.ndim == 3:
        a = a.astype(np.float64)
        a = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return a.astype(np.float64)


# ---------------------------------------------------------------------------
# 1. Orientation
# ---------------------------------------------------------------------------

def _edge_angle(img: np.ndarray) -> float:
    """Dominant edge orientation folded to (-45°, 45°], degrees."""
    sm = ndimage.gaussian_filter(img, 1.5)
    gx, gy = ndimage.sobel(sm, 1), ndimage.sobel(sm, 0)
    m2 = gx * gx + gy * gy
    mask = m2 > np.percentile(m2, 95)
    z = np.sum(m2[mask] * np.exp(4j * np.arctan2(gy[mask], gx[mask])))
    return math.degrees(np.angle(z) / 4.0)


@dataclass
class Frame:
    """Maps de-rotated (working) coordinates <-> original image coordinates."""
    angle: float
    cy: float
    cx: float

    def matrix(self) -> np.ndarray:
        a = math.radians(self.angle)
        return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])

    def to_original(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        R = self.matrix()
        dy, dx = np.asarray(y) - self.cy, np.asarray(x) - self.cx
        oy = R[0, 0] * dy + R[0, 1] * dx + self.cy
        ox = R[1, 0] * dy + R[1, 1] * dx + self.cx
        return ox, oy


def derotate(img: np.ndarray) -> tuple[np.ndarray, Frame]:
    theta = _edge_angle(img)
    cy, cx = (img.shape[0] - 1) / 2, (img.shape[1] - 1) / 2
    best = (img, Frame(0.0, cy, cx), abs(theta))
    if abs(theta) > 0.3:
        for ang in (theta, -theta):
            fr = Frame(ang, cy, cx)
            R = fr.matrix()
            c = np.array([cy, cx])
            out = ndimage.affine_transform(img, R, offset=c - R @ c, order=1, mode="nearest")
            res = abs(_edge_angle(out))
            if res < best[2]:
                best = (out, fr, res)
    return best[0], best[1]


# ---------------------------------------------------------------------------
# 2. Detection (matched filter bank)
# ---------------------------------------------------------------------------

@dataclass
class Det:
    x: float
    y: float
    w: float
    axis: str      # 'x': vertical bars (profile along x);  'y': horizontal bars
    score: float   # signed NCC (+ bright bars, - dark bars)


def _bar_coverage(u: np.ndarray, w: float, half: float) -> np.ndarray:
    """Fraction of [u-half, u+half] covered by the three bars centred at 0, ±2w."""
    cov = np.zeros_like(u, dtype=np.float64)
    for c in (-2 * w, 0.0, 2 * w):
        a, b = c - 0.5 * w, c + 0.5 * w
        cov += np.clip(np.minimum(b, u + half) - np.maximum(a, u - half), 0, None)
    return cov / (2 * half)


def _ncc_map(img: np.ndarray, img2: np.ndarray, w: float, axis: str, eps: float) -> np.ndarray:
    R = int(math.ceil(3.5 * w))
    p = _bar_coverage(np.arange(-R, R + 1, dtype=np.float64), w, 0.5)
    p -= p.mean()
    Ly = 2 * int(round(2.0 * w)) + 1          # ~80 % of the 5w bar length
    nx = 2 * R + 1
    if axis == "x":
        s = ndimage.uniform_filter1d(img, Ly, axis=0, mode="nearest") * Ly
        num = ndimage.correlate1d(s, p, axis=1, mode="nearest")
        size = (Ly, nx)
    else:
        s = ndimage.uniform_filter1d(img, Ly, axis=1, mode="nearest") * Ly
        num = ndimage.correlate1d(s, p, axis=0, mode="nearest")
        size = (nx, Ly)
    n = Ly * nx
    m1 = ndimage.uniform_filter(img, size, mode="nearest")
    m2 = ndimage.uniform_filter(img2, size, mode="nearest")
    var = np.maximum(n * (m2 - m1 * m1), n * eps)
    ncc = num / np.sqrt(Ly * float(p @ p) * var)
    hy, hx = size[0] // 2 + 1, size[1] // 2 + 1
    ncc[:hy] = 0
    ncc[-hy:] = 0
    ncc[:, :hx] = 0
    ncc[:, -hx:] = 0
    return ncc


def _block_mean(a: np.ndarray, d: int) -> np.ndarray:
    if d == 1:
        return a
    H, W = (a.shape[0] // d) * d, (a.shape[1] // d) * d
    return a[:H, :W].reshape(H // d, d, W // d, d).mean(axis=(1, 3))


def detect(img: np.ndarray, w_min: float, w_max: float, thr: float, steps_per_octave: int = 12) -> list[Det]:
    cands: list[Det] = []
    n_oct = math.log2(w_max / w_min)
    ws = w_min * 2.0 ** (np.arange(int(n_oct * steps_per_octave) + 1) / steps_per_octave)
    pyramid: dict[int, tuple[np.ndarray, np.ndarray, float]] = {}
    gvar = float(np.var(img))
    for w in ws:
        L = 0 if w < 4 else int(math.floor(math.log2(w / 2.0)))
        d = 2 ** L
        if d not in pyramid:
            im = _block_mean(img, d)
            pyramid[d] = (im, im * im, 1e-4 * gvar)
        im, im2, eps = pyramid[d]
        we = w / d
        for axis in ("x", "y"):
            ncc = _ncc_map(im, im2, we, axis, eps)
            a = np.abs(ncc)
            peaks = (a >= thr) & (a == ndimage.maximum_filter(a, size=3))
            ys, xs = np.nonzero(peaks)
            for yy, xx in zip(ys, xs):
                cands.append(Det((xx + 0.5) * d - 0.5, (yy + 0.5) * d - 0.5, float(w), axis, float(ncc[yy, xx])))
    return cands


def nms(dets: list[Det], radius: float) -> list[Det]:
    """Greedy non-maximum suppression per orientation; radius in units of w."""
    out: list[Det] = []
    for axis in ("x", "y"):
        ds = sorted((d for d in dets if d.axis == axis), key=lambda d: -abs(d.score))
        if not ds:
            continue
        pts = np.array([[d.x, d.y] for d in ds])
        tree = cKDTree(pts)
        sup = np.zeros(len(ds), bool)
        acc_xy, acc_w = [], []
        for i, d in enumerate(ds):
            if sup[i]:
                continue
            if acc_xy:
                axy, aw = np.array(acc_xy), np.array(acc_w)
                if np.any(np.hypot(axy[:, 0] - d.x, axy[:, 1] - d.y) < radius * np.maximum(aw, d.w)):
                    sup[i] = True
                    continue
            out.append(d)
            acc_xy.append((d.x, d.y))
            acc_w.append(d.w)
            sup[tree.query_ball_point((d.x, d.y), radius * d.w)] = True
    return out


# ---------------------------------------------------------------------------
# 3. Sub-pixel refinement
# ---------------------------------------------------------------------------

def _grid(x: float, y: float, w: float, axis: str, u: np.ndarray, v: np.ndarray):
    U, V = np.meshgrid(u, v)
    return (x + U, y + V) if axis == "x" else (x + V, y + U)


def sample_ncc(img: np.ndarray, x: float, y: float, w: float, axis: str) -> float:
    """NCC with the full 2-D 3-bar template (bars of length 5w inside a 7w x 7w window),
    so position is pinned both across and along the bars."""
    du = min(0.5, w / 6)
    dv = min(1.0, max(0.5, w / 6))
    u = np.arange(-3.5 * w, 3.5 * w + 1e-9, du)
    v = np.arange(-3.5 * w, 3.5 * w + 1e-9, dv)
    X, Y = _grid(x, y, w, axis, u, v)
    P = ndimage.map_coordinates(img, [Y.ravel(), X.ravel()], order=1, mode="nearest").reshape(X.shape)
    tu = _bar_coverage(u, w, du / 2)
    tv = np.clip(np.minimum(2.5 * w, v + dv / 2) - np.maximum(-2.5 * w, v - dv / 2), 0, None) / dv
    T = tv[:, None] * tu[None, :]
    T = T - T.mean()
    P = P - P.mean()
    den = math.sqrt(float((T * T).sum()) * float((P * P).sum()))
    return float((P * T).sum() / den) if den > 0 else 0.0


def refine(img: np.ndarray, d: Det) -> Det:
    sgn = 1.0 if d.score >= 0 else -1.0
    p = [0.0, 0.0, math.log2(d.w)]             # (perp offset, along offset, log2 w)

    def f(q):
        w = 2 ** q[2]
        x, y = (d.x + q[0], d.y + q[1]) if d.axis == "x" else (d.x + q[1], d.y + q[0])
        return sgn * sample_ncc(img, x, y, w, d.axis)

    best = f(p)
    steps = [0.25 * d.w, 0.5 * d.w, 1 / 24]
    for _ in range(5):
        for _ in range(8):
            moved = False
            for i in range(3):
                for s in (1, -1):
                    q = list(p)
                    q[i] += s * steps[i]
                    val = f(q)
                    if val > best:
                        best, p, moved = val, q, True
            if not moved:
                break
        steps = [s / 2 for s in steps]
    x, y = (d.x + p[0], d.y + p[1]) if d.axis == "x" else (d.x + p[1], d.y + p[0])
    return Det(x, y, 2 ** p[2], d.axis, sgn * best)


# ---------------------------------------------------------------------------
# 4-6. Lattice, pairing, identification
# ---------------------------------------------------------------------------

def fit_lattice(dets: list[Det]) -> tuple[float, np.ndarray, np.ndarray]:
    """phi such that 6*log2(w) ≈ phi + j (integer j). Returns phi, j, residual."""
    m = 6 * np.log2([d.w for d in dets])
    wt = np.array([d.score for d in dets]) ** 2
    inl = np.ones(len(m), bool)
    phi = 0.0
    for _ in range(3):
        phi = float(np.angle(np.sum(wt[inl] * np.exp(2j * np.pi * m[inl]))) / (2 * np.pi))
        res = (m - phi + 0.5) % 1.0 - 0.5
        inl = np.abs(res) < 0.25
    j = np.round(m - phi).astype(int)
    return phi, j, res


@dataclass
class Element:
    r: int                    # relative index (increases with frequency)
    h: Det | None             # horizontal-line set (axis 'y')
    v: Det | None             # vertical-line set (axis 'x')
    detected: bool = True
    k: int | None = None
    meas: dict = field(default_factory=dict)

    @property
    def center(self) -> np.ndarray:
        pts = [np.array([s.x, s.y]) for s in (self.h, self.v) if s is not None]
        return np.mean(pts, axis=0)


def pair_sets(dets: list[Det], j: np.ndarray, phi: float, ok: np.ndarray) -> list[Element]:
    by_j: dict[int, dict[str, list[Det]]] = {}
    for d, jj, good in zip(dets, j, ok):
        if good:
            by_j.setdefault(int(jj), {"x": [], "y": []})[d.axis].append(d)
    elements: list[Element] = []
    for jj, sets in by_j.items():
        w = 2 ** ((phi + jj) / 6)
        cand = []
        for hv in sets["y"]:
            for vv in sets["x"]:
                dist = math.hypot(hv.x - vv.x, hv.y - vv.y) / w
                if HV_DIST[0] <= dist <= HV_DIST[1]:
                    cand.append((min(abs(hv.score), abs(vv.score)), -abs(dist - 7.0), hv, vv))
        used = set()
        for sc, _, hv, vv in sorted(cand, key=lambda c: (c[0], c[1]), reverse=True):
            if id(hv) in used or id(vv) in used:
                continue
            used |= {id(hv), id(vv)}
            elements.append(Element(r=-jj, h=hv, v=vv))
    # one element per lattice index: keep the strongest
    best: dict[int, Element] = {}
    for e in elements:
        s = min(abs(e.h.score), abs(e.v.score))
        if e.r not in best or s > min(abs(best[e.r].h.score), abs(best[e.r].v.score)):
            best[e.r] = e
    return sorted(best.values(), key=lambda e: e.r)


def _break_expected(k_next: int) -> bool:
    """Is element k_next NOT the column neighbour of element k_next-1 on the slide?"""
    return k_next % 6 == 0 or k_next % 12 == 1


def identify_mod12(elements: list[Element], phi: float) -> tuple[int | None, list[int], int]:
    """Return best h (K0 ≡ h mod 12), the per-h scores, and the number of informative pairs."""
    by_r = {e.r: e for e in elements}
    obs = []
    for r, e in by_r.items():
        if r + 1 in by_r:
            w = 2 ** ((phi - r) / 6)
            dist = float(np.linalg.norm(by_r[r + 1].center - e.center)) / w
            obs.append((r + 1, dist > ADJ_DIST))
    scores = []
    for h in range(12):
        scores.append(sum(1 if _break_expected(rn + h) == brk else -1 for rn, brk in obs))
    if not obs:
        return None, scores, 0
    best = int(np.argmax(scores))
    if sorted(scores)[-1] == sorted(scores)[-2]:
        return None, scores, len(obs)
    return best, scores, len(obs)


def pixel_size_for(K0: int, phi: float) -> float:
    """µm/px implied by assigning relative index r -> k = K0 + r."""
    return 500.0 * 2.0 ** (-(K0 + phi) / 6.0)


# ---------------------------------------------------------------------------
# 7. Locating undetected elements
# ---------------------------------------------------------------------------
# Two exact properties of the slide are used:
#   * within a column, centres follow a geometric series: c(e) = A + B q^e, q = 2^(-1/6)
#     and the H->V offset scales as q^e;
#   * each group pair is a 1/4-scale copy of the pair two groups coarser, in the same
#     orientation: c(k+12) = c(k)/4 + t.

Q = 2.0 ** (-1 / 6)


def _column_of(k: int) -> tuple[int, str]:
    g, e = k_to_ge(k)
    return (g, "corner") if (g % 2 == 0 and e == 1) else (g, "col")


def predict_missing(elements: list[Element], k_lo: int, k_hi: int,
                    img_shape: tuple[int, int]) -> list[Element]:
    known, detected = predict_positions(elements, k_lo, k_hi)
    new = []
    H, W = img_shape
    for k, (c, hv) in sorted(known.items()):
        if k in detected or not (k_lo <= k <= k_hi):
            continue
        if not (0 <= c[0] < W and 0 <= c[1] < H):
            continue
        h = Det(c[0] - hv[0] / 2, c[1] - hv[1] / 2, 0.0, "y", 0.0)
        v = Det(c[0] + hv[0] / 2, c[1] + hv[1] / 2, 0.0, "x", 0.0)
        new.append(Element(r=k, h=h, v=v, detected=False, k=k))
    return new


def verify_small(elements: list[Element], px: float, k_lo: int, w_reliable: float = 2.8,
                 log=print) -> list[Element]:
    """
    Line widths of tiny bar sets cannot be measured to better than one lattice step
    (2^(1/6) = 12 %), so their k may be off by one. Predict every element's position
    from the reliable (large) elements and re-label / drop small detections accordingly.
    """
    wpx = lambda k: line_width_um_k(k) / px
    reliable = [e for e in elements if wpx(e.k) >= w_reliable]
    small = [e for e in elements if wpx(e.k) < w_reliable]
    if len(reliable) < 4 or not small:
        return elements
    pred, _ = predict_positions(reliable, k_lo, K_MAX)
    taken = {e.k for e in reliable}
    best_for: dict[int, tuple[float, Element]] = {}
    n_moved = n_drop = 0
    for e in small:
        opts = [(float(np.linalg.norm(pred[kk][0] - e.center)) / wpx(kk), kk)
                for kk in (e.k - 1, e.k, e.k + 1) if kk in pred and kk not in taken]
        if not opts or min(opts)[0] > 3.0:
            n_drop += 1
            continue
        d, kk = min(opts)
        n_moved += kk != e.k
        e.k, e.r = kk, e.r + (kk - e.k)
        if kk not in best_for or d < best_for[kk][0]:
            best_for[kk] = (d, e)
    if n_moved or n_drop:
        log(f"    small elements checked against layout: {n_moved} re-labelled, {n_drop} dropped")
    return sorted(reliable + [e for _, e in best_for.values()], key=lambda e: e.k)


def predict_positions(elements: list[Element], k_lo: int, k_hi: int):
    """Centre and H->V offset for every k in [k_lo, k_hi] that the slide geometry allows."""
    known: dict[int, tuple[np.ndarray, np.ndarray]] = {
        e.k: (e.center, np.array([e.v.x - e.h.x, e.v.y - e.h.y])) for e in elements}
    detected = set(known)

    def column_fit(k: int, mode: str):
        g, kind = _column_of(k)
        if kind == "corner":
            return None
        mem = [kk for kk in known if _column_of(kk) == (g, "col")]
        if len(mem) < 2:
            return None
        es = np.array([k_to_ge(kk)[1] for kk in mem], float)
        e = k_to_ge(k)[1]
        if mode == "interp" and not (es.min() < e < es.max()):
            return None
        if mode == "near" and (len(mem) < 3 or e < es.min() - 2 or e > es.max() + 2):
            return None
        A = np.stack([np.ones_like(es), Q ** es], 1)
        C = np.array([known[kk][0] for kk in mem])
        coef = np.linalg.lstsq(A, C, rcond=None)[0]
        HV = np.array([known[kk][1] for kk in mem])
        h0 = (HV * (Q ** es)[:, None]).sum(0) / (Q ** (2 * es)).sum()
        return coef[0] + coef[1] * Q ** e, h0 * Q ** e

    corr = [(k, k + 12) for k in detected if k + 12 in detected]
    t = (np.mean([known[b][0] - known[a][0] / 4 for a, b in corr], axis=0) if corr else None)

    def similarity(k: int):
        if t is None:
            return None
        if k - 12 in known:
            c, hv = known[k - 12]
            return c / 4 + t, hv / 4
        if k + 12 in known:
            c, hv = known[k + 12]
            return 4 * (c - t), hv * 4
        return None

    def fill(fn):
        changed = True
        while changed:
            changed = False
            for k in range(k_lo, k_hi + 1):
                if k not in known:
                    p = fn(k)
                    if p is not None:
                        known[k] = p
                        changed = True

    fill(lambda k: column_fit(k, "interp"))   # interpolate inside columns
    fill(lambda k: column_fit(k, "near"))     # short extrapolation of well-sampled columns
    fill(similarity)                          # copy from the pair 2 groups away
    fill(lambda k: column_fit(k, "any"))      # longer extrapolation along columns
    fill(similarity)

    return known, detected


def snap_predicted(img: np.ndarray, s: Det, w: float, polarity: float) -> Det:
    """Search ±1 w around a predicted bar set for the best matched-filter response."""
    best, bx, by = -np.inf, s.x, s.y
    offs = np.arange(-1.0, 1.0 + 1e-9, 0.25) * w
    for dy in offs:
        for dx in offs:
            sc = polarity * sample_ncc(img, s.x + dx, s.y + dy, w, s.axis)
            if sc > best:
                best, bx, by = sc, s.x + dx, s.y + dy
    if best >= 0.35:
        return Det(bx, by, w, s.axis, polarity * best)
    return Det(s.x, s.y, w, s.axis, polarity * max(best, 0.0))


# ---------------------------------------------------------------------------
# 8. Contrast measurement
# ---------------------------------------------------------------------------

def measure_set(coeffs: np.ndarray, s: Det, w: float, polarity: float, refine_pos: bool,
                frame: Frame, raw: np.ndarray | None = None, black: float = 0.0) -> dict:
    """
    `coeffs` are cubic-spline coefficients of the ORIGINAL (not de-rotated) image, so the
    profile is interpolated only once and with a near-ideal kernel; the working-frame
    sampling grid is mapped into original coordinates through `frame`.
    """
    du = min(0.25, w / 8)
    u = np.arange(-4.0 * w, 4.0 * w + 1e-9, du)
    v = np.linspace(-1.5 * w, 1.5 * w, max(5, int(3 * w / 0.5)))   # central 60 % of bar length
    X, Y = _grid(s.x, s.y, w, s.axis, u, v)
    OX, OY = frame.to_original(X, Y)
    prof = ndimage.map_coordinates(coeffs, [OY.ravel(), OX.ravel()], order=3, mode="nearest",
                                   prefilter=False).reshape(X.shape).mean(0)

    shift = 0.0
    if refine_pos:
        t = _bar_coverage(u, w, du / 2)
        best = -np.inf
        for sh in np.arange(-0.5 * w, 0.5 * w + 1e-9, du):
            tt = np.interp(u, u + sh, t, left=0, right=0)
            sc = polarity * float(((tt - tt.mean()) * prof).sum())
            if sc > best:
                best, shift = sc, sh

    def level(centres):
        # value exactly at each bar / gap centre (noise is already averaged along the bars)
        return float(np.mean(np.interp(shift + np.asarray(centres), u, prof)))

    i_bar = level([-2 * w, 0.0, 2 * w])
    i_gap = level([-w, w])
    hi, lo = (i_bar, i_gap) if polarity > 0 else (i_gap, i_bar)
    michelson = (hi - lo) / (hi + lo) if (hi + lo) > 0 else float("nan")

    # lock-in: least-squares a + b cos + c sin at the element's frequency, over the 5w bar region
    sel = np.abs(u - shift) <= 2.5 * w
    ph = np.pi * (u[sel] - shift) / w
    A = np.stack([np.ones(sel.sum()), np.cos(ph), np.sin(ph)], 1)
    a0, b, c = np.linalg.lstsq(A, prof[sel], rcond=None)[0]
    mod = math.hypot(b, c) / a0 if a0 > 0 else float("nan")
    mod = mod if (b * polarity) >= 0 else -mod      # phase reversal -> negative

    perp = (s.x if s.axis == "x" else s.y) + shift
    cx, cy = (perp, s.y) if s.axis == "x" else (s.x, perp)
    out = {"michelson": float(michelson), "lockin_modulation": float(mod),
           "i_bar": i_bar, "i_gap": i_gap, "cx": float(cx), "cy": float(cy)}

    if raw is not None:
        # Independent check: ONE scan line through the element centre, perpendicular to the
        # bars, reading the nearest raw pixel values (no interpolation, no averaging).
        t = np.arange(-4.0 * w, 4.0 * w + 1e-9, 1.0)
        tx, ty = (cx + t, np.full_like(t, cy)) if s.axis == "x" else (np.full_like(t, cx), cy + t)
        ox, oy = frame.to_original(tx, ty)
        ix = np.clip(np.rint(ox).astype(int), 0, raw.shape[1] - 1)
        iy = np.clip(np.rint(oy).astype(int), 0, raw.shape[0] - 1)
        vals = raw[iy, ix] - black
        sb = float(np.mean(np.interp([-2 * w, 0.0, 2 * w], t, vals)))
        sg = float(np.mean(np.interp([-w, w], t, vals)))
        shi, slo = (sb, sg) if polarity > 0 else (sg, sb)
        out["scan"] = {
            "t_px": t.round(3).tolist(),
            "values": (vals + black).round(4).tolist(),
            "pixels_xy": np.stack([ix, iy], 1).tolist(),
            "avg_t_px": (u - shift).round(3).tolist(),
            "avg_values": (prof + black).round(4).tolist(),
            "i_bar": sb + black, "i_gap": sg + black,
            "michelson": float((shi - slo) / (shi + slo)) if (shi + slo) > 0 else float("nan"),
        }
    return out


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze(img_raw: np.ndarray, contrast: float = 0.2, pixel_size: float | None = None,
            group_hint: int | None = None, black_level: str | float = "none",
            roi: tuple[int, int, int, int] | None = None, min_ncc: float = 0.55,
            w_min: float = 1.25, verbose: bool = True) -> dict:
    log = print if verbose else (lambda *a, **k: None)
    notes: list[str] = []

    img0 = img_raw.astype(np.float64)
    off = (0, 0)
    if roi:
        x0, y0, x1, y1 = roi
        img0 = img0[y0:y1, x0:x1]
        off = (x0, y0)

    if black_level == "auto":
        black = float(np.percentile(ndimage.median_filter(img0, 5), 0.5))
    elif black_level == "none":
        black = 0.0
    else:
        black = float(black_level)

    img, frame = derotate(img0)
    log(f"[1] orientation: de-rotated by {frame.angle:+.2f}°")

    w_max = max(w_min * 2, min(img.shape) / 22)
    raw = detect(img, w_min, w_max, min_ncc)
    dets = nms(raw, 1.5)
    log(f"[2] matched filter: {len(raw)} raw peaks -> {len(dets)} after suppression")
    dets = nms([refine(img, d) for d in dets], 1.2)
    dets = [d for d in dets if abs(d.score) >= min_ncc]
    log(f"[3] refined: {len(dets)} bar-set candidates")
    if len(dets) < 4:
        raise RuntimeError("Too few bar sets detected - is this a USAF target image?")

    phi, j, res = fit_lattice(dets)
    ok = np.abs(res) < 0.3
    log(f"[4] scale lattice phase {phi:+.3f} (1/6-octave units); {ok.sum()}/{len(dets)} on lattice")

    polarity = 1.0 if sum(d.score * abs(d.score) for d, good in zip(dets, ok) if good) >= 0 else -1.0
    ok &= np.array([d.score * polarity > 0 for d in dets])      # drop opposite-polarity hits
    elements = pair_sets(dets, j, phi, ok)
    if len(elements) < 2:
        raise RuntimeError("Could not pair horizontal/vertical bar sets into elements.")
    log(f"[5] paired into {len(elements)} elements; polarity: {'bright' if polarity > 0 else 'dark'} bars")

    # ---- identification -------------------------------------------------
    h, scores, n_obs = identify_mod12(elements, phi)
    r_vals = [e.r for e in elements]
    method = ""
    if h is not None:
        cands = [K0 for K0 in range(K_MIN - max(r_vals), K_MAX - min(r_vals) + 1) if (K0 - h) % 12 == 0]
        if not cands:
            cands = [K0 for K0 in range(-60, 80) if (K0 - h) % 12 == 0]
        if pixel_size:
            K0 = min(cands, key=lambda K: abs(math.log(pixel_size_for(K, phi) / pixel_size)))
            method = "layout (mod 12) + pixel size"
        elif group_hint is not None:
            # hint = coarsest group visible; candidates differ by 2 groups, pick the closest
            K0 = min(cands, key=lambda K: abs((K + min(r_vals)) // 6 - group_hint))
            method = "layout (mod 12) + coarsest-group hint"
        else:
            valid = [K for K in cands if min(r_vals) + K >= K_MIN and max(r_vals) + K <= K_MAX]
            K0 = max(valid) if valid else max(cands)
            method = "layout (mod 12) + assumption that the finest visible groups are the slide's finest"
            notes.append("Group number assumed (finest visible pair taken as the slide's finest). "
                         "Pass --pixel-size (approx. is fine) or --coarsest-group to confirm; "
                         "the alternative is 2 groups coarser.")
    elif pixel_size:
        K0 = int(round(6 * math.log2(500.0 / pixel_size) - phi))
        method = "pixel size only (layout inconclusive)"
        notes.append("Layout inconclusive; identification relies on pixel size being within ~5 %.")
    else:
        raise RuntimeError("Could not identify groups from the layout; please pass --pixel-size.")
    log(f"[6] identification: {method}  (column-break votes {max(scores)} of {n_obs})")

    for e in elements:
        e.k = K0 + e.r
    dropped = [e for e in elements if not (K_MIN <= e.k <= K_MAX)]
    elements = [e for e in elements if K_MIN <= e.k <= K_MAX]
    if dropped:
        log(f"    dropped {len(dropped)} pair(s) outside the slide's group range")
    px_fit = pixel_size_for(K0, phi)
    if pixel_size and abs(math.log(px_fit / pixel_size)) > math.log(1.06):
        notes.append(f"Fitted pixel size {px_fit:.4g} µm/px differs from given {pixel_size:.4g} µm/px "
                     f"by {100 * (px_fit / pixel_size - 1):+.1f} %.")

    g_lo = k_to_ge(min(e.k for e in elements))[0]
    k_lo = 6 * (g_lo - g_lo % 2)                       # start of the coarsest detected pair
    elements = verify_small(elements, px_fit, k_lo, log=log)
    extra = predict_missing(elements, k_lo, K_MAX, img.shape)
    for e in extra:
        w_px = line_width_um_k(e.k) / px_fit
        e.h = snap_predicted(img, e.h, w_px, polarity)
        e.v = snap_predicted(img, e.v, w_px, polarity)
    log(f"[7] located {len(extra)} undetected elements (column geometry + 1/4 self-similarity)")
    all_el = sorted(elements + extra, key=lambda e: e.k)

    # ---- contrast ----------------------------------------------------------
    coeffs = ndimage.spline_filter(img0 - black, order=3)
    for e in all_el:
        w_px = line_width_um_k(e.k) / px_fit
        e.meas["H"] = measure_set(coeffs, e.h, w_px, polarity, True, frame, img0, black)
        e.meas["V"] = measure_set(coeffs, e.v, w_px, polarity, True, frame, img0, black)

    rows = []
    for e in all_el:
        g, el = k_to_ge(e.k)
        w_px = line_width_um_k(e.k) / px_fit
        cH, cV = e.meas["H"]["michelson"], e.meas["V"]["michelson"]
        cmin = min(cH, cV)
        undersampled = 2 * w_px < 2.0
        polys = {}
        for key, s in (("H", e.meas["H"]), ("V", e.meas["V"])):
            axis = "y" if key == "H" else "x"
            hw = 2.5 * w_px
            corners = np.array([[-hw, -hw], [hw, -hw], [hw, hw], [-hw, hw]]) + [s["cx"], s["cy"]]
            ox, oy = frame.to_original(corners[:, 0], corners[:, 1])
            polys[key] = [[round(float(a) + off[0], 2), round(float(b) + off[1], 2)] for a, b in zip(ox, oy)]
        rows.append({
            "group": g, "element": el, "k": e.k,
            "lp_per_mm": round(lp_per_mm_k(e.k), 4),
            "line_width_um": round(line_width_um_k(e.k), 4),
            "line_width_px": round(w_px, 3),
            "detected": e.detected,
            "contrast_H": round(cH, 4), "contrast_V": round(cV, 4), "contrast_min": round(cmin, 4),
            "lockin_H": round(e.meas["H"]["lockin_modulation"], 4),
            "lockin_V": round(e.meas["V"]["lockin_modulation"], 4),
            "passes": bool(cmin >= contrast and not undersampled),
            "undersampled": bool(undersampled),
            "ncc_H": round(e.h.score, 3),
            "ncc_V": round(e.v.score, 3),
            "polygon_H_px": polys["H"], "polygon_V_px": polys["V"],
            "scanline_contrast_H": round(e.meas["H"]["scan"]["michelson"], 4),
            "scanline_contrast_V": round(e.meas["V"]["scan"]["michelson"], 4),
            "scan_H": {**e.meas["H"]["scan"],
                       "pixels_xy": [[a + off[0], b + off[1]] for a, b in e.meas["H"]["scan"]["pixels_xy"]]},
            "scan_V": {**e.meas["V"]["scan"],
                       "pixels_xy": [[a + off[0], b + off[1]] for a, b in e.meas["V"]["scan"]["pixels_xy"]]},
        })

    passing = [r for r in rows if r["passes"]]
    limit = max(passing, key=lambda r: r["k"]) if passing else None
    if limit:
        coarser_fail = [f"G{r['group']}E{r['element']}" for r in rows
                        if r["k"] < limit["k"] and not r["passes"] and not r["undersampled"]]
        if coarser_fail:
            notes.append("Coarser elements below threshold (defocus / field effects or spurious "
                         "resolution?): " + ", ".join(coarser_fail))
        nxt = [r for r in rows if r["k"] == limit["k"] + 1]
        if not nxt:
            notes.append("The next finer element could not be measured (outside field / not located).")
        elif nxt[0]["undersampled"]:
            notes.append("The next finer element is below the camera's Nyquist limit: result is pixel-limited.")

    return {
        "contrast_threshold": contrast,
        "result": None if not limit else {
            "group": limit["group"], "element": limit["element"],
            "lp_per_mm": limit["lp_per_mm"], "line_width_um": limit["line_width_um"],
            "contrast_H": limit["contrast_H"], "contrast_V": limit["contrast_V"],
        },
        "pixel_size_um_fitted": round(px_fit, 5),
        "pixel_size_um_given": pixel_size,
        "identification": method,
        "rotation_deg": round(frame.angle, 3),
        "polarity": "bright-bars" if polarity > 0 else "dark-bars",
        "black_level": black,
        "roi": roi,
        "notes": notes,
        "elements": rows,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def save_overlay(img: np.ndarray, res: dict, path: Path) -> None:
    lo, hi = np.percentile(img, [0.5, 99.8])
    base = (np.clip((img - lo) / max(hi - lo, 1e-9), 0, 1) ** 0.7 * 255).astype(np.uint8)
    scale = max(1.0, 1600 / max(img.shape))
    im = Image.fromarray(base).convert("RGB")
    if scale > 1:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    dr = ImageDraw.Draw(im)
    lim = res["result"]
    for r in res["elements"]:
        col = (40, 220, 90) if r["passes"] else (235, 60, 60)
        if not r["detected"]:
            col = (255, 170, 40) if r["passes"] else (170, 70, 200)
        if lim and r["group"] == lim["group"] and r["element"] == lim["element"]:
            col = (60, 200, 255)
        for key in ("polygon_H_px", "polygon_V_px"):
            pts = [(x * scale, y * scale) for x, y in r[key]]
            dr.polygon(pts, outline=col, width=2 if r["line_width_px"] * scale > 4 else 1)
        for key in ("scan_H", "scan_V"):
            px_ = r[key]["pixels_xy"]
            dr.line([(px_[0][0] * scale, px_[0][1] * scale), (px_[-1][0] * scale, px_[-1][1] * scale)],
                    fill=(255, 255, 0), width=1)
        xs = [p[0] for p in r["polygon_H_px"] + r["polygon_V_px"]]
        ys = [p[1] for p in r["polygon_H_px"] + r["polygon_V_px"]]
        fs = int(np.clip(r["line_width_px"] * scale * 2.2, 9, 28))
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", fs)
        except OSError:
            font = ImageFont.load_default()
        dr.text((max(xs) * scale + 3, min(ys) * scale),
                f"{r['group']}.{r['element']} {100 * r['contrast_min']:.0f}%", fill=col, font=font)
    im.save(path)


def save_ctf_plot(res: dict, path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = res["elements"]
    f = np.array([r["lp_per_mm"] for r in rows])
    det = np.array([r["detected"] for r in rows])
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, mk, colr in (("contrast_H", "o", "tab:blue"), ("contrast_V", "s", "tab:orange")):
        c = np.array([r[key] for r in rows])
        ax.plot(f, c, color=colr, lw=0.8, alpha=0.6)
        ax.scatter(f[det], c[det], marker=mk, color=colr, label=f"{key[-1]} lines (detected)", zorder=3)
        ax.scatter(f[~det], c[~det], marker=mk, facecolors="none", edgecolors=colr,
                   label=f"{key[-1]} lines (extrapolated)", zorder=3)
    ax.axhline(res["contrast_threshold"], color="k", ls="--", lw=1,
               label=f"threshold {100 * res['contrast_threshold']:.0f}%")
    if res["result"]:
        ax.axvline(res["result"]["lp_per_mm"], color="tab:green", lw=1.2,
                   label=f"limit G{res['result']['group']}E{res['result']['element']} "
                         f"({res['result']['lp_per_mm']:.1f} lp/mm)")
    nyq = 500.0 / res["pixel_size_um_fitted"]
    ax.axvline(nyq, color="tab:red", ls=":", lw=1, label=f"camera Nyquist ({nyq:.0f} lp/mm)")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("spatial frequency [lp/mm]")
    ax.set_ylabel("Michelson contrast")
    ax.set_ylim(min(-0.1, ax.get_ylim()[0]), 1.05)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8, loc="lower left")
    ax.set_title(title)
    sec = ax.secondary_xaxis("top", functions=(lambda x: np.log2(np.maximum(x, 1e-9)),
                                               lambda g: 2.0 ** g))
    sec.set_xlabel("group")
    g_lo, g_hi = int(np.floor(np.log2(f.min()))), int(np.ceil(np.log2(max(f.max(), nyq))))
    sec.set_xticks(list(range(g_lo, g_hi + 1)))
    sec.set_xticklabels([str(g) for g in range(g_lo, g_hi + 1)])
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def save_scanline_plot(res: dict, path: Path, title: str) -> None:
    """One panel per bar set: raw centre scan line (pixel values) vs. the reader's averaged
    profile, with the ideal bar positions shaded and the bar/gap levels marked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = res["elements"]
    px = res["pixel_size_um_fitted"]
    bright = res["polarity"] == "bright-bars"
    ncols = 4                                    # H, V of two elements per row
    nrows = math.ceil(len(rows) / 2)
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 2.3 * nrows), squeeze=False)
    for i, ax in enumerate(axes.ravel()):
        r_i, side = divmod(i, 2)
        if r_i >= len(rows):
            ax.axis("off")
            continue
        r = rows[r_i]
        key = "H" if side == 0 else "V"
        sc = r[f"scan_{key}"]
        w = r["line_width_px"]
        for c in (-2, 0, 2):                     # ideal bar positions
            ax.axvspan((c - 0.5) * w * px, (c + 0.5) * w * px,
                       color="0.85" if bright else "0.6", alpha=0.6, lw=0)
        ax.plot(np.array(sc["avg_t_px"]) * px, sc["avg_values"], color="tab:blue", lw=1.2,
                label="reader profile (avg. along bars)")
        ax.plot(np.array(sc["t_px"]) * px, sc["values"], color="tab:red", lw=0.8, marker=".", ms=4,
                drawstyle="steps-mid", label="centre scan line (raw pixels)")
        ax.axhline(sc["i_bar"], color="tab:green", ls="--", lw=0.8)
        ax.axhline(sc["i_gap"], color="tab:purple", ls="--", lw=0.8)
        ok = r["passes"]
        ax.set_title(f"G{r['group']}E{r['element']} {key}-lines  {r['lp_per_mm']:.1f} lp/mm  "
                     f"reader {100 * r[f'contrast_{key}']:.1f}%  scan {100 * sc['michelson']:.1f}%"
                     + ("" if r["detected"] else "  (located)"),
                     fontsize=8, color="tab:green" if ok else "tab:red")
        ax.tick_params(labelsize=7)
        if r_i == len(rows) - 1 or i >= (nrows - 1) * ncols:
            ax.set_xlabel("position across bars [µm]", fontsize=7)
    axes[0, 0].legend(fontsize=7, loc="lower right")
    fig.suptitle(f"{title}\nshaded = ideal bar positions; dashed = bar (green) / gap (purple) "
                 f"levels from the scan line; title colour = element pass/fail at "
                 f"{100 * res['contrast_threshold']:.0f}%", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--contrast", type=float, default=0.20, help="required contrast, 0-1 (default 0.20)")
    ap.add_argument("--pixel-size", type=float, default=None, help="approx. object-space pixel size, µm")
    ap.add_argument("--magnification", type=float, default=None)
    ap.add_argument("--camera-pixel", type=float, default=None, help="camera pixel pitch, µm")
    ap.add_argument("--coarsest-group", type=int, default=None,
                    help="number of the coarsest (largest-bar) group visible in the image")
    ap.add_argument("--black-level", default="none",
                    help="'none' (default), 'auto' (0.5th percentile), or a number to subtract")
    ap.add_argument("--roi", type=int, nargs=4, default=None, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--min-ncc", type=float, default=0.55, help="matched-filter detection threshold")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    px = args.pixel_size
    if px is None and args.magnification and args.camera_pixel:
        px = args.camera_pixel / args.magnification
    bl = args.black_level if args.black_level in ("none", "auto") else float(args.black_level)

    img = load_gray(args.image)
    res = analyze(img, args.contrast, px, args.coarsest_group, bl, tuple(args.roi) if args.roi else None,
                  args.min_ncc)
    res["image"] = str(args.image)

    out = args.out_dir or args.image.parent / "usaf_results"
    out.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    (out / f"{stem}_usaf.json").write_text(json.dumps(res, indent=2))
    cols = ["group", "element", "lp_per_mm", "line_width_um", "line_width_px", "detected",
            "contrast_H", "contrast_V", "contrast_min", "lockin_H", "lockin_V",
            "scanline_contrast_H", "scanline_contrast_V", "passes", "undersampled"]
    with open(out / f"{stem}_usaf.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(res["elements"])
    save_overlay(img, res, out / f"{stem}_overlay.png")
    save_ctf_plot(res, out / f"{stem}_ctf.png", f"{args.image.name} - CTF")
    save_scanline_plot(res, out / f"{stem}_scanlines.png", f"{args.image.name} - scan lines")
    with open(out / f"{stem}_scanlines.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["group", "element", "lines", "kind", "position_px", "position_um", "value",
                     "pixel_x", "pixel_y"])
        for r in res["elements"]:
            for key in ("H", "V"):
                sc = r[f"scan_{key}"]
                for t, v, (x, y) in zip(sc["t_px"], sc["values"], sc["pixels_xy"]):
                    wr.writerow([r["group"], r["element"], key, "scanline", t,
                                 round(t * res["pixel_size_um_fitted"], 4), v, x, y])
                for t, v in zip(sc["avg_t_px"], sc["avg_values"]):
                    wr.writerow([r["group"], r["element"], key, "reader_profile", t,
                                 round(t * res["pixel_size_um_fitted"], 4), v, "", ""])

    print()
    print(f"{'G':>3} {'E':>2} {'lp/mm':>8} {'w[µm]':>7} {'w[px]':>6}  {'C_H':>6} {'C_V':>6}  "
          f"{'scanH':>6} {'scanV':>6}  status")
    for r in res["elements"]:
        st = "PASS" if r["passes"] else ("undersampled" if r["undersampled"] else "fail")
        st += "" if r["detected"] else " (extrapolated)"
        print(f"{r['group']:>3} {r['element']:>2} {r['lp_per_mm']:>8.2f} {r['line_width_um']:>7.3f} "
              f"{r['line_width_px']:>6.2f}  {100 * r['contrast_H']:>5.1f}% {100 * r['contrast_V']:>5.1f}%  "
              f"{100 * r['scanline_contrast_H']:>5.1f}% {100 * r['scanline_contrast_V']:>5.1f}%  {st}")
    print()
    print(f"Pixel size (fitted): {res['pixel_size_um_fitted']:.4g} µm/px   identification: {res['identification']}")
    if res["result"]:
        r = res["result"]
        print(f"RESULT @ {100 * args.contrast:.0f}% contrast: Group {r['group']} Element {r['element']}  "
              f"= {r['lp_per_mm']:.2f} lp/mm, line width {r['line_width_um']:.3f} µm "
              f"(C_H {100 * r['contrast_H']:.1f}%, C_V {100 * r['contrast_V']:.1f}%)")
    else:
        print(f"RESULT: no element reaches {100 * args.contrast:.0f}% contrast.")
    for n in res["notes"]:
        print("note:", n)
    print(f"Saved results to {out}/")


if __name__ == "__main__":
    main()

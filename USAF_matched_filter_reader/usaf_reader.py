#!/usr/bin/env python3
"""
Read a microscope image of a 1951 USAF target: find every bar element, identify
its group/element, measure its contrast, and report the finest element that
meets a requested contrast (default 20 %).

Why not a global FFT?
    A global spectrum mixes all 36 elements (plus digits, square, illumination)
    and loses *where* each frequency came from, so it cannot say which element
    still has 20 % contrast. Instead we use local matched-filter analysis at each element's own bar width:

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
                      (good to within ×/÷2) or a group hint. Without either, the
                      finest detected pair is taken as the slide's finest unless a
                      finer pair, even blurred flat, puts light where the layout
                      predicts it; each one found moves the labels 2 groups coarser.
                      Group pairs missing between detected ones are searched again
                      at their line widths with a lower threshold, keeping only hits
                      that fit the 1/4-scale copy of the coarser pair.
    7. Prediction   - elements too blurred (or too small) to detect are located from
                      the slide geometry: each column is a geometric series, and each
                      group pair is a 1/4-scale copy of the pair two groups coarser.
                      Tiny detections (< ~3 px line width, where width alone can't
                      tell neighbouring elements apart) are re-checked against these
                      predicted positions. So the contrast fall-off past the
                      resolution limit is measured, not assumed.
                      Each detected element is also checked against the layout
                      predicted from the others: a bar set far off while its partner
                      agrees was paired with the wrong feature and is moved. Bar sets
                      not fully inside the image are flagged as cut off and skipped.
    8. Contrast     - per bar set, a profile across the bars (averaged over the
                      central 60 % of the bar length) gives
                        Michelson contrast  C = (I_bar - I_gap)/(I_bar + I_gap)
                      using the 3 bar centres and 2 inner gaps (signed: negative =
                      contrast reversal / spurious resolution), and a lock-in
                      (least-squares sine fit at the known frequency) modulation.
                      An element passes when both orientations reach the threshold.
                      The limit is the last passing element before the first failure,
                      going from coarse to fine. One isolated failure (the next element
                      passes again) is stepped over and reported (--skip-isolated 0 to
                      stop there; --limit-rule finest-pass: finest element that passes).
                      Contrast is reported on the raw image and after a background
                      correction: a dark frame (--dark-frame, recommended), a value, or
                      an automatic estimate. The raw image is the primary result unless a
                      dark frame or value is given, because stray light is part of the
                      system's performance and the automatic estimate can't separate it.
    9. CTF fit      - (ctf_fit.py) a model (3 bars x Gaussian PSF x camera pixel, plus
                      uniform stray light) is fitted to all measured contrasts, per
                      direction. It gives the blur (sigma), the stray-light level, and the
                      frequency where the fitted curve crosses the threshold, with an
                      uncertainty. It only reads the measured contrasts; it doesn't change
                      them or the reported element limit, and is reported next to it.

Usage
    python usaf_reader.py image.png                         # 20 % threshold
    python usaf_reader.py image.png --contrast 0.3 --pixel-size 1.1
    python usaf_reader.py image.png --magnification 10 --camera-pixel 3.45
    python usaf_reader.py image.png --coarsest-group 4      # biggest group you can see
    python usaf_reader.py image.png --workers 1             # one process (slower, same result)

Outputs (in --out-dir, default: <image folder>/usaf_results/):
    <stem>_usaf.json     everything, incl. per-element contrast and bounding boxes
    <stem>_usaf.csv      per-element table (measured; fit_H/fit_V are the CTF fit's values)
    <stem>_overlay.png   detections drawn on the image (green pass, red fail), with a text box
                         giving the element limit and the CTF fit
    <stem>_ctf.png       contrast vs spatial frequency (CTF) with the threshold and the fitted curves
    <stem>_scanlines.png raw centre scan line (pixel values) vs. the reader's profile, per bar set
    <stem>_scanlines.csv the scan-line and profile values behind that plot
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import ctf_fit  # noqa: E402
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

def _edge_angle(img: np.ndarray, border: int = 16) -> float:
    """Dominant edge orientation folded to (-45°, 45°], degrees.
    Gradients within `border` px of the image edge are ignored: padding strips, frame
    borders and the edges left by de-rotation are long straight edges that would
    otherwise outweigh the target."""
    sm = ndimage.gaussian_filter(img, 1.5)
    gx, gy = ndimage.sobel(sm, 1), ndimage.sobel(sm, 0)
    m2 = gx * gx + gy * gy
    b = max(0, min(border, min(img.shape) // 8))
    if b:
        m2[:b], m2[-b:], m2[:, :b], m2[:, -b:] = 0, 0, 0, 0
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


def _level(w: float) -> int:
    """Block size of the image pyramid used for line width w (template stays 2-4 px wide)."""
    return 2 ** (0 if w < 4 else int(math.floor(math.log2(w / 2.0))))


def _detect_one(img: np.ndarray, pyramid: dict, w: float, axis: str, thr: float, gvar: float):
    """Matched-filter peaks for one line width and orientation: (ys, xs, scores, block size)."""
    d = _level(w)
    if d not in pyramid:
        im = _block_mean(img, d)
        pyramid[d] = (im, im * im, 1e-4 * gvar)
    im, im2, eps = pyramid[d]
    ncc = _ncc_map(im, im2, w / d, axis, eps)
    ys, xs = _peaks(np.abs(ncc), thr)
    return ys, xs, ncc[ys, xs], d


def detect(img: np.ndarray, w_min: float, w_max: float, thr: float, steps_per_octave: int = 12,
           pool: "WorkerPool | None" = None, box: tuple[int, int, int, int] | None = None) -> list[Det]:
    """Matched-filter bank. img is the image searched; with a pool, img must be the pool's
    image cropped to box (y0, y1, x0, x1), or the whole pool image when box is None. Each
    (width, orientation) is independent, so the pool runs them in its worker processes with
    the same code; the candidates come back in the same order as serial."""
    n_oct = math.log2(w_max / w_min)
    ws = w_min * 2.0 ** (np.arange(int(n_oct * steps_per_octave) + 1) / steps_per_octave)
    gvar = float(np.var(img))
    jobs = [(float(w), axis) for w in ws for axis in ("x", "y")]
    if pool is not None and pool.parallel:
        results = pool.detect(jobs, thr, gvar, box)
    else:
        pyramid: dict = {}
        results = [_detect_one(img, pyramid, w, axis, thr, gvar) for w, axis in jobs]
    cands: list[Det] = []
    for (w, axis), (ys, xs, sc, d) in zip(jobs, results):
        for yy, xx, v in zip(ys, xs, sc):
            cands.append(Det((xx + 0.5) * d - 0.5, (yy + 0.5) * d - 0.5, w, axis, float(v)))
    return cands


def _peaks(a: np.ndarray, thr: float) -> tuple[np.ndarray, np.ndarray]:
    """Pixels >= thr that are the maximum of their 3x3 neighbourhood, in row-major order.
    Same result as (a >= thr) & (a == maximum_filter(a, 3)), but only the pixels above the
    threshold are checked. _ncc_map zeroes the border, so their neighbours are all inside."""
    ys, xs = np.nonzero(a >= thr)
    if not len(ys):
        return ys, xs
    H, W = a.shape
    v = a[ys, xs]
    keep = np.ones(len(ys), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                keep &= v >= a[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)]
    return ys[keep], xs[keep]


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
        # accepted detections, filled in place (same values and comparisons as growing lists)
        ax_, ay_, aw_ = np.empty(len(ds)), np.empty(len(ds)), np.empty(len(ds))
        n = 0
        for i, d in enumerate(ds):
            if sup[i]:
                continue
            if n and np.any(np.hypot(ax_[:n] - d.x, ay_[:n] - d.y) < radius * np.maximum(aw_[:n], d.w)):
                sup[i] = True
                continue
            out.append(d)
            ax_[n], ay_[n], aw_[n] = d.x, d.y, d.w
            n += 1
            sup[tree.query_ball_point((d.x, d.y), radius * d.w)] = True
    return out


# ---------------------------------------------------------------------------
# 3. Sub-pixel refinement
# ---------------------------------------------------------------------------

def _grid(x: float, y: float, w: float, axis: str, u: np.ndarray, v: np.ndarray):
    U, V = np.meshgrid(u, v)
    return (x + U, y + V) if axis == "x" else (x + V, y + U)


@lru_cache(maxsize=4096)
def _template(w: float):
    """Sampling offsets and the zero-mean 2-D 3-bar template for line width w (depends on w only)."""
    du = min(0.5, w / 6)
    dv = min(1.0, max(0.5, w / 6))
    u = np.arange(-3.5 * w, 3.5 * w + 1e-9, du)
    v = np.arange(-3.5 * w, 3.5 * w + 1e-9, dv)
    U, V = np.meshgrid(u, v)
    tu = _bar_coverage(u, w, du / 2)
    tv = np.clip(np.minimum(2.5 * w, v + dv / 2) - np.maximum(-2.5 * w, v - dv / 2), 0, None) / dv
    T = tv[:, None] * tu[None, :]
    T = T - T.mean()
    return U, V, T, float((T * T).sum())


def sample_ncc(img: np.ndarray, x: float, y: float, w: float, axis: str) -> float:
    """NCC with the full 2-D 3-bar template (bars of length 5w inside a 7w x 7w window),
    so position is pinned both across and along the bars."""
    U, V, T, tt = _template(w)
    X, Y = (x + U, y + V) if axis == "x" else (x + V, y + U)
    P = ndimage.map_coordinates(img, [Y.ravel(), X.ravel()], order=1, mode="nearest").reshape(X.shape)
    P = P - P.mean()
    den = math.sqrt(tt * float((P * P).sum()))
    return float((P * T).sum() / den) if den > 0 else 0.0


def refine(img: np.ndarray, d: Det) -> Det:
    sgn = 1.0 if d.score >= 0 else -1.0
    p = [0.0, 0.0, math.log2(d.w)]             # (perp offset, along offset, log2 w)

    seen: dict[tuple[float, float, float], float] = {}

    def f(q):
        w = 2 ** q[2]
        x, y = (d.x + q[0], d.y + q[1]) if d.axis == "x" else (d.x + q[1], d.y + q[0])
        # the search often re-tests a point it already evaluated: reuse that exact value
        key = (x, y, w)
        if key not in seen:
            seen[key] = sgn * sample_ncc(img, x, y, w, d.axis)
        return seen[key]

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


_WORKER_IMG: np.ndarray | None = None
_WORKER_PYR: tuple = (None, {})            # (box, pyramid) cached per worker process


def _pool_init(img: np.ndarray) -> None:
    global _WORKER_IMG
    _WORKER_IMG = img


def _refine_worker(d: Det) -> Det:
    return refine(_WORKER_IMG, d)


def _detect_worker(job: tuple) -> tuple:
    global _WORKER_PYR
    w, axis, thr, gvar, box = job
    if _WORKER_PYR[0] != box:
        _WORKER_PYR = (box, {})
    img = _WORKER_IMG if box is None else _WORKER_IMG[box[0]:box[1], box[2]:box[3]]
    return _detect_one(img, _WORKER_PYR[1], w, axis, thr, gvar)


def default_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


class WorkerPool:
    """Worker processes for the matched-filter bank and the candidate refinement on one image.
    Every (width, orientation) map and every candidate is independent, so they run in separate
    processes (started on first use, reused until close()) with the same code as serial; the
    results are identical. With workers <= 1 everything runs serially in this process."""

    def __init__(self, img: np.ndarray, workers: int = 1):
        self.img, self.workers, self._ex = img, workers, None

    @property
    def parallel(self) -> bool:
        return self.workers > 1

    def _executor(self):
        if self._ex is None:
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor
            self._ex = ProcessPoolExecutor(max_workers=self.workers, mp_context=mp.get_context("spawn"),
                                           initializer=_pool_init, initargs=(self.img,))
        return self._ex

    def refine(self, dets: list[Det]) -> list[Det]:
        if not self.parallel or len(dets) < 64:
            return [refine(self.img, d) for d in dets]
        return list(self._executor().map(_refine_worker, dets,
                                         chunksize=max(1, len(dets) // (4 * self.workers))))

    def detect(self, jobs: list[tuple[float, str]], thr: float, gvar: float, box) -> list[tuple]:
        return list(self._executor().map(_detect_worker, [(w, a, thr, gvar, box) for w, a in jobs]))

    def close(self) -> None:
        if self._ex is not None:
            self._ex.shutdown()
            self._ex = None

    def __del__(self):                      # e.g. analyze() raised before close()
        if getattr(self, "_ex", None) is not None:
            self._ex.shutdown(wait=False)


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
    relocated: list = field(default_factory=list)   # bar sets moved to their layout position

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
    for k, (c, hv) in sorted(known.items()):
        if k in detected or not (k_lo <= k <= k_hi):
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
    n_keep = 0
    for e in small:
        if not any(kk in pred for kk in (e.k - 1, e.k, e.k + 1)):
            # the layout can't predict this region from the large elements alone (e.g. no
            # group pair is seen together with the pair 2 groups finer yet): keep it unverified;
            # it is what anchors the 1/4 self-similarity for the finest groups
            if e.k not in best_for:
                best_for[e.k] = (0.0, e)
                n_keep += 1
            continue
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
    if n_moved or n_drop or n_keep:
        log(f"    small elements checked against layout: {n_moved} re-labelled, {n_drop} dropped"
            + (f", {n_keep} kept unverified (no layout prediction there)" if n_keep else ""))
    return sorted(reliable + [e for _, e in best_for.values()], key=lambda e: e.k)


def _w_rel(phi: float, r: int) -> float:
    """Line width in px of relative index r (r grows with frequency)."""
    return 2.0 ** ((phi - r) / 6.0)


def _pair_of(K0: int, r: int) -> int:
    """Group-pair level of relative index r (pairs of groups (2p, 2p+1) -> p)."""
    return (K0 + r) // 12


def _similarity_t(elements: list[Element]) -> tuple[np.ndarray | None, int]:
    """Translation t of the 1/4 self-similarity c(r+12) = c(r)/4 + t, from all correspondences."""
    by_r = {e.r: e for e in elements}
    ts = [by_r[r + 12].center - by_r[r].center / 4 for r in by_r if r + 12 in by_r]
    if not ts:
        return None, 0
    return np.median(np.array(ts), axis=0), len(ts)


def redetect_missing(img: np.ndarray, elements: list[Element], phi: float, K0: int, polarity: float,
                     w_min: float, thr: float = 0.35, log=print, pool: WorkerPool | None = None) -> list[Element]:
    """
    Guided second pass for group pairs finer than the coarsest detected pair that have no
    detections (typically blurred or saturated). The matched filter is re-run only at that
    pair's 12 line widths, only inside the region of the next coarser pair, with a lower
    threshold. Hits are kept only if they obey the 1/4 self-similarity with the coarser pair,
    so digits and noise picked up at the low threshold are rejected.
    """
    for _ in range(4):
        present = {_pair_of(K0, e.r) for e in elements}
        missing = [P for P in range(min(present) + 1, max(present) + 2) if P not in present]
        if not missing:
            break
        P = missing[0]
        outer = [e for e in elements if _pair_of(K0, e.r) == P - 1]
        if len(outer) < 3:
            break
        r_lo = 12 * P - K0
        w_hi, w_lo = _w_rel(phi, r_lo), _w_rel(phi, r_lo + 11)
        if w_lo < w_min:
            w_lo = w_min
        if w_hi < w_min:
            break
        pts = np.array([[s_.x, s_.y] for e in outer for s_ in (e.h, e.v)])
        wo = _w_rel(phi, outer[0].r)
        x0, y0 = np.maximum(0, pts.min(0) - 6 * wo).astype(int)
        x1, y1 = np.minimum([img.shape[1], img.shape[0]], pts.max(0) + 6 * wo).astype(int)
        if x1 - x0 < 10 or y1 - y0 < 10:
            break
        sub = img[y0:y1, x0:x1]
        raw = detect(sub, w_lo / 1.06, w_hi * 1.06, thr, pool=pool, box=(int(y0), int(y1), int(x0), int(x1)))
        raw = [Det(d.x + x0, d.y + y0, d.w, d.axis, d.score) for d in raw if d.score * polarity > 0]
        dets = nms(raw, 1.5)
        dets = nms(pool.refine(dets) if pool else [refine(img, d) for d in dets], 1.2)
        dets = [d for d in dets if d.score * polarity >= thr]
        if not dets:
            break
        m = 6 * np.log2([d.w for d in dets])
        res = (m - phi + 0.5) % 1.0 - 0.5
        rr = -np.round(m - phi).astype(int)
        good = (np.abs(res) < 0.3) & (rr >= r_lo) & (rr <= r_lo + 11)
        # index candidate bar sets by (relative index, axis)
        groups: dict[tuple[int, str], list[Det]] = {}
        for d, r_, g_ in zip(dets, rr, good):
            if g_:
                groups.setdefault((int(r_), d.axis), []).append(d)
        trees = {key: (cKDTree(np.array([[d.x, d.y] for d in v])), v) for key, v in groups.items()}
        # outer bar sets and the (r, axis) their 1/4-scale copy must have
        outer_sets = [(e.r + 12, ax, s_) for e in outer for ax, s_ in (("y", e.h), ("x", e.v))]

        def inliers(t_):
            hit = []
            for r_, ax, s_ in outer_sets:
                if (r_, ax) not in trees:
                    continue
                tree, v = trees[(r_, ax)]
                pred = np.array([s_.x, s_.y]) / 4 + t_
                dist, idx = tree.query(pred)
                if dist < 1.5 * _w_rel(phi, r_):
                    hit.append((r_, ax, v[idx]))
            return hit

        # RANSAC-style: every (outer set, candidate) correspondence proposes a translation
        t0, _ = _similarity_t(elements)
        hyps = [t0] if t0 is not None else []
        for r_, ax, s_ in outer_sets:
            for d in groups.get((r_, ax), []):
                hyps.append(np.array([d.x, d.y]) - np.array([s_.x, s_.y]) / 4)
        best: list = []
        for t_ in hyps:
            hit = inliers(t_)
            if len(hit) > len(best):
                best = hit
        # >= 4 bar sets at different line widths agreeing on one translation is very unlikely
        # by chance (each must land within 1.5 w of its predicted position)
        if len(best) < max(4, len(outer_sets) // 6):
            log(f"    guided search, next finer group pair: nothing consistent found")
            break
        sets = {(r_, ax): d for r_, ax, d in best}
        t_fit = np.median(np.array([[d.x, d.y] for r_, ax, d in best]) -
                          np.array([[s_.x, s_.y] for r2, ax2, s_ in outer_sets
                                    for r_, ax, d in best if (r2, ax2) == (r_, ax)]) / 4, axis=0)
        by_r_outer = {e.r + 12: e for e in outer}
        keep = []
        for r_ in sorted({r_ for r_, _ in sets}):
            o = by_r_outer[r_]
            hh = sets.get((r_, "y")) or Det(o.h.x / 4 + t_fit[0], o.h.y / 4 + t_fit[1], _w_rel(phi, r_), "y", 0.0)
            vv = sets.get((r_, "x")) or Det(o.v.x / 4 + t_fit[0], o.v.y / 4 + t_fit[1], _w_rel(phi, r_), "x", 0.0)
            keep.append(Element(r=r_, h=hh, v=vv))
        elements = sorted(elements + keep, key=lambda e: e.r)
        log(f"    guided search, next finer group pair: {len(keep)} element(s) recovered "
            f"({len(best)} of {len(outer_sets)} bar sets matched the 1/4-scale layout)")
    return elements


def finer_pair_present(img: np.ndarray, elements: list[Element], phi: float, K0: int,
                       depth: int = 1) -> tuple[bool | None, float]:
    """
    Is there a group pair `depth` levels finer than the finest detected one? Even when its
    bars are blurred flat, each bar set still deposits its light: the integrated excess
    intensity around the positions predicted by the 1/4 self-similarity is compared with
    that of three solid bars (ratio ~1 if the pair exists, ~0 over empty background).
    Returns (None, nan) when it can't be tested (self-similarity unknown / outside image).
    """
    t, _ = _similarity_t(elements)
    if t is None:
        return None, float("nan")
    L = max(_pair_of(K0, e.r) for e in elements)
    base = [e for e in elements if _pair_of(K0, e.r) == L]
    pts = np.array([[s_.x, s_.y] for e in base for s_ in (e.h, e.v)])
    wb = _w_rel(phi, base[0].r)
    x0, y0 = np.maximum(0, pts.min(0) - 8 * wb).astype(int)
    x1, y1 = np.minimum([img.shape[1], img.shape[0]], pts.max(0) + 8 * wb).astype(int)
    region = img[y0:y1, x0:x1]
    dark = float(np.percentile(region, 10))
    bright = float(np.percentile(region, 99))
    if bright - dark <= 0:
        return None, float("nan")
    ratios = []
    for e in base:
        w = _w_rel(phi, e.r + 12 * depth)
        for s_ in (e.h, e.v):
            c = np.array([s_.x, s_.y])
            for _ in range(depth):
                c = c / 4 + t
            half = 4.5 * w
            xa, xb = int(round(c[0] - half)), int(round(c[0] + half)) + 1
            ya, yb = int(round(c[1] - half)), int(round(c[1] + half)) + 1
            if xa < 0 or ya < 0 or xb > img.shape[1] or yb > img.shape[0] or xb - xa < 3:
                continue
            excess = float(np.sum(img[ya:yb, xa:xb] - dark))
            ratios.append(excess / ((bright - dark) * 15.0 * w * w))
    if len(ratios) < 4:
        return None, float("nan")
    return bool(np.median(ratios) >= 0.35), float(np.median(ratios))


def check_layout(elements: list[Element], img: np.ndarray, px: float, k_lo: int, polarity: float,
                 tol: float = 4.0, agree: float = 1.5, log=print) -> list[Element]:
    """
    Leave-one-out check of every detected element against the slide layout predicted from
    all the others. If one bar set sits far from its predicted position (> tol·w) while the
    other agrees (< agree·w), the outlier was paired with the wrong feature (reference square,
    a digit, a neighbouring element): it is moved to the predicted position and re-snapped.
    """
    wpx = lambda k: line_width_um_k(k) / px
    n_fix = 0
    for e in elements:
        pred, _ = predict_positions([o for o in elements if o is not e], k_lo, K_MAX)
        if e.k not in pred:
            continue
        c, hv = pred[e.k]
        w = wpx(e.k)
        ph, pv = c - hv / 2, c + hv / 2
        dh = float(np.linalg.norm(np.array([e.h.x, e.h.y]) - ph)) / w
        dv = float(np.linalg.norm(np.array([e.v.x, e.v.y]) - pv)) / w
        if dh > tol and dv < agree:
            e.h = snap_predicted(img, Det(ph[0], ph[1], w, "y", 0.0), w, polarity)
            e.relocated.append("H")
        elif dv > tol and dh < agree:
            e.v = snap_predicted(img, Det(pv[0], pv[1], w, "x", 0.0), w, polarity)
            e.relocated.append("V")
        else:
            continue
        n_fix += 1
        g, el = k_to_ge(e.k)
        log(f"    G{g}E{el}: {e.relocated[-1]} set was {max(dh, dv):.1f} w off the layout "
            f"(paired with another feature) -> moved to its predicted position")
    if n_fix:
        log(f"    layout check: {n_fix} bar set(s) relocated")
    return elements


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
            w_min: float = 1.25, verbose: bool = True, limit_rule: str = "first-fail",
            skip_isolated: int = 1, dark_frame: np.ndarray | None = None,
            workers: int | None = None) -> dict:
    """workers: processes for the matched-filter bank and candidate refinement (default: CPU count,
    at most 8; 1 = serial).
    It changes only the speed, not the result."""
    log = print if verbose else (lambda *a, **k: None)
    workers = default_workers() if workers is None else workers
    notes: list[str] = []

    img0 = img_raw.astype(np.float64)
    off = (0, 0)
    if roi:
        x0, y0, x1, y1 = roi
        img0 = img0[y0:y1, x0:x1]
        off = (x0, y0)

    # ---- background ---------------------------------------------------------
    # Contrast is always measured twice: on the raw image and after a background correction.
    # The correction is a dark frame (per pixel) if given, else a fixed value if given, else an
    # automatic estimate (darkest 0.5 % of the median-filtered image). The automatic estimate
    # cannot tell camera offset from stray light, so it is never the primary result: the
    # primary result is the corrected one only when the user supplied a dark frame or value.
    auto_black = float(np.percentile(ndimage.median_filter(img0, 5), 0.5))
    if dark_frame is not None:
        dark = np.asarray(dark_frame, dtype=np.float64)
        if roi:
            dark = dark[y0:y1, x0:x1]
        if dark.shape != img0.shape:
            raise ValueError(f"Dark frame shape {dark.shape} does not match image {img0.shape}.")
        bg, bg_method, primary = dark, f"dark frame (mean {dark.mean():.4g})", "corrected"
    elif black_level == "auto":
        bg, bg_method, primary = auto_black, f"automatic black level {auto_black:.4g}", "corrected"
    elif black_level == "none":
        bg, bg_method, primary = auto_black, f"automatic black level {auto_black:.4g}", "raw"
    else:
        bg, bg_method, primary = float(black_level), f"black level {float(black_level):.4g}", "corrected"
    img_corr = img0 - bg
    black = float(np.mean(bg)) if primary == "corrected" else 0.0

    img, frame = derotate(img0)
    log(f"[1] orientation: de-rotated by {frame.angle:+.2f}°")

    w_max = max(w_min * 2, min(img.shape) / 22)
    img = np.ascontiguousarray(img)         # no-op for images read from disk; the workers get this layout
    pool = WorkerPool(img, workers)
    raw = detect(img, w_min, w_max, min_ncc, pool=pool)
    dets = nms(raw, 1.5)
    log(f"[2] matched filter: {len(raw)} raw peaks -> {len(dets)} after suppression")
    dets = nms(pool.refine(dets), 1.2)
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

    if h is not None:
        n_before = len(elements)
        elements = redetect_missing(img, elements, phi, K0, polarity, w_min, log=log, pool=pool)
    pool.close()                            # last use of the workers; frees them
    if h is not None:
        if len(elements) > n_before:
            notes.append(f"{len(elements) - n_before} element(s) of a blurred / saturated group pair "
                         "recovered by a guided low-threshold search (consistent with the slide's "
                         "1/4 self-similarity).")
        if method.endswith("slide's finest"):
            # recovered pairs may sit past the slide's finest under the current assumption
            while max(e.r for e in elements) + K0 > K_MAX and min(e.r for e in elements) + K0 - 12 >= K_MIN:
                K0 -= 12
            # The finest *detected* pair need not be the slide's finest: a finer pair that is
            # blurred flat still shows up as light at its predicted position.
            shifted = 0
            while True:
                present, ratio = finer_pair_present(img, elements, phi, K0, depth=1 + shifted)
                if present is None:
                    if shifted == 0:
                        notes.append("Could not test whether a finer, unresolved group pair is present "
                                     "(only one group pair visible).")
                    break
                log(f"    finer-pair check (depth {1 + shifted}): light ratio {ratio:.2f} -> "
                    f"{'present' if present else 'absent'}")
                if not present or min(e.r for e in elements) + K0 - 12 < K_MIN:
                    break
                K0 -= 12
                shifted += 1
            if shifted:
                method = ("layout (mod 12) + finest groups located by the light of the unresolved "
                          "finer pair(s)")
                notes[:] = [n for n in notes if not n.startswith("Group number assumed")]
                notes.append(f"An unresolved finer group pair was found at the position the layout "
                             f"predicts, so the detected groups are {2 * shifted} group(s) coarser than "
                             "the 'finest visible' assumption. Pass --pixel-size to confirm.")
                log(f"    -> identification shifted by {2 * shifted} groups")

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
    elements = check_layout(elements, img, px_fit, k_lo, polarity, log=log)
    extra = predict_missing(elements, k_lo, K_MAX, img.shape)
    for e in extra:
        w_px = line_width_um_k(e.k) / px_fit
        e.h = snap_predicted(img, e.h, w_px, polarity)
        e.v = snap_predicted(img, e.v, w_px, polarity)
    log(f"[7] located {len(extra)} undetected elements (column geometry + 1/4 self-similarity)")
    all_el = sorted(elements + extra, key=lambda e: e.k)

    # ---- contrast ----------------------------------------------------------
    img_p, img_s = (img_corr, img0) if primary == "corrected" else (img0, img_corr)
    coeffs = ndimage.spline_filter(img_p, order=3)
    coeffs_s = ndimage.spline_filter(img_s, order=3)
    alt: dict[int, dict[str, float]] = {}
    for e in all_el:
        w_px = line_width_um_k(e.k) / px_fit
        e.meas["H"] = measure_set(coeffs, e.h, w_px, polarity, True, frame, img_p)
        e.meas["V"] = measure_set(coeffs, e.v, w_px, polarity, True, frame, img_p)
        alt[e.k] = {q: measure_set(coeffs_s, (e.h if q == "H" else e.v), w_px, polarity, True,
                                   frame)["michelson"] for q in ("H", "V")}

    # camera full scale: flag elements whose bars reach it (clipped peaks bias contrast)
    vmax = float(img0.max())
    sat_level = next((fs for fs in (255.0, 1023.0, 4095.0, 16383.0, 65535.0) if abs(vmax - fs) < 0.5), None)
    rows = []
    for e in all_el:
        g, el = k_to_ge(e.k)
        w_px = line_width_um_k(e.k) / px_fit
        cH, cV = e.meas["H"]["michelson"], e.meas["V"]["michelson"]
        cmin = min(cH, cV)
        aH, aV = alt[e.k]["H"], alt[e.k]["V"]
        undersampled = 2 * w_px < 2.0
        polys = {}
        cut_off = False
        H0, W0 = img0.shape
        for key, s in (("H", e.meas["H"]), ("V", e.meas["V"])):
            axis = "y" if key == "H" else "x"
            hw = 2.5 * w_px
            corners = np.array([[-hw, -hw], [hw, -hw], [hw, hw], [-hw, hw]]) + [s["cx"], s["cy"]]
            ox, oy = frame.to_original(corners[:, 0], corners[:, 1])
            # a bar set not fully inside the image can't be measured: flag it, don't fail it
            cut_off |= bool(np.any(ox < 0) or np.any(oy < 0) or np.any(ox > W0 - 1) or np.any(oy > H0 - 1))
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
            "passes": bool(cmin >= contrast and not undersampled and not cut_off),
            "contrast_H_raw": round(cH if primary == "raw" else aH, 4),
            "contrast_V_raw": round(cV if primary == "raw" else aV, 4),
            "contrast_H_corrected": round(aH if primary == "raw" else cH, 4),
            "contrast_V_corrected": round(aV if primary == "raw" else cV, 4),
            "passes_alt": bool(min(aH, aV) >= contrast and not undersampled and not cut_off),
            "undersampled": bool(undersampled),
            "cut_off": cut_off,
            "saturated": bool(sat_level is not None and max(
                max(img0[y, x] for x, y in e.meas[q]["scan"]["pixels_xy"]) for q in ("H", "V"))
                >= sat_level - 0.5),
            "relocated": list(e.relocated),
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

    # Limit. "first-fail" (default): walk from the coarsest measured element towards finer
    # ones and stop at the first element that fails (or a missing one); the limit is the last
    # passing element before it. Up to `skip_isolated` failures are tolerated when they are
    # isolated, i.e. the very next element passes again (a single out-of-focus element at the
    # edge of the field should not end the reading). "finest-pass": the finest element that
    # passes at all.
    # Elements cut off by the image border are not measurable and are stepped over.
    def walk(key: str):
        ff, prev_k, skp = None, None, []
        meas_rows = [r for r in rows if not r["cut_off"]]
        for r in rows:
            if prev_k is not None and r["k"] != prev_k + 1:
                break
            prev_k = r["k"]
            if r["cut_off"]:
                continue
            if r[key]:
                ff = r
                continue
            j_m = meas_rows.index(r)
            nxt_r = meas_rows[j_m + 1] if j_m + 1 < len(meas_rows) else None
            isolated = nxt_r is not None and nxt_r[key] and all(
                q["cut_off"] for q in rows if r["k"] < q["k"] < nxt_r["k"])
            if isolated and len(skp) < skip_isolated:
                skp.append(r)
                continue
            break
        passing = [r for r in rows if r[key]]
        fp = max(passing, key=lambda r: r["k"]) if passing else None
        return ff, skp, fp

    first_fail_lim, skipped, finest_pass_lim = walk("passes")
    limit = first_fail_lim if limit_rule == "first-fail" else finest_pass_lim
    ff_a, _, fp_a = walk("passes_alt")
    limit_alt = ff_a if limit_rule == "first-fail" else fp_a

    def _name(r):
        return f"G{r['group']}E{r['element']}" if r else "none"

    lim_raw, lim_corr = (limit, limit_alt) if primary == "raw" else (limit_alt, limit)
    if _name(lim_raw) != _name(lim_corr):
        notes.append(f"Background matters here: raw image -> {_name(lim_raw)}, after {bg_method} -> "
                     f"{_name(lim_corr)}. "
                     + ("The automatic estimate can't tell camera offset from stray light; take a dark "
                        "frame (light blocked, same exposure) and pass --dark-frame for a corrected result."
                        if dark_frame is None else
                        "The dark frame removes only the camera offset; stray light stays in the raw-image value too."))

    sat = [_name(r) for r in rows if r["saturated"] and not r["cut_off"]]
    if sat:
        notes.append(f"Bars reach the camera's full scale ({sat_level:.0f}) in {len(sat)} element(s) "
                     f"({sat[0]}-{sat[-1]}): clipped peaks bias contrast; lower the exposure if possible.")
    cut = [_name(r) for r in rows if r["cut_off"]]
    if cut:
        notes.append("Not measurable, cut off by the image border (stepped over): " + ", ".join(cut))
    rel = [f"{_name(r)} {'+'.join(r['relocated'])}" for r in rows if r["relocated"]]
    if rel:
        notes.append("Bar sets moved to their layout position (detection was paired with another "
                     "feature): " + ", ".join(rel))
    if limit_rule == "first-fail":
        for r in skipped:
            notes.append(f"Skipped isolated failure {_name(r)} (C_H {100 * r['contrast_H']:.1f}%, "
                         f"C_V {100 * r['contrast_V']:.1f}%): the next element passes again, so it is "
                         "treated as a local focus / field-of-view effect (--skip-isolated 0 to stop there).")
    if finest_pass_lim is not None and finest_pass_lim is not first_fail_lim:
        if limit_rule == "first-fail":
            stop = next((r for r in rows if not r["cut_off"] and not r["passes"]
                         and r["k"] not in {q["k"] for q in skipped}
                         and (first_fail_lim is None or r["k"] > first_fail_lim["k"])), None)
            if stop is not None:
                notes.append(f"Stopped at the first failing element {_name(stop)} "
                             f"(C_H {100 * stop['contrast_H']:.1f}%, C_V {100 * stop['contrast_V']:.1f}%); "
                             f"finer elements up to {_name(finest_pass_lim)} pass again "
                             f"(--limit-rule finest-pass would report {_name(finest_pass_lim)}).")
        else:
            notes.append(f"Coarser elements fail below the reported limit; "
                         f"--limit-rule first-fail would report {_name(first_fail_lim)}.")
    if limit and limit["line_width_px"] < 2.0:
        sl = min(limit["scanline_contrast_H"], limit["scanline_contrast_V"])
        notes.append(f"The limit element has only {limit['line_width_px']:.2f} px per line: its contrast "
                     "relies on sub-pixel averaging along the (tilted) bars. A single row of pixels reads "
                     f"{100 * sl:.1f}% there. The result is close to the camera's sampling limit.")
    if limit:
        nxt = [r for r in rows if r["k"] > limit["k"] and not r["cut_off"]][:1]
        if not nxt:
            notes.append("The next finer element could not be measured (outside field / not located).")
        elif nxt[0]["undersampled"]:
            notes.append("The next finer element is below the camera's Nyquist limit: result is pixel-limited.")

    # ---- CTF fit (reads the measured contrasts, never changes them) ----------
    fit = ctf_fit.fit_ctf(rows, px_fit, frame.angle, polarity, contrast,
                          flare_min=0.0 if primary == "raw" else -0.1)
    if fit.get("crossing_lp_per_mm"):
        d = fit["directions"]
        fx, fu = fit["crossing_lp_per_mm"], fit["crossing_lp_per_mm_unc"]
        log(f"[9] CTF fit: {100 * contrast:.0f}% crossing at {fx:.1f}"
            + (f" ± {fu:.1f}" if fu else "") + f" lp/mm ({fit['limit_element']}, "
            f"{fit['limiting_direction']} lines decide)")
        if limit and fit["limit_element"] != _name(limit):
            notes.append(f"The fitted CTF curve crosses {100 * contrast:.0f}% at {fx:.1f} lp/mm, inside "
                         f"{fit['limit_element']}, while the element-by-element limit is {_name(limit)}. "
                         "They can differ when elements near the threshold are within the measurement "
                         "noise of it; the fit uses all elements at once.")
        if max(d["H"]["rms_residual"], d["V"]["rms_residual"]) > 0.05:
            notes.append("The CTF model fits poorly here (rms residual "
                         f"{100 * max(d['H']['rms_residual'], d['V']['rms_residual']):.1f}%): the blur is "
                         "not described by the model or changes across the field. Trust the measured elements "
                         "over the fit.")
        if fit.get("beyond_nyquist"):
            notes.append("The fitted crossing lies beyond the camera's Nyquist limit: the result is pixel-limited.")
        elif fit.get("extrapolated"):
            notes.append("The fitted crossing lies beyond the finest measured element (extrapolated).")
        if fit.get("ill_defined"):
            notes.append("CTF fit: the fitted contrast never rises far above the threshold, so where it "
                         "crosses is poorly defined (see the uncertainty).")
    elif fit.get("crossing_lp_per_mm") == 0.0:
        notes.append("CTF fit: the fitted curve never reaches the threshold.")

    return {
        "contrast_threshold": contrast,
        "limit_rule": limit_rule,
        "result_first_fail": None if not first_fail_lim else _name(first_fail_lim),
        "skipped_isolated_failures": [_name(r) for r in skipped] if limit_rule == "first-fail" else [],
        "result_finest_pass": None if not finest_pass_lim else _name(finest_pass_lim),
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
        "background": {
            "primary": primary,
            "correction": bg_method,
            "auto_estimate": round(auto_black, 4),
            "result_raw": _name(lim_raw) if lim_raw else None,
            "result_corrected": _name(lim_corr) if lim_corr else None,
            "lp_per_mm_raw": lim_raw["lp_per_mm"] if lim_raw else None,
            "lp_per_mm_corrected": lim_corr["lp_per_mm"] if lim_corr else None,
        },
        "ctf_fit": fit,
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
        if r["cut_off"]:
            col = (140, 140, 140)
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
    _draw_fit_box(im, res, scale)
    im.save(path)


def fit_summary_lines(res: dict) -> list[tuple[str, tuple[int, int, int]]]:
    """Short text lines (and colours) summarising the element limit and the CTF fit."""
    thr = 100 * res["contrast_threshold"]
    lim = res["result"]
    out = [(f"Element limit @ {thr:.0f}%: " + (f"G{lim['group']}E{lim['element']} ({lim['lp_per_mm']:.1f} lp/mm)"
                                               if lim else "none"), (60, 200, 255))]
    fit = res.get("ctf_fit") or {}
    if not fit.get("crossing_lp_per_mm"):
        out.append(("CTF fit: " + (fit.get("error") or "no threshold crossing"), (230, 230, 230)))
        return out
    fu = fit.get("crossing_lp_per_mm_unc")
    out.append((f"CTF fit: {thr:.0f}% at {fit['crossing_lp_per_mm']:.1f}" + (f" ± {fu:.1f}" if fu else "")
                + f" lp/mm, in {fit['limit_element']} ({fit['limiting_direction']} lines decide)", (200, 150, 255)))
    for q in ("H", "V"):
        d = fit["directions"][q]
        blur = (f"blur σ {d['sigma_um']:.2f} µm" if d["psf"] == "gaussian" else
                f"blur σ {d['sigma_um']:.2f} µm + {100 * d['halo_fraction']:.0f}% halo σ {d['halo_sigma_um']:.1f} µm")
        out.append((f"  {q} lines: {blur}, stray light {100 * d['stray_light']:.0f}%, "
                    f"fit rms {100 * d['rms_residual']:.1f}%", (230, 230, 230)))
    warn = []
    if max(fit["directions"][q]["rms_residual"] for q in ("H", "V")) > 0.05:
        warn.append("fit is poor, trust the measured elements")
    if fit.get("ill_defined"):
        warn.append("crossing poorly defined")
    if fit.get("beyond_nyquist"):
        warn.append("beyond camera Nyquist")
    elif fit.get("extrapolated"):
        warn.append("extrapolated past the finest element")
    if warn:
        out.append(("  Warning: " + "; ".join(warn), (255, 190, 60)))
    return out


def _draw_fit_box(im: Image.Image, res: dict, scale: float) -> None:
    """Text box with the element limit and the CTF fit, in the image corner with the fewest elements."""
    lines = fit_summary_lines(res)
    fs = int(np.clip(im.width / 75, 13, 30))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", fs)
    except OSError:
        font = ImageFont.load_default()
    dr = ImageDraw.Draw(im)
    pad, gap = fs // 2, fs // 4
    sizes = [dr.textbbox((0, 0), t, font=font) for t, _ in lines]
    bw = max(b[2] - b[0] for b in sizes) + 2 * pad
    bh = sum(b[3] - b[1] + gap for b in sizes) + 2 * pad
    m = fs // 2
    corners = [(m, m), (im.width - bw - m, m), (m, im.height - bh - m), (im.width - bw - m, im.height - bh - m)]
    pts = np.array([[x * scale, y * scale] for r in res["elements"]
                    for key in ("polygon_H_px", "polygon_V_px") for x, y in r[key]])

    def crowd(c):
        x0, y0 = c
        if not len(pts):
            return 0
        return int(np.sum((pts[:, 0] > x0 - m) & (pts[:, 0] < x0 + bw + m) &
                          (pts[:, 1] > y0 - m) & (pts[:, 1] < y0 + bh + m)))

    x0, y0 = min(corners, key=crowd)
    box = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(box).rectangle([x0, y0, x0 + bw, y0 + bh], fill=(0, 0, 0, 185))
    im.paste(Image.alpha_composite(im.convert("RGBA"), box).convert("RGB"))
    dr = ImageDraw.Draw(im)
    y = y0 + pad
    for (t, col), b in zip(lines, sizes):
        dr.text((x0 + pad, y - b[1]), t, fill=col, font=font)
        y += b[3] - b[1] + gap


def save_ctf_plot(res: dict, path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r for r in res["elements"] if not r["cut_off"]]
    f = np.array([r["lp_per_mm"] for r in rows])
    det = np.array([r["detected"] for r in rows])
    fig, ax = plt.subplots(figsize=(11.5, 5))
    bgd = res["background"]
    other = "corrected" if bgd["primary"] == "raw" else "raw"
    for key, colr in (("contrast_H", "tab:blue"), ("contrast_V", "tab:orange")):
        c2 = np.array([r[f"{key}_{other}"] for r in rows])
        ax.plot(f, c2, color=colr, lw=0.8, ls="--", alpha=0.6,
                label=f"{key[-1]} lines, " + ("raw image" if other == "raw" else bgd["correction"]))
    for key, mk, colr in (("contrast_H", "o", "tab:blue"), ("contrast_V", "s", "tab:orange")):
        c = np.array([r[key] for r in rows])
        ax.plot(f, c, color=colr, lw=0.8, alpha=0.6)
        ax.scatter(f[det], c[det], marker=mk, color=colr, label=f"{key[-1]} lines (detected)", zorder=3)
        ax.scatter(f[~det], c[~det], marker=mk, facecolors="none", edgecolors=colr,
                   label=f"{key[-1]} lines (extrapolated)", zorder=3)
    fit = res.get("ctf_fit") or {}
    if fit.get("directions"):
        ff = np.geomspace(0.8 * f.min(), 1.25 * max(f.max(), 500.0 / res["pixel_size_um_fitted"]), 300)
        off = ctf_fit._pixel_offsets(res["pixel_size_um_fitted"], res["rotation_deg"])
        pol = 1 if res["polarity"] == "bright-bars" else -1
        for q, colr in (("H", "tab:blue"), ("V", "tab:orange")):
            d = fit["directions"][q]
            psf = (f"σ {d['sigma_um']:.2f} µm" if d["psf"] == "gaussian" else
                   f"core σ {d['sigma_um']:.2f} µm {100 * (1 - d['halo_fraction']):.0f}% + "
                   f"halo σ {d['halo_sigma_um']:.1f} µm {100 * d['halo_fraction']:.0f}%")
            ax.plot(ff, ctf_fit.curve(d, 500.0 / ff, off, pol), color=colr, lw=2.4, alpha=0.35,
                    label=f"{q} fit: {psf}, stray light {100 * d['stray_light']:.0f}%")
        if fit.get("crossing_lp_per_mm"):
            fx, fu = fit["crossing_lp_per_mm"], fit.get("crossing_lp_per_mm_unc") or 0.0
            if fu:
                ax.axvspan(fx - fu, fx + fu, color="tab:purple", alpha=0.12, lw=0)
            ax.axvline(fx, color="tab:purple", lw=1.2, ls="-.",
                       label=f"fit crossing {fx:.1f}" + (f" ± {fu:.1f}" if fu else "")
                             + f" lp/mm ({fit['limit_element']})")
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
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
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
                     + ("" if r["detected"] else "  (located)")
                     + ("  CUT OFF" if r["cut_off"] else "")
                     + (f"  (moved {'+'.join(r['relocated'])})" if r["relocated"] else ""),
                     fontsize=8, color="0.5" if r["cut_off"] else ("tab:green" if ok else "tab:red"))
        ax.tick_params(labelsize=7)
        if r_i == len(rows) - 1 or i >= (nrows - 1) * ncols:
            ax.set_xlabel("position across bars [µm]", fontsize=7)
    axes[0, 0].legend(fontsize=7, loc="lower right")
    bgd = res["background"]
    what = "raw pixel values" if bgd["primary"] == "raw" else f"pixel values after {bgd['correction']}"
    fig.suptitle(f"{title}  ({what})\nshaded = ideal bar positions; dashed = bar (green) / gap (purple) "
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
    ap.add_argument("--dark-frame", type=Path, nargs="+", default=None,
                    help="dark frame(s): same camera, exposure and gain, light blocked. Averaged and "
                         "subtracted per pixel; the corrected contrast becomes the primary result")
    ap.add_argument("--black-level", default="none",
                    help="'none' (default: primary result on the raw image), a number to subtract, or "
                         "'auto' (darkest 0.5%% of the image; may remove stray light too). The raw and "
                         "corrected results are both always reported")
    ap.add_argument("--roi", type=int, nargs=4, default=None, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--limit-rule", choices=("first-fail", "finest-pass"), default="first-fail",
                    help="first-fail (default): last passing element before the first failure, "
                         "going from coarse to fine; finest-pass: finest element that passes at all")
    ap.add_argument("--skip-isolated", type=int, default=1,
                    help="first-fail rule: how many isolated failures (next element passes again) "
                         "to step over (default 1; 0 = stop at the very first failure)")
    ap.add_argument("--min-ncc", type=float, default=0.55, help="matched-filter detection threshold")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=None,
                    help="processes for the matched-filter bank and candidate refinement (default: CPU count, at most 8; "
                         "1 = serial). Changes only the speed, not the result")
    args = ap.parse_args()

    px = args.pixel_size
    if px is None and args.magnification and args.camera_pixel:
        px = args.camera_pixel / args.magnification
    bl = args.black_level if args.black_level in ("none", "auto") else float(args.black_level)

    img = load_gray(args.image)
    dark = None
    if args.dark_frame:
        dark = np.mean([load_gray(pth) for pth in args.dark_frame], axis=0)
    res = analyze(img, args.contrast, px, args.coarsest_group, bl, tuple(args.roi) if args.roi else None,
                  args.min_ncc, limit_rule=args.limit_rule,
                  skip_isolated=args.skip_isolated, dark_frame=dark, workers=args.workers)
    res["image"] = str(args.image)

    out = args.out_dir or args.image.parent / "usaf_results"
    out.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    (out / f"{stem}_usaf.json").write_text(json.dumps(res, indent=2))
    cols = ["group", "element", "lp_per_mm", "line_width_um", "line_width_px", "detected",
            "contrast_H", "contrast_V", "contrast_min", "lockin_H", "lockin_V",
            "scanline_contrast_H", "scanline_contrast_V",
            "contrast_H_raw", "contrast_V_raw", "contrast_H_corrected", "contrast_V_corrected",
            "passes", "undersampled", "cut_off", "fit_H", "fit_V"]
    # fitted contrast from the CTF fit, as extra columns; the measured values are written unchanged
    fitted = {(e["group"], e["element"], q): e["fitted"]
              for q, d in (res["ctf_fit"].get("directions") or {}).items() for e in d["per_element"]}
    with open(out / f"{stem}_usaf.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        for r in res["elements"]:
            wr.writerow({**r, **{f"fit_{q}": fitted.get((r["group"], r["element"], q), "") for q in ("H", "V")}})
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
        if r["cut_off"]:
            st = "cut off"
        st += "" if r["detected"] else " (extrapolated)"
        st += f" (moved {'+'.join(r['relocated'])})" if r["relocated"] else ""
        print(f"{r['group']:>3} {r['element']:>2} {r['lp_per_mm']:>8.2f} {r['line_width_um']:>7.3f} "
              f"{r['line_width_px']:>6.2f}  {100 * r['contrast_H']:>5.1f}% {100 * r['contrast_V']:>5.1f}%  "
              f"{100 * r['scanline_contrast_H']:>5.1f}% {100 * r['scanline_contrast_V']:>5.1f}%  {st}")
    print()
    print(f"Pixel size (fitted): {res['pixel_size_um_fitted']:.4g} µm/px   identification: {res['identification']}")
    bgd = res["background"]
    print(f"Primary result on: {'raw image' if bgd['primary'] == 'raw' else 'image after ' + bgd['correction']}")
    print(f"  raw image:               {bgd['result_raw']}"
          + (f" ({bgd['lp_per_mm_raw']:.2f} lp/mm)" if bgd["lp_per_mm_raw"] else ""))
    print(f"  after {bgd['correction']}: {bgd['result_corrected']}"
          + (f" ({bgd['lp_per_mm_corrected']:.2f} lp/mm)" if bgd["lp_per_mm_corrected"] else ""))
    if res["result"]:
        r = res["result"]
        print(f"RESULT @ {100 * args.contrast:.0f}% contrast: Group {r['group']} Element {r['element']}  "
              f"= {r['lp_per_mm']:.2f} lp/mm, line width {r['line_width_um']:.3f} µm "
              f"(C_H {100 * r['contrast_H']:.1f}%, C_V {100 * r['contrast_V']:.1f}%)")
    else:
        print(f"RESULT: no element reaches {100 * args.contrast:.0f}% contrast.")
    fit = res["ctf_fit"]
    if fit.get("crossing_lp_per_mm"):
        fu = fit["crossing_lp_per_mm_unc"]
        print(f"CTF FIT: crosses {100 * args.contrast:.0f}% at {fit['crossing_lp_per_mm']:.2f}"
              + (f" ± {fu:.2f}" if fu else "") + f" lp/mm, inside {fit['limit_element']} "
              f"({fit['limiting_direction']} lines decide)")
        for q in ("H", "V"):
            d = fit["directions"][q]
            cx = d["crossing_lp_per_mm"]
            if d["psf"] == "gaussian":
                psf = f"Gaussian blur sigma {d['sigma_um']:.2f} µm (FWHM {d['fwhm_um']:.2f} µm)"
            else:
                psf = (f"blur core sigma {d['sigma_um']:.2f} µm ({100 * (1 - d['halo_fraction']):.0f}%) + halo "
                       f"sigma {d['halo_sigma_um']:.1f} µm ({100 * d['halo_fraction']:.0f}%)")
            print(f"  {q} lines: {psf}, stray light "
                  f"{100 * d['stray_light']:.1f}%, crossing {cx if cx is None else round(cx, 2)} lp/mm, "
                  f"rms residual {100 * d['rms_residual']:.1f}%")
    elif "error" in fit:
        print(f"CTF FIT: {fit['error']}")
    for n in res["notes"]:
        print("note:", n)
    print(f"Saved results to {out}/")


if __name__ == "__main__":
    main()

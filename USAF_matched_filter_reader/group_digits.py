"""
Read the printed group numbers of a USAF 1951 slide to settle which groups are in view.

The bar sets alone fix the group numbers only up to steps of 2 groups: every group pair is
an exact 1/4-scale copy of the pair around it, so groups (g, g+1) and (g-2, g-1) look the
same apart from the digits printed next to them. Usually the finest visible pair is taken
as the slide's finest, but slides end at different groups (7 on the standard slide, 9 on
high-resolution ones), so the printed numbers are the only way to tell.

Method, for every group pair with at least 2 detected elements:
  1. Map the slide layout (generate_usaf_target.pair_block) onto the image with an affine
     fit to the detected bar-set centres, weighted towards the bar sets near each printed
     number (the layout is exact only locally). The map includes rotation and mirroring,
     so everything sampled through it comes out upright and unmirrored.
  2. Reference digits: the pair's element numbers (1-6, known from the layout), cut out
     tightly. They share the group numbers' font, blur, exposure and sampling.
  3. Each group number is searched for in a window around its layout position, with the
     reference digit each hypothesis predicts, at a few sizes (printed group numbers are
     larger than element numbers by a slide-dependent factor). The score is the best
     normalised correlation. Because of the self-similarity the window is the same under
     every hypothesis; only the digit looked for differs.

Only digits 1-6 have references, so a group number is used only when every hypothesis
predicts a digit in 1-6 for it.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import ndimage, signal

import generate_usaf_target as gen

MIN_REF_PX = 9.0           # smallest element-number height (px) usable as a reference digit
MIN_GROUP_PX = 9.0         # smallest group-number height (px) worth searching for
SAMPLES_PER_H = 28         # samples across a reference digit's height
SIZES = (0.8, 0.95, 1.1, 1.3, 1.5)   # group-number height / layout height, searched
MAX_FIT_ERR = 0.8          # local layout-fit error allowed, in line widths
NEAREST_ELEMENTS = 3       # elements (H + V bar sets each) a number's local map is fitted to
MIN_SCORE = 0.75           # a printed number votes only if its best match scores this ...
MIN_LEAD = 0.10            # ... and leads the next hypothesis by this much
MIN_VOTES = 2              # votes the winning hypothesis needs


@lru_cache(maxsize=64)
def _pair_layout(g: int):
    """Bar-set centres and printed numbers of pair (g, g+1), in slide µm."""
    blk = gen.pair_block(g, True, None)
    centres = {}
    for e in blk.elements:
        hr, vr = e.h_lines, e.v_lines
        centres[(e.group, e.element)] = (((hr.x0 + hr.x1) / 2, (hr.y0 + hr.y1) / 2),
                                         ((vr.x0 + vr.x1) / 2, (vr.y0 + vr.y1) / 2))
    # construction order in gen._pair_layout: left label g, elements g:2-6, right label g+1,
    # elements (g+1):1-6, corner label g, corner element g:1
    roles = ([("group", 0)] + [("elem", e) for e in range(2, 7)] + [("group", 1)]
             + [("elem", e) for e in range(1, 7)] + [("group", 0), ("elem", 1)])
    if len(blk.texts) != len(roles):
        raise RuntimeError("unexpected slide layout from generate_usaf_target")
    texts = []
    for t, (kind, val) in zip(blk.texts, roles):
        if kind == "elem" and t.text != str(val):
            raise RuntimeError("unexpected element-number order in the slide layout")
        texts.append((kind, val, t))       # group: val = offset (0 -> g, 1 -> g+1)
    return centres, texts


def _fit_affine(src: np.ndarray, dst: np.ndarray, weights: np.ndarray) -> np.ndarray:
    P = np.hstack([src, np.ones((len(src), 1))])
    sw = np.sqrt(weights)[:, None]
    A, *_ = np.linalg.lstsq(P * sw, dst * sw, rcond=None)
    return A                                        # (3, 2): [x, y, 1] @ A -> (x_px, y_px)


def _sample(img: np.ndarray, A: np.ndarray, u0, u1, v0, v1, step) -> np.ndarray | None:
    """Image sampled through map A on a grid over slide coordinates [u0,u1]x[v0,v1]."""
    nx, ny = int((u1 - u0) / step) + 1, int((v1 - v0) / step) + 1
    if nx < 4 or ny < 4 or nx * ny > 400_000:
        return None
    U, V = np.meshgrid(u0 + step * np.arange(nx), v0 + step * np.arange(ny))
    with np.errstate(all="ignore"):
        xy = np.stack([U.ravel(), V.ravel(), np.ones(U.size)], 1) @ A
    if not np.all(np.isfinite(xy)):
        return None
    x, y = xy[:, 0], xy[:, 1]
    if x.min() < 0 or y.min() < 0 or x.max() > img.shape[1] - 1 or y.max() > img.shape[0] - 1:
        return None
    return ndimage.map_coordinates(img, [y, x], order=1).reshape(ny, nx)


def _reference(img: np.ndarray, A: np.ndarray, t, polarity: float) -> np.ndarray | None:
    """Tight cut-out of an element number, upright, `SAMPLES_PER_H` samples tall; or None."""
    h = t.height
    width = gen.LABEL_WIDTH / gen.LABEL_HEIGHT * h * len(t.text)
    px, py = 0.5 * h, 0.4 * h
    a = _sample(img, A, t.x - px, t.x + width + px, t.y - py, t.y + h + py, h / SAMPLES_PER_H)
    if a is None:
        return None
    a = polarity * a
    a -= np.percentile(a, 10)
    top = np.percentile(a, 99)
    if top <= 0:
        return None
    lab, n = ndimage.label(a > 0.5 * top)
    ny, nx = a.shape
    iy0, iy1 = int(0.4 * SAMPLES_PER_H), int(1.4 * SAMPLES_PER_H)      # the nominal text box
    ix0, ix1 = int(0.5 * SAMPLES_PER_H), nx - int(0.5 * SAMPLES_PER_H)
    keep = [i for i, sl in enumerate(ndimage.find_objects(lab), 1)
            if sl is not None and sl[0].start < iy1 and sl[0].stop > iy0
            and sl[1].start < ix1 and sl[1].stop > ix0
            and sl[0].start > 0 and sl[1].start > 0 and sl[0].stop < ny and sl[1].stop < nx]
    if not keep:
        return None
    rows, cols = np.nonzero(np.isin(lab, keep))
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    if r1 - r0 < 0.6 * SAMPLES_PER_H:
        return None                                 # not a whole digit
    m = max(1, SAMPLES_PER_H // 10)                 # keep a little background around it
    return a[max(0, r0 - m):r1 + m, max(0, c0 - m):c1 + m]


def _ncc_max(window: np.ndarray, tmpl: np.ndarray) -> float:
    """Best normalised cross-correlation of tmpl anywhere inside window."""
    th, tw = tmpl.shape
    if th > window.shape[0] or tw > window.shape[1]:
        return -1.0
    t = tmpl - tmpl.mean()
    tn = math.sqrt(float(np.sum(t * t)))
    if tn == 0:
        return -1.0
    num = signal.correlate(window, t, mode="valid", method="fft")
    c1 = np.cumsum(np.cumsum(np.pad(window, ((1, 0), (1, 0))), 0), 1)
    c2 = np.cumsum(np.cumsum(np.pad(window * window, ((1, 0), (1, 0))), 0), 1)
    def box(c):
        return c[th:, tw:] - c[:-th, tw:] - c[th:, :-tw] + c[:-th, :-tw]
    n = th * tw
    var = box(c2) - box(c1) ** 2 / n
    den = np.sqrt(np.maximum(var, 1e-9)) * tn
    return float(np.max(num / den))


def read_group_numbers(img: np.ndarray, elements, K0: int, polarity: float,
                       candidates: list[int]) -> dict:
    """
    Score each candidate K0 (group/element index offset: k = K0 + r) by the printed group
    numbers. `elements` carry relative indices r and detected H/V bar-set centres (.h/.v
    with .x, .y, .w in image px). Candidates must differ from K0 by multiples of 12.
    Returns {"best": K0 or None, "scores": {K0: mean score}, "votes": n, ...}.
    """
    img = np.asarray(img, dtype=np.float64)

    def k_to_ge(k: int) -> tuple[int, int]:        # same index convention as usaf_reader
        return k // 6, k % 6 + 1

    pairs: dict[int, list] = {}
    for e in elements:
        if not e.detected or e.h is None or e.v is None:
            continue
        g, el = k_to_ge(K0 + e.r)
        pairs.setdefault(g - (g % 2), []).append((g, el, e))

    refs: dict[int, list[np.ndarray]] = {}
    windows = []                       # (pair g under K0, offset, window, layout-height samples)
    for g, items in sorted(pairs.items()):
        if len(items) < 2:
            continue
        centres, texts = _pair_layout(g)
        src, dst, ws = [], [], []
        for gg, el, e in items:
            (hx, hy), (vx, vy) = centres[(gg, el)]
            src += [(hx, hy), (vx, vy)]
            dst += [(e.h.x, e.h.y), (e.v.x, e.v.y)]
            ws.append(e.h.w)
        src, dst, ws = np.array(src), np.array(dst), np.repeat(ws, 2)
        if len(src) < 2 * NEAREST_ELEMENTS:
            continue
        for kind, val, t in texts:
            # the layout is exact only locally (tilt, distortion, small differences from the
            # real slide), so each number is mapped with an affine fit to its nearest bar sets
            width = gen.LABEL_WIDTH / gen.LABEL_HEIGHT * t.height * len(t.text)
            at = np.array([t.x + width / 2, t.y + t.height / 2])
            near = np.argsort(np.sum((src - at) ** 2, 1))[:2 * NEAREST_ELEMENTS]
            s_, d_ = src[near], dst[near]
            A = _fit_affine(s_, d_, np.ones(len(near)))
            err = np.sqrt(np.mean(np.sum((np.hstack([s_, np.ones((len(near), 1))]) @ A - d_) ** 2, 1)))
            if not np.isfinite(err) or err > MAX_FIT_ERR * float(np.median(ws[near])):
                continue
            scale = math.sqrt(abs(np.linalg.det(A[:2])))   # px per µm
            h = t.height
            if kind == "elem":
                if h * scale < MIN_REF_PX:
                    continue
                r = _reference(img, A, t, polarity)
                if r is not None:
                    refs.setdefault(val, []).append(r)
            else:
                if h * scale * min(SIZES) < MIN_GROUP_PX:
                    continue
                step = h / SAMPLES_PER_H
                win = _sample(img, A, t.x - 1.0 * h, t.x + width + 1.0 * h,
                              t.y - 1.0 * h, t.y + 2.2 * h, step)
                if win is not None:
                    windows.append((g, val, polarity * win))

    def digit_score(digit: int, win: np.ndarray) -> float | None:
        best = None
        for r in refs.get(digit, []):
            for s in SIZES:
                z = s * SAMPLES_PER_H / (r.shape[0] / 1.2)   # ref is ~1.2 digit heights tall
                tm = ndimage.zoom(r, z, order=1)
                v = _ncc_max(win, tm)
                best = v if best is None else max(best, v)
        return best

    # score of every readable group number under every hypothesis that predicts a digit 1-6
    readings = []
    for g, off, win in windows:
        per = {}
        for K in candidates:
            gK = g + off + (K - K0) // 6             # candidates differ by whole group pairs
            if 1 <= gK <= 6:
                v = digit_score(gK, win)
                if v is not None:
                    per[K] = v
        if len(per) >= 2:
            readings.append({"label": g + off, "scores": per})

    # a printed number votes only when its best match is good and clearly ahead; it then also
    # rules out every hypothesis it was compared with. A hypothesis wins with at least
    # MIN_VOTES votes, none against it, and every other hypothesis ruled out at least once.
    votes = []
    for r in readings:
        order = sorted(r["scores"], key=r["scores"].get, reverse=True)
        top, second = r["scores"][order[0]], r["scores"][order[1]]
        r["vote"] = None
        if top >= MIN_SCORE and top - second >= MIN_LEAD:
            r["vote"] = order[0]
            votes.append((order[0], set(order[1:])))
    best = None
    for c in candidates:
        mine = [lost for win, lost in votes if win == c]
        against = [win for win, _ in votes if win != c]
        ruled_out = set().union(*mine) if mine else set()
        if len(mine) >= MIN_VOTES and not against and ruled_out >= set(candidates) - {c}:
            best = c
    out_read = [{"group_under_K0": r["label"],
                 "scores": {f"{(K - K0) // 6:+d} groups": round(v, 3) for K, v in r["scores"].items()},
                 "vote": None if r["vote"] is None else f"{(r['vote'] - K0) // 6:+d} groups"}
                for r in readings]
    return {"best": best, "readable": len(readings),
            "votes": {f"{(K - K0) // 6:+d} groups": sum(1 for w, _ in votes if w == K) for K in candidates},
            "references": {str(k): len(v) for k, v in sorted(refs.items())}, "readings": out_read}

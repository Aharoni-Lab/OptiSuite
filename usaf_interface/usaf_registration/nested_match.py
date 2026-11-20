"""
Nested (recursive) matching: places every glyph's scanline by carrying the hand-annotated
template boxes (nested_templates.json, template pixels) onto the photo with SIFT
homographies. Experiments, reports and notes behind it are on branch emz95-experiments
(lab_images_report/NOTES.md).

Templates by nested count: each layer's template holds exactly the levels still left
  3 left -> config 3 (full target, groups 2-7)
  2 left -> config 4 (groups 4-7) or config 17 (6-9)
  1 left -> config 14 (one level) or config 16 (8-9)
The pattern repeats every 2 groups at 1/4 scale, so a template stands in for other groups
with its labels shifted by an even number ("4@-2" = config 4 used as groups 2-5).

Layer 1: whole-photo SIFT, photo resized to template density by the big square. A match
~0.25x the expected size locked onto the inner copy -> moved out one level.
Deeper layers (NESTED_MATCH):
  "own_template": the layer's own template, shrunk to the layer-above template's scale,
                  matched in a cutout around where the layer above puts it
  "parent_crop":  the layer-above template's region of these groups, same cutout
Same settings for both: ratio 0.8, RANSAC 6 px, >= 6 inliers, boxes not broken, size within
3x of the prediction. If a layer fails, it and every deeper layer use the last good match's
boxes and nothing deeper is matched.
"""
import json
from pathlib import Path

import cv2
import numpy as np

_DIR = Path(__file__).resolve().parent
_TEMPLATE_DATA = json.loads((_DIR / "nested_templates.json").read_text())["templates"]   # keyed by template id
LEVELS = {int(c): t["levels"] for c, t in _TEMPLATE_DATA.items()}
FIRST_GROUP = {int(c): t["first_group"] for c, t in _TEMPLATE_DATA.items()}
PREF = [3, 4, 14, 17, 16]          # real renders before the synthetic 6-9 ones

CUTOUT_MARGIN = 0.30               # cutout around the predicted block, each side
TEMPLATE_MARGIN = 0.15             # "parent_crop" template region around the block, each side
MIN_INLIERS = 6
SIZE_GATE = 3.0
MAX_DIM = 7000                     # cap on the resized photo's longer side (px)

_CACHE = {"img": {}, "kd": {}, "tmap": {}, "inner": {}}
_SIFT = []


def _sift():
    if not _SIFT:
        _SIFT.append(cv2.SIFT_create())
    return _SIFT[0]


# ---------------------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------------------
def _base(key):
    return int(str(key).split("@")[0])


def _offset(key):
    s = str(key).split("@")
    return int(s[1]) if len(s) > 1 else 0


def nested_template_for(g, levels_left):
    """Template key holding exactly `levels_left` group pairs starting at group g."""
    cands = [c for c in PREF if LEVELS[c] == levels_left]
    native = [c for c in cands if FIRST_GROUP[c] == g]
    c = native[0] if native else cands[0]
    off = g - FIRST_GROUP[c]
    return c if off == 0 else f"{c}@{off:+d}"


def _template_image(self, cfg, flip):
    k = (cfg, flip)
    if k not in _CACHE["img"]:
        path = str(_DIR / "templates" / _TEMPLATE_DATA[str(cfg)]["image"])
        im = cv2.imread(path, 0)
        if im is None:
            raise FileNotFoundError(f"nested_match: cannot read template {path}")
        _CACHE["img"][k] = cv2.flip(im, 1) if flip else im
    return _CACHE["img"][k]


def _boxes(key, flip, g0=None):
    """[{label, quad(4x2), scan(2x2), dir}] in template px; g0 -> only groups g0, g0+1."""
    t = _TEMPLATE_DATA[str(_base(key))]
    off, w = _offset(key), t["width"]
    out = []
    for b in t["boxes"]:
        g, e = b["label"][0] + off, b["label"][1]
        if g0 is not None and g not in (g0, g0 + 1):
            continue
        q, s = np.array(b["quad"], float), np.array(b["scan"], float)
        if flip:
            q[:, 0] = w - 1 - q[:, 0]; q = q[[1, 0, 3, 2]]
            s[:, 0] = w - 1 - s[:, 0]
        d = "vertical" if abs(s[1, 1] - s[0, 1]) > abs(s[1, 0] - s[0, 0]) else "horizontal"
        out.append(dict(label=(g, e), quad=q, scan=s, dir=d))
    return out


def _square(key, flip):
    t = _TEMPLATE_DATA[str(_base(key))]
    cx, cy, side = t["square"]
    if flip:
        cx = t["width"] - 1 - cx
    return np.array([cx, cy]), side


def _corners(bx):
    return np.vstack([b["quad"] for b in bx])


def _tmap(a, b, flip):
    """Homography template a px -> template b px, fitted on the boxes both have."""
    if a == b:
        return np.eye(3)
    k = (a, b, flip)
    if k not in _CACHE["tmap"]:
        A = {(x["label"], x["dir"]): x["quad"] for x in _boxes(a, flip)}
        B = {(x["label"], x["dir"]): x["quad"] for x in _boxes(b, flip)}
        common = sorted(set(A) & set(B))
        if not common:
            raise ValueError(f"nested_match: templates {a} and {b} share no boxes")
        H, _ = cv2.findHomography(np.vstack([A[c] for c in common]).astype(np.float32),
                                  np.vstack([B[c] for c in common]).astype(np.float32), 0)
        _CACHE["tmap"][k] = H
    return _CACHE["tmap"][k]


def _inner_copy(key, flip):
    """Template px map: outer pair of groups -> the 4x-smaller inner pair (same pixels whatever the labels)."""
    cfg = _base(key)
    k = (cfg, flip)
    if k not in _CACHE["inner"]:
        src = {14: 3, 16: 17}.get(cfg, cfg)
        bx = _boxes(src, flip)
        g0 = min(b["label"][0] for b in bx)
        outer = {((b["label"][0] + 2, b["label"][1]), b["dir"]): b["quad"] for b in bx if b["label"][0] in (g0, g0 + 1)}
        inner = {(b["label"], b["dir"]): b["quad"] for b in bx if b["label"][0] in (g0 + 2, g0 + 3)}
        common = sorted(set(outer) & set(inner))
        S, _ = cv2.estimateAffinePartial2D(np.vstack([outer[c] for c in common]).astype(np.float32),
                                           np.vstack([inner[c] for c in common]).astype(np.float32), method=cv2.LMEDS)
        T = np.vstack([S, [0, 0, 1]])
        if src != cfg:
            T = _tmap(src, cfg, flip) @ T @ _tmap(cfg, src, flip)
        _CACHE["inner"][k] = T
    return _CACHE["inner"][k]


def _apply(H, pts):
    pts = np.asarray(pts, float).reshape(-1, 2)
    q = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    return q[:, :2] / q[:, 2:3]


def _local_scale(H, p):
    p = np.asarray(p, float)
    a = _apply(H, [p, p + [1.0, 0], p + [0, 1.0]])
    return float(np.mean([np.linalg.norm(a[1] - a[0]), np.linalg.norm(a[2] - a[0])]))


def _kd(self, key, flip, region=None, scale=1.0):
    cfg = _base(key)
    k = (cfg, flip, region, round(scale, 4))
    if k not in _CACHE["kd"]:
        im = _template_image(self, cfg, flip)
        if region is not None:
            x0, y0, x1, y1 = region
            im = im[y0:y1, x0:x1]
        if abs(scale - 1) > 1e-3:
            im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        _CACHE["kd"][k] = _sift().detectAndCompute(im, None)
    return _CACHE["kd"][k]


def _ratio_matches(d1, d2, ratio):
    """Lowe ratio test, then one-to-one (each photo keypoint keeps its best template match)."""
    if d1 is None or d2 is None or len(d1) < 2 or len(d2) < 2:
        return []
    good = [m for pair in cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2) if len(pair) == 2
            for m, n in [pair] if m.distance < ratio * n.distance]
    best = {}
    for m in good:
        if m.trainIdx not in best or m.distance < best[m.trainIdx].distance:
            best[m.trainIdx] = m
    return list(best.values())


def _fit(kp1, d1, tgt, ratio, tol, min_inl):
    kp2, d2 = _sift().detectAndCompute(tgt, None)
    good = _ratio_matches(d1, d2, ratio)
    if len(good) < 4:
        return None, 0, len(good)
    src = np.float32([kp1[g.queryIdx].pt for g in good])
    dst = np.float32([kp2[g.trainIdx].pt for g in good])
    cv2.setRNGSeed(42)
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, tol)
    n = int(inl.sum()) if inl is not None else 0
    if H is None or n < min_inl:
        return None, n, len(good)
    return H, n, len(good)


def _quads_sane(H, bx):
    """Rejects collapsed or exploded fits for one nested level's glyph boxes: any box not
    finite, the boxes together spanning less than 20 px wide or tall, or one box more than
    6x the median box size."""
    quads = [_apply(H, b["quad"]) for b in bx]
    if not all(np.all(np.isfinite(q)) for q in quads):
        return False
    diags = np.array([np.linalg.norm(q.max(0) - q.min(0)) for q in quads])
    ext = np.ptp(np.vstack(quads), 0)
    if ext.min() < 20:
        return False
    med = np.median(diags)
    return not (med > 0 and diags.max() > 6 * med)


# ---------------------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------------------
def _layer_one(self, gray, flip, key, g0):
    """Whole-photo SIFT for the biggest layer. Returns (H: template px -> photo px, inliers, note).
    Successful matches are kept per (template image, flip) for the current photo
    (self._layer_one_cache, reset by nested_scanline_contrast_scores): a label shift ("4@-2")
    doesn't change the match, so later steps that use the same template image share it."""
    cache = getattr(self, "_layer_one_cache", None)
    ck = (_base(key), bool(flip), gray.shape)
    if cache is not None and ck in cache:
        return cache[ck]
    out = _layer_one_match(self, gray, flip, key, g0)
    if cache is not None:
        cache[ck] = out
    return out


def _layer_one_match(self, gray, flip, key, g0):
    sq = self.C.valid_squares[0] if len(self.C.valid_squares) else self.make_dummy_valid_square(gray)
    s = sq.reshape(-1, 2).astype(float)
    p_sq, p_side = s.mean(0), float(np.mean([np.linalg.norm(s[i] - s[(i + 1) % 4]) for i in range(4)]))
    t_sq, t_side = _square(key, flip)
    sc = min(t_side / p_side, MAX_DIM / max(gray.shape))
    kp1, d1 = _kd(self, key, flip)
    for _ in range(3):   # too many photo keypoints overflows OpenCV's matcher -> retry smaller
        tgt = cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_LANCZOS4 if sc > 1 else cv2.INTER_AREA)
        try:
            H, n, ng = _fit(kp1, d1, tgt, 0.75, 5.0, 8)
            break
        except cv2.error:
            sc *= 0.6
    else:
        raise ValueError("SIFT matcher overflow")
    if H is None:
        raise ValueError(f"template {key}: {n} inliers / {ng} matches")
    H = np.diag([1 / sc, 1 / sc, 1]) @ H
    if not _quads_sane(H, _boxes(key, flip, g0)):
        raise ValueError(f"template {key}: boxes broken")
    ratio = _local_scale(H, t_sq) / (p_side / t_side)
    note = ""
    if 0.18 <= ratio <= 0.35:       # matched the 4x-smaller inner copy -> move out one level
        H2 = H @ np.linalg.inv(_inner_copy(key, flip))
        r2 = _local_scale(H2, t_sq) / (p_side / t_side)
        off = np.linalg.norm(_apply(H2, t_sq)[0] - p_sq) / p_side
        if not (0.6 <= r2 <= 1.6 and off < 0.5):
            raise ValueError(f"template {key}: matched inner copy, re-anchor didn't line up")
        H, note = H2, f", re-anchored one level out (was {ratio:.2f}x)"
    return H, n, note


def _deeper(self, gray, H_out, key_out, key_in, g_in, g_out, flip, own_template):
    """Match one deeper layer. Returns (H: key_in px -> photo px or None, info, why-not)."""
    info = {"template": str(key_in)}
    h, w = gray.shape
    bx_in = _boxes(key_in, flip, g_in)
    tc = _corners(bx_in)
    H_pred = H_out @ _tmap(key_in, key_out, flip)
    proj = _apply(H_pred, tc)
    if not np.all(np.isfinite(proj)):
        return None, info, "layer above not finite"
    lo, hi = proj.min(0), proj.max(0)
    m = CUTOUT_MARGIN * (hi - lo)
    x0, y0 = np.maximum((lo - m).astype(int), 0)
    x1, y1 = np.minimum((hi + m).astype(int), [w, h])
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None, info, "cutout empty / off image"
    cut = gray[y0:y1, x0:x1]
    if own_template:
        # shrink the template (not blow up the photo) to the layer-above template's scale
        k = min(1.0, _local_scale(_tmap(key_in, key_out, flip), tc.mean(0)))
        s = min(k / _local_scale(H_pred, tc.mean(0)), MAX_DIM / max(cut.shape))
        kp1, d1 = _kd(self, key_in, flip, scale=k)
        post = np.diag([k, k, 1])
    else:
        s = min(1.0 / _local_scale(H_pred, tc.mean(0)), MAX_DIM / max(cut.shape))
        th, tw = _template_image(self, _base(key_in), flip).shape
        tlo, thi = tc.min(0), tc.max(0)
        tm = TEMPLATE_MARGIN * (thi - tlo)
        region = (int(max(tlo[0] - tm[0], 0)), int(max(tlo[1] - tm[1], 0)),
                  int(min(thi[0] + tm[0], tw)), int(min(thi[1] + tm[1], th)))
        kp1, d1 = _kd(self, key_in, flip, region=region)
        post = np.array([[1, 0, -region[0]], [0, 1, -region[1]], [0, 0, 1]], float)
    tgt = cv2.resize(cut, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA) if abs(s - 1) > 1e-3 else cut
    H, n, ng = _fit(kp1, d1, tgt, 0.8, 6.0, 1)
    info.update(cutout=[int(x0), int(y0), int(x1), int(y1)], inliers=n, matches=ng)
    if H is None:
        return None, info, f"no fit ({ng} matches)" if ng < 4 else f"too few inliers ({n})"
    H = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], float) @ np.diag([1 / s, 1 / s, 1]) @ H @ post
    if n < MIN_INLIERS:
        return H, info, f"too few inliers ({n})"
    if not _quads_sane(H, bx_in):
        return H, info, "boxes broken"
    bx_out = _boxes(key_out, flip, g_out)
    if _quads_sane(H_out, bx_out):
        r = np.linalg.norm(np.ptp(_apply(H, tc), 0)) / np.linalg.norm(np.ptp(proj, 0))
        info["size_vs_prediction"] = round(float(r), 2)
        if not (np.isfinite(r) and 1 / SIZE_GATE <= r <= SIZE_GATE):
            return H, info, f"implausible size ({r:.2f}x)"
    else:
        bo = _boxes(key_in, flip, g_out)
        if bo:
            po = _apply(H, _corners(bo))
            inside = (po[:, 0].min() >= -0.05 * w and po[:, 1].min() >= -0.05 * h
                      and po[:, 0].max() <= 1.05 * w and po[:, 1].max() <= 1.05 * h)
            if not (inside and _quads_sane(H, bo)):
                return H, info, "matched the outer copy of the pattern"
    return H, info, None


def nested_match_layers(self, gray, flip, g0, nested, method="own_template"):
    """[{group, H, template, fallback, desc, info}] one per nested level, biggest first.
    method: "own_template" or "parent_crop" (see the module docstring)."""
    if method not in ("own_template", "parent_crop"):
        raise ValueError(f"nested_match: unknown NESTED_MATCH {method!r} (own_template / parent_crop)")
    spec = [(g0 + 2 * i, nested_template_for(g0 + 2 * i, nested - i)) for i in range(nested)]
    H, n, note = _layer_one(self, gray, flip, spec[0][1], spec[0][0])
    layers = [dict(group=spec[0][0], H=H, template=spec[0][1], fallback=False,
                   desc=f"SIFT template {spec[0][1]} ({n} inliers{note})", info={"inliers": n})]
    stopped = None
    for i in range(1, len(spec)):
        g_in, key_in = spec[i]
        up = layers[-1]
        if stopped:
            layers.append(dict(group=g_in, H=up["H"], template=up["template"], fallback=True, info={},
                               desc=f"not matched (stopped after groups {stopped} fell back); boxes from template {up['template']}"))
            continue
        own = method == "own_template"
        key = key_in if own else spec[i - 1][1]
        Hf, info, why = _deeper(self, gray, up["H"], up["template"], key, g_in, up["group"], flip, own_template=own)
        meth = f"SIFT template {key}" if own else f"parent crop of template {key}"
        if why is None:
            layers.append(dict(group=g_in, H=Hf, template=key, fallback=False, info=info, desc=f"{meth} ({info['inliers']} inliers)"))
        else:
            layers.append(dict(group=g_in, H=up["H"], template=up["template"], fallback=True, info=info,
                               desc=f"fallback, boxes from the match above ({meth}: {why})"))
            stopped = f"{g_in}-{g_in + 1}"
    return layers

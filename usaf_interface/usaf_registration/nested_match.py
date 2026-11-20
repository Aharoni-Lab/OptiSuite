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

"""
Report helpers for nested matching: the glyph boxes of a scored photo projected onto it, a
drawing of them, and a batch runner that writes one drawing per photo plus results.json.

    python -m usaf_interface.usaf_registration.nested_report <images or folders> [--out DIR]

Drawing colours: green = resolved, red = not resolved, yellow = the best element.
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import UsafRegistration
from . import nested_match as nm

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
RESOLVED, NOT_RESOLVED, BEST = (0, 200, 0), (0, 0, 255), (0, 255, 255)


def projected_glyphs(reg):
    """
    Every glyph box of the matched layers of the last photo reg scored, in photo px, with its
    checker result. [{group, element, dir, layer, template, fallback, quad (4x2), scan (2x2),
    resolved, score, minima}]; empty if the photo wasn't matched.
    """
    nr = reg.C.nested_result or {}
    checks = {(c["group"], c["element"], c["dir"]): c for c in (nr.get("checker") or {}).get("glyphs", [])}
    out = []
    for L in nr.get("layers", []):
        H, g0 = np.array(L["H"]), int(L["groups"].split("-")[0])
        for b in nm._boxes(L["template"], nr["flip"], g0):
            (g, e), c = b["label"], checks.get((*b["label"], b["dir"]))
            out.append(dict(group=g, element=e, dir=b["dir"], layer=L["groups"], template=L["template"],
                            fallback=L["fallback"], quad=nm._apply(H, b["quad"]).round(1).tolist(),
                            scan=nm._apply(H, b["scan"]).round(1).tolist(),
                            resolved=bool(c and c["resolved"]), score=c and c["score"], minima=c and c["minima"]))
    return out


def draw_glyphs(img, glyphs, best=None, title=None, labels=True, max_side=1600):
    """Glyph boxes and their scanlines drawn on a copy of img (colours in the module docstring),
    with an optional title bar, shrunk so the longer side is at most max_side."""
    vis = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    t = max(1, round(max(vis.shape[:2]) / 900))
    for gl in glyphs:
        is_best = best is not None and [gl["group"], gl["element"]] == list(best)
        color = BEST if is_best else RESOLVED if gl["resolved"] else NOT_RESOLVED
        q = np.round(gl["quad"]).astype(np.int32)
        cv2.polylines(vis, [q.reshape(-1, 1, 2)], True, color, (2 if is_best else 1) * t)
        a, b = np.round(gl["scan"]).astype(int)
        cv2.line(vis, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), color, t)
        if labels and gl["dir"] == "vertical":
            # label above the box, shrunk to the box width; skipped when too small to read
            text, width = f"{gl['group']}-{gl['element']}", float(np.ptp(q[:, 0]))
            scale = 0.4 * t
            tw = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, t)[0][0]
            scale *= min(1.0, width / max(tw, 1))
            if scale >= 0.3:
                x, y = q.min(0)
                cv2.putText(vis, text, (int(x), int(y) - 3 * t), cv2.FONT_HERSHEY_SIMPLEX, scale, color, t)
    if title:
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 34 * t), (0, 0, 0), -1)
        cv2.putText(vis, title, (8, 24 * t), cv2.FONT_HERSHEY_SIMPLEX, 0.7 * t, (255, 255, 255), 2 * t)
    s = min(1.0, max_side / max(vis.shape[:2]))
    return cv2.resize(vis, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else vis


def report_image(reg, path):
    """Score one photo with reg; returns (record, drawing). Photos that can't be scored still
    get a record (with error) and a drawing of whatever was matched."""
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"nested_report: cannot read {path}")
    reg.C.nested_result = None
    rec = dict(name=Path(path).name, path=str(path), best=None)
    t0 = time.time()
    try:
        best = reg.find_usaf_score(str(path))[0]
        rec["best"] = [int(best[0]), int(best[1])]
    except ValueError as e:
        rec["error"] = str(e)
    rec["seconds"] = round(time.time() - t0, 2)
    nr = reg.C.nested_result or {}
    rec.update(start_group=nr.get("first_group"), start_group_source=nr.get("first_group_source"),
               flipped=nr.get("flip"), pattern_count=int(reg.C.pattern_count),
               layers=[{k: v for k, v in L.items() if k != "H"} for L in nr.get("layers", [])])
    rec["glyphs"] = projected_glyphs(reg)
    if rec["best"]:
        result = f"best G{rec['best'][0]} E{rec['best'][1]}"
    else:
        result = "no result: " + rec["error"].removeprefix("nested_match: ").split(" (")[0][:40]
    title = f"{Path(path).stem[:24]}: {result}, start {rec['start_group']}, {rec['seconds']}s"
    return rec, draw_glyphs(img, rec["glyphs"], rec["best"], title)


def image_paths(args):
    """Image files from a list of files and folders (folders not searched recursively)."""
    out = []
    for a in map(Path, args):
        out += sorted(p for p in a.iterdir() if p.suffix.lower() in IMAGE_EXTS) if a.is_dir() else [a]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw the projected glyph boxes for each photo and save results.json.")
    ap.add_argument("images", nargs="+", help="image files or folders")
    ap.add_argument("--out", default="nested_report", help="output folder (default: ./nested_report)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    (out / "img").mkdir(parents=True, exist_ok=True)
    reg = UsafRegistration()
    results = []
    for p in image_paths(args.images):
        rec, vis = report_image(reg, p)
        stem = "".join(c if c.isalnum() else "_" for c in p.stem)[:80]
        rec["image"] = f"img/{stem}.jpg"
        cv2.imwrite(str(out / rec["image"]), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])
        results.append(rec)
        print(f"{rec['name'][:50]:50s} {rec['best'] or rec.get('error', '')[:60]}", flush=True)
    (out / "results.json").write_text(json.dumps(results, indent=1))
    print(f"{len(results)} photos -> {out}")


if __name__ == "__main__":
    main()

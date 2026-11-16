#!/usr/bin/env python3
"""
Generate an ideal (synthetic) 1951 USAF resolution target as a single image.

Geometry follows MIL-STD-150A:
    resolution (lp/mm) = 2 ** (group + (element - 1) / 6)
    line width         = 1 / (2 * resolution)            [mm]
    each element       = 3 horizontal + 3 vertical bars, bar length = 5 * line width

Groups are laid out in nested pairs like the physical slide: for each pair
(even g, odd g+1), group g element 1 sits at the top right, g elements 2-6 run
down the left column, group g+1 elements 1-6 run down the right column, and the
next (smaller) pair is nested in the centre.

Bars are rasterised with exact area coverage (analytic anti-aliasing), so the
image is a "perfect" sampled version of the slide at the chosen pixel size.

Alongside the image a JSON sidecar is written with, for every element, its
spatial frequency, line width in µm and px, and the pixel bounding boxes of
its horizontal-line and vertical-line bar sets (for frequency / contrast analysis).

Usage:
    python generate_usaf_target.py                       # groups 2-7, 0.5 µm/px
    python generate_usaf_target.py --groups 2 7 --pixel-size 0.25 --polarity bright-bars
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# USAF geometry
# ---------------------------------------------------------------------------

BAR_GAP_FACTOR = 2.0      # gap between horizontal and vertical bar sets, in line widths
LABEL_HEIGHT = 5.0        # element-number height, in line widths (= bar length)
LABEL_GAP = 1.5           # gap between element number and bars, in line widths
LABEL_WIDTH = 3.2         # approx. width of one digit, in line widths
ROW_GAP_FACTOR = 2.5      # vertical gap after each element, in line widths


def lp_per_mm(group: int, element: int) -> float:
    return 2.0 ** (group + (element - 1) / 6.0)


def line_width_um(group: int, element: int) -> float:
    return 1000.0 / (2.0 * lp_per_mm(group, element))


@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Text:
    text: str
    x: float       # left edge (µm)
    y: float       # top edge (µm)
    height: float  # cap height (µm)


@dataclass
class ElementRecord:
    group: int
    element: int
    h_lines: Rect   # three horizontal lines -> modulation along y
    v_lines: Rect   # three vertical lines   -> modulation along x


@dataclass
class Block:
    """A laid-out piece of the target in local µm coordinates (origin top-left)."""
    width: float
    height: float
    rects: list[Rect] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    elements: list[ElementRecord] = field(default_factory=list)

    def place(self, other: "Block", dx: float, dy: float) -> None:
        self.rects += [Rect(r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy) for r in other.rects]
        self.texts += [Text(t.text, t.x + dx, t.y + dy, t.height) for t in other.texts]
        for e in other.elements:
            self.elements.append(ElementRecord(
                e.group, e.element,
                Rect(e.h_lines.x0 + dx, e.h_lines.y0 + dy, e.h_lines.x1 + dx, e.h_lines.y1 + dy),
                Rect(e.v_lines.x0 + dx, e.v_lines.y0 + dy, e.v_lines.x1 + dx, e.v_lines.y1 + dy),
            ))


def element_block(group: int, element: int) -> Block:
    """Element number on the left, then horizontal-line set, then vertical-line set."""
    w = line_width_um(group, element)
    label_w = LABEL_WIDTH * w
    bx = label_w + LABEL_GAP * w            # x where bars start
    L = 5.0 * w                             # bar length
    b = Block(width=bx + 2 * L + BAR_GAP_FACTOR * w, height=L)

    b.texts.append(Text(str(element), 0.0, 0.0, LABEL_HEIGHT * w))

    # horizontal lines (run along x, stacked along y)
    for k in range(3):
        b.rects.append(Rect(bx, 2 * k * w, bx + L, 2 * k * w + w))
    h = Rect(bx, 0.0, bx + L, L)

    # vertical lines (run along y, stacked along x)
    vx = bx + L + BAR_GAP_FACTOR * w
    for k in range(3):
        b.rects.append(Rect(vx + 2 * k * w, 0.0, vx + 2 * k * w + w, L))
    v = Rect(vx, 0.0, vx + L, L)

    b.elements.append(ElementRecord(group, element, h, v))
    return b


def column(items: list[tuple]) -> Block:
    """Stack items top-down. Item = ('el', g, e) or ('label', g, height_um)."""
    blocks: list[tuple[Block, float]] = []
    for it in items:
        if it[0] == "el":
            _, g, e = it
            blocks.append((element_block(g, e), ROW_GAP_FACTOR * line_width_um(g, e)))
        else:
            _, g, hgt = it
            lb = Block(width=LABEL_WIDTH * hgt / LABEL_HEIGHT * len(str(g)), height=hgt)
            lb.texts.append(Text(str(g), 0.0, 0.0, hgt))
            blocks.append((lb, 0.6 * hgt))
    col = Block(width=max(bl.width for bl, _ in blocks), height=0.0)
    y = 0.0
    for i, (bl, gap) in enumerate(blocks):
        col.place(bl, 0.0, y)
        y += bl.height + (gap if i < len(blocks) - 1 else 0.0)
    col.height = y
    return col


def pair_block(g: int, has_odd: bool, inner: Block | None) -> Block:
    """Lay out group g (even slot) and optionally g+1 (odd slot) around `inner`."""
    label_h_left = 1.2 * LABEL_HEIGHT * line_width_um(g, 2)
    left = column([("label", g, label_h_left)] + [("el", g, e) for e in range(2, 7)])

    right_items: list[tuple] = [("el", g, 1)]
    if has_odd:
        label_h_right = 1.2 * LABEL_HEIGHT * line_width_um(g + 1, 1)
        right_items += [("label", g + 1, label_h_right)] + [("el", g + 1, e) for e in range(1, 7)]
    right = column(right_items)

    gc = 2.5 * line_width_um(g, 2)          # clearance around the nested pair
    inner_w = inner.width if inner else 0.0
    inner_h = inner.height if inner else 0.0
    centre_w = inner_w + 2 * gc if inner else gc

    blk = Block(width=left.width + centre_w + right.width,
                height=max(left.height, right.height, inner_h + 2 * gc))
    blk.place(left, 0.0, 0.0)
    blk.place(right, left.width + centre_w, 0.0)
    if inner:
        blk.place(inner, left.width + gc, (blk.height - inner_h) / 2.0)
    return blk


def build_target(g_min: int, g_max: int) -> Block:
    """Nested pairs: (g_min, g_min+1) outermost, smallest pair in the centre."""
    pairs = [(g, g + 1 <= g_max) for g in range(g_min, g_max + 1, 2)]
    inner: Block | None = None
    for g, has_odd in reversed(pairs):
        inner = pair_block(g, has_odd, inner)
    assert inner is not None
    return inner


# ---------------------------------------------------------------------------
# Rasterisation
# ---------------------------------------------------------------------------

def _coverage_1d(a: float, b: float, n0: int, n1: int) -> np.ndarray:
    """Fraction of each pixel [i, i+1) for i in [n0, n1) covered by interval [a, b)."""
    i = np.arange(n0, n1, dtype=np.float64)
    return np.clip(np.minimum(b, i + 1.0) - np.maximum(a, i), 0.0, 1.0)


def draw_rect(canvas: np.ndarray, r: Rect) -> None:
    """Exact area-coverage rasterisation of an axis-aligned rectangle (pixel units)."""
    H, W = canvas.shape
    c0, c1 = max(int(math.floor(r.x0)), 0), min(int(math.ceil(r.x1)), W)
    r0, r1 = max(int(math.floor(r.y0)), 0), min(int(math.ceil(r.y1)), H)
    if c1 <= c0 or r1 <= r0:
        return
    cov = np.outer(_coverage_1d(r.y0, r.y1, r0, r1), _coverage_1d(r.x0, r.x1, c0, c1))
    np.maximum(canvas[r0:r1, c0:c1], cov, out=canvas[r0:r1, c0:c1])


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def draw_text(canvas: np.ndarray, t: Text, ss: int = 8) -> None:
    """Render digits at `ss`x supersampling, box-filter down, and max-composite."""
    cap_px = t.height
    if cap_px < 3:          # too small to be meaningful; skip
        return
    ref = _load_font(200)
    l, top, r, bot = ref.getbbox("0")
    cap_ratio = (bot - top) / 200.0
    font = _load_font(max(4, int(round(cap_px * ss / cap_ratio))))
    l, top, r, bot = font.getbbox(t.text)
    w_ss, h_ss = r - l, bot - top
    pad = ss
    W_ss = int(math.ceil((w_ss + 2 * pad) / ss)) * ss
    H_ss = int(math.ceil((h_ss + 2 * pad) / ss)) * ss
    img = Image.new("L", (W_ss, H_ss), 0)
    ImageDraw.Draw(img).text((pad - l, pad - top), t.text, fill=255, font=font)
    patch = np.asarray(img.reduce(ss), dtype=np.float64) / 255.0

    x0 = int(round(t.x - pad / ss))
    y0 = int(round(t.y - pad / ss))
    H, W = canvas.shape
    ph, pw = patch.shape
    xa, ya = max(x0, 0), max(y0, 0)
    xb, yb = min(x0 + pw, W), min(y0 + ph, H)
    if xb <= xa or yb <= ya:
        return
    sub = patch[ya - y0:yb - y0, xa - x0:xb - x0]
    np.maximum(canvas[ya:yb, xa:xb], sub, out=canvas[ya:yb, xa:xb])


def render(block: Block, pixel_um: float, margin_um: float) -> tuple[np.ndarray, list[dict]]:
    s = 1.0 / pixel_um
    W = int(math.ceil((block.width + 2 * margin_um) * s))
    H = int(math.ceil((block.height + 2 * margin_um) * s))
    canvas = np.zeros((H, W), dtype=np.float64)   # 1.0 = chrome (bar), 0.0 = glass

    def px(r: Rect) -> Rect:
        return Rect((r.x0 + margin_um) * s, (r.y0 + margin_um) * s,
                    (r.x1 + margin_um) * s, (r.y1 + margin_um) * s)

    for r in block.rects:
        draw_rect(canvas, px(r))
    for t in block.texts:
        draw_text(canvas, Text(t.text, (t.x + margin_um) * s, (t.y + margin_um) * s, t.height * s))

    records = []
    for e in sorted(block.elements, key=lambda e: (e.group, e.element)):
        w_um = line_width_um(e.group, e.element)
        h, v = px(e.h_lines), px(e.v_lines)
        records.append({
            "group": e.group,
            "element": e.element,
            "lp_per_mm": round(lp_per_mm(e.group, e.element), 4),
            "line_width_um": round(w_um, 4),
            "line_width_px": round(w_um / pixel_um, 4),
            "period_px": round(2 * w_um / pixel_um, 4),
            "cycles_per_px": round(pixel_um / (2 * w_um), 5),
            "above_nyquist": bool(2 * w_um / pixel_um < 2.0),
            # bbox = [x0, y0, x1, y1] in pixel coordinates (float, origin top-left)
            "horizontal_lines_bbox_px": [round(h.x0, 3), round(h.y0, 3), round(h.x1, 3), round(h.y1, 3)],
            "vertical_lines_bbox_px": [round(v.x0, 3), round(v.y0, 3), round(v.x1, 3), round(v.y1, 3)],
        })
    return canvas, records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", nargs=2, type=int, default=[2, 7], metavar=("MIN", "MAX"))
    ap.add_argument("--pixel-size", type=float, default=0.5, help="object-space pixel size in µm (default 0.5)")
    ap.add_argument("--polarity", choices=["dark-bars", "bright-bars"], default="dark-bars",
                    help="dark-bars: chrome bars dark on bright glass (transmitted light, default)")
    ap.add_argument("--bit-depth", type=int, choices=[8, 16], default=16)
    ap.add_argument("--margin", type=float, default=None, help="border in µm (default: 4 line widths of the largest element)")
    ap.add_argument("--out", type=Path, default=None, help="output .png/.tif path")
    args = ap.parse_args()

    g_min, g_max = sorted(args.groups)
    margin = args.margin if args.margin is not None else 4 * line_width_um(g_min, 1)

    block = build_target(g_min, g_max)
    chrome, records = render(block, args.pixel_size, margin)

    img = 1.0 - chrome if args.polarity == "dark-bars" else chrome
    maxval = 65535 if args.bit_depth == 16 else 255
    arr = np.round(img * maxval).astype(np.uint16 if args.bit_depth == 16 else np.uint8)

    out = args.out or Path(__file__).parent / "output" / f"USAF1951_G{g_min}-G{g_max}_{args.pixel_size:g}um_px.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    dpi = 25400.0 / args.pixel_size
    Image.fromarray(arr).save(out, dpi=(dpi, dpi))

    meta = {
        "description": "Synthetic ideal 1951 USAF resolution target",
        "groups": [g_min, g_max],
        "pixel_size_um": args.pixel_size,
        "image_shape_hw": list(arr.shape),
        "field_of_view_um": [round(arr.shape[1] * args.pixel_size, 2), round(arr.shape[0] * args.pixel_size, 2)],
        "polarity": args.polarity,
        "bit_depth": args.bit_depth,
        "notes": ("horizontal_lines = 3 bars running along x (modulation along y); "
                  "vertical_lines = 3 bars running along y (modulation along x). "
                  "Bars are anti-aliased by exact pixel-area coverage."),
        "elements": records,
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))

    print(f"Saved {out}  ({arr.shape[1]} x {arr.shape[0]} px, "
          f"{arr.shape[1] * args.pixel_size / 1000:.2f} x {arr.shape[0] * args.pixel_size / 1000:.2f} mm)")
    finest = records[-1]
    print(f"Finest element G{finest['group']}E{finest['element']}: {finest['lp_per_mm']} lp/mm, "
          f"line width {finest['line_width_px']} px")
    if any(r["above_nyquist"] for r in records):
        print("WARNING: some elements exceed the Nyquist limit at this pixel size.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate an ideal (synthetic) 1951 USAF resolution target as a single image.

Geometry follows MIL-STD-150A:
    resolution (lp/mm) = 2 ** (group + (element - 1) / 6)
    line width         = 1 / (2 * resolution)            [mm]
    each element       = 3 horizontal + 3 vertical bars, bar length = 5 * line width

Layout matches the standard chrome slide. For each group pair (even g, odd g+1):

        g                [square]               g+1
    2 ═ |||                                  ||| ═ 1
    3 ═ |||          ( next pair )           ||| ═ 2
    4 ═ |||          ( nested in )           ||| ═ 3
    5 ═ |||          ( the centre)           ||| ═ 4
    6 ═ |||                                  ||| ═ 5
                                             ||| ═ 6
                                               g
                                       |||  ═  1

  * left column : group g elements 2-6   (number, horizontal lines, vertical lines)
  * right column: group g+1 elements 1-6 (vertical lines, horizontal lines, number)
  * bottom right: group g element 1, with its group number above it
  * top centre  : a solid reference square
  * centre      : the next (4x smaller) pair, recursively

Bars are rasterised with exact area coverage (analytic anti-aliasing), so the
image is a "perfect" sampled version of the slide at the chosen pixel size.
Default polarity is inverted: bright bars on a black background.

Alongside the image a JSON sidecar is written with, for every element, its
spatial frequency, line width in µm and px, and the pixel bounding boxes of its
horizontal-line and vertical-line bar sets, plus the reference squares
(for frequency / contrast analysis).

Usage:
    python generate_usaf_target.py                       # groups 2-7, 0.5 µm/px, bright bars
    python generate_usaf_target.py --groups 2 7 --pixel-size 0.25 --polarity dark-bars
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
# USAF geometry (all lengths in units of the element's own line width w)
# ---------------------------------------------------------------------------

BAR_GAP = 2.0          # gap between horizontal- and vertical-line sets
LABEL_HEIGHT = 5.0     # element-number cap height (= bar length)
LABEL_WIDTH = 3.4      # approx. width of one digit
LABEL_GAP = 1.5        # gap between element number and bars
ROW_GAP = 3.0          # vertical gap below each element in a column
GROUP_LABEL_SCALE = 1.2  # group number height relative to element-number height


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

    def shift(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)


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
    squares: list[tuple[int, Rect]] = field(default_factory=list)

    def place(self, other: "Block", dx: float, dy: float) -> None:
        self.rects += [r.shift(dx, dy) for r in other.rects]
        self.texts += [Text(t.text, t.x + dx, t.y + dy, t.height) for t in other.texts]
        self.elements += [ElementRecord(e.group, e.element, e.h_lines.shift(dx, dy), e.v_lines.shift(dx, dy))
                          for e in other.elements]
        self.squares += [(g, r.shift(dx, dy)) for g, r in other.squares]


def text_block(text: str, height: float) -> Block:
    b = Block(width=LABEL_WIDTH / LABEL_HEIGHT * height * len(text), height=height)
    b.texts.append(Text(text, 0.0, 0.0, height))
    return b


def element_block(group: int, element: int, mirrored: bool = False) -> Block:
    """
    Normal  : [number] [horizontal lines] [vertical lines]
    Mirrored: [vertical lines] [horizontal lines] [number]
    """
    w = line_width_um(group, element)
    L = 5.0 * w
    label_w = LABEL_WIDTH * w
    b = Block(width=label_w + LABEL_GAP * w + 2 * L + BAR_GAP * w, height=L)

    if mirrored:
        vx = 0.0
        hx = L + BAR_GAP * w
        tx = hx + L + LABEL_GAP * w
    else:
        tx = 0.0
        hx = label_w + LABEL_GAP * w
        vx = hx + L + BAR_GAP * w

    b.texts.append(Text(str(element), tx, 0.0, LABEL_HEIGHT * w))
    for k in range(3):
        b.rects.append(Rect(hx, 2 * k * w, hx + L, 2 * k * w + w))          # horizontal lines
        b.rects.append(Rect(vx + 2 * k * w, 0.0, vx + 2 * k * w + w, L))    # vertical lines
    b.elements.append(ElementRecord(group, element, Rect(hx, 0.0, hx + L, L), Rect(vx, 0.0, vx + L, L)))
    return b


def element_column(group: int, elements: range, mirrored: bool) -> Block:
    """Stack elements top-down; normal columns are left-aligned, mirrored ones right-aligned."""
    blocks = [element_block(group, e, mirrored) for e in elements]
    col = Block(width=max(b.width for b in blocks), height=0.0)
    y = 0.0
    for i, (e, b) in enumerate(zip(elements, blocks)):
        col.place(b, col.width - b.width if mirrored else 0.0, y)
        y += b.height + (ROW_GAP * line_width_um(group, e) if i < len(blocks) - 1 else 0.0)
    col.height = y
    return col


def stack_label_over(label: Block, body: Block, gap: float, align: str) -> Block:
    """Put `label` above `body`, horizontally centred or right-aligned."""
    out = Block(width=max(label.width, body.width), height=label.height + gap + body.height)
    bx = (out.width - body.width) if align == "right" else (out.width - body.width) / 2
    lx = (out.width - label.width) if align == "right" else (out.width - label.width) / 2
    out.place(label, lx, 0.0)
    out.place(body, bx, label.height + gap)
    return out


def pair_block(g: int, has_odd: bool, inner: Block | None) -> Block:
    """Lay out group g and (optionally) g+1 around the nested `inner` pair."""
    wg1 = line_width_um(g, 1)
    wg2 = line_width_um(g, 2)

    # left column: group number g over elements 2..6
    lbl_g = text_block(str(g), GROUP_LABEL_SCALE * LABEL_HEIGHT * wg2)
    left = stack_label_over(lbl_g, element_column(g, range(2, 7), mirrored=False), 2.0 * wg2, "centre")

    # right column: group number g+1 over elements 1..6 (mirrored)
    if has_odd:
        wo1 = line_width_um(g + 1, 1)
        lbl_o = text_block(str(g + 1), GROUP_LABEL_SCALE * LABEL_HEIGHT * wg2)
        right = stack_label_over(lbl_o, element_column(g + 1, range(1, 7), mirrored=True), 2.0 * wg2, "centre")
    else:
        right = Block(width=0.0, height=lbl_g.height)

    # bottom right: group g element 1 (mirrored) with group number g above it, right-aligned
    corner = stack_label_over(text_block(str(g), GROUP_LABEL_SCALE * LABEL_HEIGHT * wg1 * 0.8),
                              element_block(g, 1, mirrored=True), 1.0 * wg1, "right")

    # reference square at top centre, top-aligned with the first element row
    sq = 5.0 * wg2
    gc = 3.0 * wg2                      # clearance around centre content
    inner_w = inner.width if inner else 0.0
    inner_h = inner.height if inner else 0.0
    centre_w = max(sq, inner_w) + 2 * gc

    width = left.width + centre_w + right.width
    sq_top = lbl_g.height + 2.0 * wg2
    # height: tallest of left column, right column + corner element, square + inner + corner
    corner_top_min = max(right.height + gc, sq_top + sq + gc + inner_h + gc)
    height = max(left.height, corner_top_min + corner.height)

    blk = Block(width=width, height=height)
    blk.place(left, 0.0, 0.0)
    blk.place(right, width - right.width, 0.0)
    corner_y = height - corner.height
    blk.place(corner, width - corner.width, corner_y)

    cx0 = left.width                     # centre region spans [cx0, cx0 + centre_w]
    sq_x = cx0 + (centre_w - sq) / 2
    blk.rects.append(Rect(sq_x, sq_top, sq_x + sq, sq_top + sq))
    blk.squares.append((g, Rect(sq_x, sq_top, sq_x + sq, sq_top + sq)))

    if inner:
        # centre the nested pair in the gap between the square and the corner element
        y_lo, y_hi = sq_top + sq + gc, corner_y - gc
        blk.place(inner, cx0 + (centre_w - inner_w) / 2, y_lo + (y_hi - y_lo - inner_h) / 2)
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
    for path, index in (("/System/Library/Fonts/Helvetica.ttc", 1),          # Helvetica Bold
                        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
                        ("DejaVuSans-Bold.ttf", 0), ("arialbd.ttf", 0)):
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default(size)


def draw_text(canvas: np.ndarray, t: Text, ss: int = 8) -> None:
    """Render digits at `ss`x supersampling, box-filter down, and max-composite."""
    cap_px = t.height
    if cap_px < 3:          # too small to be meaningful; skip
        return
    ref = _load_font(200)
    _, top, _, bot = ref.getbbox("0")
    cap_ratio = (bot - top) / 200.0
    font = _load_font(max(4, int(round(cap_px * ss / cap_ratio))))
    l, top, r, bot = font.getbbox(t.text)
    pad = ss
    W_ss = int(math.ceil((r - l + 2 * pad) / ss)) * ss
    H_ss = int(math.ceil((bot - top + 2 * pad) / ss)) * ss
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


def _bbox(r: Rect) -> list[float]:
    return [round(r.x0, 3), round(r.y0, 3), round(r.x1, 3), round(r.y1, 3)]


def render(block: Block, pixel_um: float, margin_um: float) -> tuple[np.ndarray, dict]:
    s = 1.0 / pixel_um
    W = int(math.ceil((block.width + 2 * margin_um) * s))
    H = int(math.ceil((block.height + 2 * margin_um) * s))
    canvas = np.zeros((H, W), dtype=np.float64)   # 1.0 = chrome (pattern), 0.0 = background

    def px(r: Rect) -> Rect:
        return Rect((r.x0 + margin_um) * s, (r.y0 + margin_um) * s,
                    (r.x1 + margin_um) * s, (r.y1 + margin_um) * s)

    for r in block.rects:
        draw_rect(canvas, px(r))
    for t in block.texts:
        draw_text(canvas, Text(t.text, (t.x + margin_um) * s, (t.y + margin_um) * s, t.height * s))

    elements = []
    for e in sorted(block.elements, key=lambda e: (e.group, e.element)):
        w_um = line_width_um(e.group, e.element)
        elements.append({
            "group": e.group,
            "element": e.element,
            "lp_per_mm": round(lp_per_mm(e.group, e.element), 4),
            "line_width_um": round(w_um, 4),
            "line_width_px": round(w_um / pixel_um, 4),
            "period_px": round(2 * w_um / pixel_um, 4),
            "cycles_per_px": round(pixel_um / (2 * w_um), 5),
            "above_nyquist": bool(2 * w_um / pixel_um < 2.0),
            # bbox = [x0, y0, x1, y1] in pixel coordinates (float, origin top-left)
            "horizontal_lines_bbox_px": _bbox(px(e.h_lines)),
            "vertical_lines_bbox_px": _bbox(px(e.v_lines)),
        })
    squares = [{"pair_group": g, "bbox_px": _bbox(px(r))} for g, r in sorted(block.squares)]
    return canvas, {"elements": elements, "reference_squares": squares}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", nargs=2, type=int, default=[2, 7], metavar=("MIN", "MAX"))
    ap.add_argument("--pixel-size", type=float, default=0.5, help="object-space pixel size in µm (default 0.5)")
    ap.add_argument("--polarity", choices=["bright-bars", "dark-bars"], default="bright-bars",
                    help="bright-bars: white pattern on black (default, inverted); "
                         "dark-bars: black pattern on white")
    ap.add_argument("--bit-depth", type=int, choices=[8, 16], default=16)
    ap.add_argument("--margin", type=float, default=None,
                    help="border in µm (default: 4 line widths of the largest element)")
    ap.add_argument("--out", type=Path, default=None, help="output .png/.tif path")
    args = ap.parse_args()

    g_min, g_max = sorted(args.groups)
    margin = args.margin if args.margin is not None else 4 * line_width_um(g_min, 1)

    block = build_target(g_min, g_max)
    chrome, records = render(block, args.pixel_size, margin)

    img = chrome if args.polarity == "bright-bars" else 1.0 - chrome
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
                  "Pattern is anti-aliased by exact pixel-area coverage."),
        **records,
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))

    print(f"Saved {out}  ({arr.shape[1]} x {arr.shape[0]} px, "
          f"{arr.shape[1] * args.pixel_size / 1000:.2f} x {arr.shape[0] * args.pixel_size / 1000:.2f} mm)")
    finest = records["elements"][-1]
    print(f"Finest element G{finest['group']}E{finest['element']}: {finest['lp_per_mm']} lp/mm, "
          f"line width {finest['line_width_px']} px")
    if any(r["above_nyquist"] for r in records["elements"]):
        print("WARNING: some elements exceed the Nyquist limit at this pixel size.")


if __name__ == "__main__":
    main()

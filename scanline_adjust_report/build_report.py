import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
results = json.loads((OUT_DIR / "results.json").read_text())

TAG_LABELS = {
    "keystoning": "keystoning", "rotated": "rotated", "blurry": "blurry",
    "obscured": "obscured", "flipped": "flipped", "added-background": "added background",
    "addedbackground": "added background", "edmund-optics-site": "external source",
    "group4": "group 4 content",
}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tags_html(tags):
    if not tags:
        return '<span class="meta">no tags</span>'
    return "".join(f'<span class="tag">{esc(TAG_LABELS.get(t, t))}</span>' for t in tags)


def sort_key(r):
    if not r.get("sift_file"):
        return (0, 0)
    return (1, -(r.get("sift_avg_move_px") or 0))


rows_sorted = sorted(results, key=sort_key)

n = len(results)
n_ok = sum(1 for r in results if r.get("sift_file"))
n_both = sum(1 for r in results if r.get("sift_file") and r.get("elastix_file"))

import statistics
sift_moves = [r["sift_avg_move_px"] for r in results if r.get("sift_avg_move_px") is not None]
elastix_moves = [r["elastix_avg_move_px"] for r in results if r.get("elastix_avg_move_px") is not None]

sections = []
for i, r in enumerate(rows_sorted):
    name = r.get("original_name", str(r.get("image_id")))
    header = f"""
    <div class="imghead">
      <h3>{i+1}. {esc(name)}</h3>
      <div class="tags">{tags_html(r.get('user_tags'))}</div>
      <table class="imgstats">
        <tr>
          <td>SIFT: avg move <b>{r.get('sift_avg_move_px','-')}px</b> (max {r.get('sift_max_move_px','-')}px)</td>
          <td>SIFT+elastix: avg move <b>{r.get('elastix_avg_move_px','-')}px</b> (max {r.get('elastix_max_move_px','-')}px)</td>
        </tr>
      </table>
    </div>"""

    if r.get("sift_file"):
        panels = f"""
    <div class="panels">
      <div class="panelbox">
        <div class="panelcap">SIFT: unadjusted (red) vs adjusted (green)</div>
        <img class="panelimg" src="{r['sift_file']}" loading="lazy">
      </div>"""
        if r.get("elastix_file"):
            panels += f"""
      <div class="panelbox">
        <div class="panelcap">SIFT+elastix: unadjusted (red) vs adjusted (green)</div>
        <img class="panelimg" src="{r['elastix_file']}" loading="lazy">
      </div>"""
        else:
            panels += f"""
      <div class="panelbox">
        <div class="panelcap">SIFT+elastix</div>
        <div class="meta">elastix failed: {esc(r.get('elastix_error',''))}</div>
      </div>"""
        panels += "\n    </div>"
    else:
        panels = f'<div class="failbox">FAILED &mdash; {esc(r.get("error") or "unknown")}</div>'

    sections.append(f'<section class="imgsection">{header}{panels}</section>')

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Scanline adjustment: on vs off, SIFT and SIFT+elastix</title>
<style>
  body {{
    font-family: Georgia, "Times New Roman", serif; font-size: 14px; color: #1a1a1a;
    background: #ffffff; max-width: 1150px; margin: 0 auto; padding: 24px 20px 80px; line-height: 1.5;
  }}
  h1 {{ font-size: 20px; font-weight: normal; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; }}
  .subtitle {{ color: #555; font-size: 13px; margin-bottom: 20px; font-family: "Courier New", monospace; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: 0.03em; color: #333; margin-top: 28px; }}
  table.stats {{ border-collapse: collapse; margin-bottom: 8px; font-family: "Courier New", monospace; font-size: 13px; }}
  table.stats td {{ padding: 3px 14px 3px 0; }}
  table.stats td.label {{ color: #555; }}
  table.stats td.val {{ font-weight: bold; text-align: right; }}
  .imgsection {{ border-top: 1px solid #ccc; padding-top: 18px; margin-top: 22px; }}
  .imghead h3 {{ font-size: 15px; margin: 0 0 6px; font-family: "Courier New", monospace; word-break: break-all; }}
  .tags {{ margin-bottom: 8px; }}
  .tag {{
    display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
    background: #eee; color: #444; border: 1px solid #ccc; border-radius: 3px; padding: 2px 7px; margin-right: 5px;
  }}
  .meta {{ color: #999; font-size: 12px; }}
  table.imgstats {{ font-size: 12px; color: #444; font-family: "Courier New", monospace; margin-bottom: 10px; }}
  table.imgstats td {{ padding-right: 24px; }}
  .panels {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .panelbox {{ flex: 1 1 480px; border: 1px solid #ccc; padding: 8px; }}
  .panelcap {{ font-size: 11px; color: #666; text-transform: uppercase; margin-bottom: 4px; }}
  .panelimg {{ width: 100%; display: block; }}
  .failbox {{ border: 1px solid #c62828; background: #fdf1f1; padding: 10px 12px; font-size: 13px; color: #c62828; font-family: "Courier New", monospace; }}
  footer {{ margin-top: 40px; font-size: 11px; color: #999; border-top: 1px solid #ddd; padding-top: 10px; }}
</style>
</head>
<body>

<h1>Scanline adjustment: on vs. off, for SIFT and SIFT+elastix</h1>
<div class="subtitle">dataset: usaf test images.v1i.coco &middot; n={n}</div>
<p style="font-size:13px;color:#444;max-width:900px;">
Thick red = unadjusted scanline (raw registration output). Thick green = after
apply_point_adjustment_algorithm, which shrinks the scanline inward until both endpoints
land on bright pixels (up to 80% of its original length). Shown for both SIFT-only and
SIFT+elastix projection, so the adjustment's effect is visible on top of each registration
method separately. <b>AUTO_ADJUST defaults to False in production</b> -- this is forced on
here specifically to visualize what it would do, not what runs by default.
</p>

<h2>Summary</h2>
<table class="stats">
  <tr><td class="label">Total images</td><td class="val">{n}</td></tr>
  <tr><td class="label">SIFT succeeded</td><td class="val">{n_ok} / {n}</td></tr>
  <tr><td class="label">Both SIFT and SIFT+elastix succeeded</td><td class="val">{n_both} / {n}</td></tr>
  <tr><td class="label">SIFT: avg adjustment movement</td><td class="val">{statistics.mean(sift_moves):.1f}px</td></tr>
  <tr><td class="label">SIFT+elastix: avg adjustment movement</td><td class="val">{statistics.mean(elastix_moves):.1f}px</td></tr>
</table>

<h2>Per-image comparison (largest SIFT adjustment movement first)</h2>
{''.join(sections)}

<footer>
  Red = unadjusted, green = adjusted. Line thickness 4px for visibility.
</footer>

</body>
</html>
"""

(OUT_DIR / "report.html").write_text(html)
print(f"wrote {OUT_DIR / 'report.html'}")
print(json.dumps({"n": n, "ok": n_ok, "both": n_both,
                   "sift_avg_move": round(statistics.mean(sift_moves), 2),
                   "elastix_avg_move": round(statistics.mean(elastix_moves), 2)}, indent=2))

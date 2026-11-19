"""
Score results/results.jsonl against ground truth and write results/scores.json and
results/summary.md.

Ground truth:
  synthetic  - exact: images/synthetic/<name>.json (analytic contrast of every element,
               limit = last element before the first one below 20 %, coarse -> fine)
  labelled   - the group/element in the file name (the team's own label)
  unlabelled - none; the readers' answers are listed side by side

The matched-filter reader's CTF fit (../ctf_fit.py) is scored as two extra readers
("+ CTF fit"). It is computed here from the per-element contrast tables the reader saved
(results/matched_filter_reader/<image>[_px]/*_usaf.csv), so no reader run is needed. Bright
bars are assumed (true for every image here); the tilt only changes the pixel footprint a
little, so it is taken from the truth for simulated images and as 0 for photos.

Usage:  python scripts/score.py [results/results.jsonl]
"""
import csv, json, re, sys
from pathlib import Path
import numpy as np

B = Path(__file__).resolve().parents[1]
RES = Path(sys.argv[1]) if len(sys.argv) > 1 else B / "results/results.jsonl"
recs = [json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
METHODS = ["yolo", "sift:auto", "sift:sift", "mine", "mine+px", "mine:fit", "mine+px:fit"]
NAMES = {"yolo": "YOLO (OmniTargetReader)", "sift:auto": "SIFT pipeline, default (auto)",
         "sift:sift": "SIFT pipeline, forced SIFT", "mine": "Matched-filter reader, no hint",
         "mine+px": "Matched-filter reader, pixel size given",
         "mine:fit": "Matched-filter reader + CTF fit, no hint",
         "mine+px:fit": "Matched-filter reader + CTF fit, pixel size given"}

sys.path.insert(0, str(B.parent))
import ctf_fit  # noqa: E402


def _fit_record(r):
    """The CTF-fit answer for one matched-filter reader record, from its saved element table."""
    stem = Path(r["image"]).stem + ("_px" if r["method"] == "mine+px" else "")
    cs = list((B / "results/matched_filter_reader" / stem).glob("*_usaf.csv"))
    base = {**{k: r[k] for k in ("kind", "image", "seconds")}, "method": r["method"] + ":fit", "result": None}
    if not cs or not r.get("result"):
        return base                                   # the reader gave no answer, so neither does the fit
    rows = []
    for e in csv.DictReader(open(cs[0])):
        rows.append({k: (v == "True") if v in ("True", "False") else
                     (int(v) if k in ("group", "element") else float(v)) for k, v in e.items()
                     if not k.startswith("fit_")})       # the reader's own fit columns (often blank)
    angle = 0.0
    if r["kind"] == "synthetic":
        angle = json.loads((B / r["image"]).with_suffix(".json").read_text())["angle_deg"]
    fit = ctf_fit.fit_ctf(rows, r["pixel_size"], angle, 1, 0.2)
    le = fit.get("limit_element")
    ge = [int(x) for x in le[1:].split("E")] if le else None
    return {**base, "result": ge, "crossing_lp_per_mm": fit.get("crossing_lp_per_mm"),
            "crossing_lp_per_mm_unc": fit.get("crossing_lp_per_mm_unc")}


# the saved element tables belong to the current run only, so older result files get no fit rows
if RES.name == "results.jsonl":
    recs += [_fit_record(r) for r in list(recs) if r["method"] in ("mine", "mine+px")]
else:
    METHODS = METHODS[:5]
kidx = lambda ge: 6 * ge[0] + ge[1] - 1
name = lambda ge: f"G{ge[0]}E{ge[1]}"

rows: dict = {}
for r in recs:
    rows.setdefault((r["kind"], Path(r["image"]).name), {})[r["method"]] = r


def truth(kind, img):
    if kind == "synthetic":
        t = json.loads((B / "images/synthetic" / img).with_suffix(".json").read_text())
        return tuple(t["truth_limit"]), t
    m = re.search(r"g(\d)e(\d)", img)
    return (int(m[1]), int(m[2])), None


out = {"per_image": [], "summary": {}, "contrast_accuracy": {}}
for kind in ("synthetic", "labelled"):
    st = {m: {"n": 0, "fail": 0, "exact": 0, "w1": 0, "abs": [], "signed": []} for m in METHODS}
    for (kd, img), mm in sorted(rows.items()):
        if kd != kind:
            continue
        tr, tj = truth(kind, img)
        line = {"kind": kind, "image": img, "truth": name(tr)}
        for m in METHODS:
            r = mm.get(m)
            if r is None:
                continue
            s = st[m]; s["n"] += 1
            res = r.get("result")
            if not res:
                s["fail"] += 1
                line[m] = "no answer"
                continue
            d = kidx(res) - kidx(tr)
            line[m] = name(res)
            s["signed"].append(d); s["abs"].append(abs(d)); s["exact"] += d == 0; s["w1"] += abs(d) <= 1
        out["per_image"].append(line)
    out["summary"][kind] = {
        NAMES[m]: {"images": s["n"], "no_answer": s["fail"], "exact": s["exact"], "within_1_element": s["w1"],
                   "mean_abs_error_elements": round(float(np.mean(s["abs"])), 2) if s["abs"] else None,
                   "mean_signed_error_elements": round(float(np.mean(s["signed"])), 2) if s["signed"] else None,
                   "worst_abs_error_elements": int(max(s["abs"])) if s["abs"] else None}
        for m, s in st.items() if s["n"]}

# contrast accuracy of the matched-filter reader on synthetic images (per element, vs analytic truth)
for m, suffix in (("mine", ""), ("mine+px", "_px")):
    errs = []
    for tf in sorted((B / "images/synthetic").glob("*.json")):
        t = json.loads(tf.read_text())
        tr = {(e["group"], e["element"]): e["contrast"] for e in t["elements"]}
        cs = list((B / "results/matched_filter_reader" / (tf.stem + suffix)).glob("*_usaf.csv"))
        if not cs:
            continue
        for e in csv.DictReader(open(cs[0])):
            ge = (int(e["group"]), int(e["element"]))
            if e["cut_off"] == "True" or e["undersampled"] == "True" or ge not in tr:
                continue
            errs.append(max(abs(float(e["contrast_H"]) - tr[ge]), abs(float(e["contrast_V"]) - tr[ge])))
    if errs:
        out["contrast_accuracy"][NAMES[m]] = {
            "elements": len(errs), "mean_abs_error": round(float(np.mean(errs)), 4),
            "median": round(float(np.median(errs)), 4), "p95": round(float(np.percentile(errs, 95)), 4),
            "max": round(float(np.max(errs)), 4)}

out["unlabelled"] = [{"image": img, **{m: (name(mm[m]["result"]) if mm[m].get("result") else "no answer")
                                       for m in METHODS if m in mm}}
                     for (kd, img), mm in sorted(rows.items()) if kd == "unlabelled"]
times: dict = {}
for r in recs:
    times.setdefault(r["method"], []).append(r["seconds"])
out["median_seconds_per_image"] = {NAMES[m]: float(np.median(v)) for m, v in times.items() if m in NAMES}

stem = RES.stem.replace("results", "scores")
(RES.parent / f"{stem}.json").write_text(json.dumps(out, indent=1))

# markdown summary
md = []
for kind, title in (("synthetic", "Simulated images, exact ground truth"),
                    ("labelled", "Team-labelled photos (label from the file name)")):
    md += [f"### {title}", "", "| Reader | Images | Exact | Within 1 element | Mean abs. error (elements) | Mean signed error | No answer |",
           "|---|---|---|---|---|---|---|"]
    for n, s in out["summary"][kind].items():
        md.append(f"| {n} | {s['images']} | {s['exact']} | {s['within_1_element']} | {s['mean_abs_error_elements']} | "
                  f"{s['mean_signed_error_elements']} | {s['no_answer']} |")
    md += ["", "| Image | Truth | " + " | ".join(NAMES[m] for m in METHODS) + " |", "|---" * (2 + len(METHODS)) + "|"]
    for l in out["per_image"]:
        if l["kind"] == kind:
            md.append(f"| {l['image']} | {l['truth']} | " + " | ".join(str(l.get(m, "")) for m in METHODS) + " |")
    md.append("")
UM = [m for m in ("yolo", "sift:auto", "sift:sift", "mine", "mine:fit") if m in METHODS]
md += ["### Unlabelled photos (no ground truth)", "", "| Image | " + " | ".join(NAMES[m] for m in UM) + " |",
       "|---" * (1 + len(UM)) + "|"]
for l in out["unlabelled"]:
    md.append(f"| {l['image']} | " + " | ".join(str(l.get(m, "")) for m in UM) + " |")
md += ["", "### Contrast accuracy of the matched-filter reader (simulated images, per element)", "",
       "| Run | Elements | Mean abs. error | Median | 95th percentile | Max |", "|---|---|---|---|---|---|"]
for n, c in out["contrast_accuracy"].items():
    md.append(f"| {n} | {c['elements']} | {c['mean_abs_error']:.3f} | {c['median']:.3f} | {c['p95']:.3f} | {c['max']:.3f} |")
md += ["", "### Median time per image (s)", "", "| Reader | Seconds |", "|---|---|"]
md += [f"| {n} | {t:.1f} |" for n, t in out["median_seconds_per_image"].items()]
(RES.parent / f"{stem.replace('scores', 'summary')}.md").write_text("\n".join(md) + "\n")
print("\n".join(md))

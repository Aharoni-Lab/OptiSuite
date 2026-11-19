"""
Run every reader on every benchmark image and append one JSON line per (image, method)
to results/results.jsonl. Already-present (image, method) pairs are skipped, so the run
can be resumed.

The YOLO and SIFT readers live on other branches. Extract them once, e.g.:
    git archive origin/OmniTargetReader | tar -x -C /tmp/omni
    git archive origin/usaf_target      | tar -x -C /tmp/sift
On Python < 3.10 add `from __future__ import annotations` to the top of each file in
/tmp/sift/usaf_interface/usaf_registration/*.py (it only changes how type hints are parsed).
Dependencies: numpy scipy pillow matplotlib opencv-python ultralytics.

Usage:
    python scripts/run_all.py --omni /tmp/omni --sift /tmp/sift/usaf_interface
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

B = Path(__file__).resolve().parents[1]          # benchmark/
READER = B.parent / "usaf_reader.py"
ap = argparse.ArgumentParser()
ap.add_argument("--omni", type=Path, help="extracted OmniTargetReader branch (YOLO reader)")
ap.add_argument("--sift", type=Path, help="usaf_interface folder of the usaf_target branch (SIFT reader)")
ap.add_argument("--python", default=sys.executable)
ap.add_argument("--methods", nargs="+", default=["yolo", "sift:auto", "sift:sift", "mine", "mine+px"])
ap.add_argument("--results", type=Path, default=B / "results/results.jsonl")
args = ap.parse_args()

imgs = [("synthetic", p, 2.4) for p in sorted((B / "images/synthetic").glob("*.png"))]
imgs += [("labelled", p, 2.4) for p in sorted((B / "images/labelled").glob("*.png"))]
imgs += [("unlabelled", B.parent / "output" / n, None) for n in
         ["USAF-Test-1.png", "USAF-Test-2.png", "USAF-Test-3.bmp", "STIMscopeLFOVImage.bmp", "SingleWell.PNG"]]
rel = lambda p: str(Path(p).resolve().relative_to(B)) if B in Path(p).resolve().parents else "../output/" + Path(p).name

done = set()
if args.results.exists():
    done = {(d["image"], d["method"]) for d in map(json.loads, args.results.read_text().splitlines())}

with open(args.results, "a") as fh:
    for kind, f, px in imgs:
        od = B / "results/matched_filter_reader" / f.stem
        jobs = []
        if "yolo" in args.methods and args.omni:
            jobs.append(("yolo", [args.python, str(B / "scripts/run_yolo.py"), str(args.omni), str(f)]))
        for mode in ("auto", "sift"):
            if f"sift:{mode}" in args.methods and args.sift:
                jobs.append((f"sift:{mode}", [args.python, str(B / "scripts/run_sift.py"), str(args.sift), str(f), mode]))
        if "mine" in args.methods:
            jobs.append(("mine", [args.python, str(READER), str(f), "--out-dir", str(od)]))
        if "mine+px" in args.methods and px:
            jobs.append(("mine+px", [args.python, str(READER), str(f), "--pixel-size", str(px), "--out-dir", str(od) + "_px"]))
        for m, cmd in jobs:
            if (rel(f), m) in done:
                continue
            t = time.time()
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                out, err = p.stdout + p.stderr, None
            except subprocess.TimeoutExpired:
                out, err = "", "timeout"
            rec = {"kind": kind, "image": rel(f), "method": m, "seconds": round(time.time() - t, 1)}
            if err:
                rec["error"] = err
            elif m.startswith("mine"):
                js = list(Path(cmd[cmd.index("--out-dir") + 1]).glob("*_usaf.json"))
                if js:
                    d = json.loads(js[0].read_text())
                    r = d["result"]
                    rec["result"] = [r["group"], r["element"]] if r else None
                    rec["pixel_size"] = d["pixel_size_um_fitted"]
                    rec["contrast"] = {f"{e['group']}:{e['element']}": [e["contrast_H"], e["contrast_V"]]
                                       for e in d["elements"] if not e["cut_off"]}
                else:
                    rec["error"] = out.strip().splitlines()[-1][:300] if out.strip() else "no output"
            else:
                line = [l for l in out.splitlines() if l.startswith("@@")]
                if line:
                    d = json.loads(line[-1][2:])
                    rec.update({k: v for k, v in d.items() if k in ("result", "error", "flipped")})
                else:
                    rec["error"] = out.strip().splitlines()[-1][:300] if out.strip() else "no output"
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            print(f.name, m, rec.get("result"), rec.get("error", ""), rec["seconds"], flush=True)

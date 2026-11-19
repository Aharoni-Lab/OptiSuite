# USAF reader benchmark

A comparison of three ways to read a 1951 USAF target image, scored against ground truth.

| Reader | Where | How it works |
|---|---|---|
| **YOLO** | branch `OmniTargetReader` (`usaf_algo.find_usaf_score`, model `best12.pt`) | Finds the large square to calibrate coordinates, a YOLO model finds bar sets, then measures (max − min) along hard-coded scanlines |
| **SIFT** | branch `usaf_target` (`usaf_registration.UsafRegistration.score_image_routine`) | Aligns the image to a reference photo with SIFT (plus a YOLO 4-point model), then a YOLO classifier calls each element resolved or unresolved. Run in its default `auto` mode and with SIFT forced |
| **Matched filter** | this folder's `../usaf_reader.py` | Matched-filter bar detection, layout-based identification, Michelson contrast per element. Run without a hint and with the pixel size given (`--pixel-size 2.4`) |
| **Matched filter + CTF fit** | `../ctf_fit.py`, on the same runs | The element the fitted contrast curve crosses 20% in, instead of the element-by-element limit. Computed by `scripts/score.py` from the saved element tables |

All readers were run with their default settings. The result compared is the reported group and element. The error is
counted in elements: 6 elements = 1 group.

## Ground truth

- **Simulated images** (`images/synthetic/`, 15 images): made to copy the STIMscope setup in the labelled photos:
  - groups 2–7 in view; target mirrored and tilted −28° (6 images) or −34° (6 images), or not mirrored and
    tilted +12° (3 images)
  - 2.4 µm camera pixels, 2592 × 1944 px, 8-bit
  - Gaussian blur σ = 2–9 µm, a constant stray-light floor and read noise

  The true Michelson contrast of every element is computed analytically (3 bars × Gaussian blur × square pixel at the
  tilt angle) and stored next to each image as `<name>.json`. The true limit is the last element before the first one
  below 20% contrast, going from coarse to fine. Truth limits range from G5E1 to G7E1.
- **Labelled photos** (`images/labelled/`, 6 images): copied from the `usaf_target` branch (`test_img/`). The label is
  the team's in the file name (for example `test_image_g4e4` = G4E4). It is a judgement of "resolved", not a measured
  20% contrast.
- **Unlabelled photos** (`../output/`, 5 images): no ground truth; the readers' answers are listed side by side.

## Results

The full tables, including every image, are in [`results/summary.md`](results/summary.md).

### Simulated images (exact truth)

| Reader | Exact | Within 1 element | Mean abs. error (elements) | No answer |
|---|---|---|---|---|
| YOLO | 0 / 15 | 1 | 8.4 | 0 |
| SIFT, default | 0 / 15 | 0 | 22.0 | 12 |
| SIFT, forced | 0 / 15 | 0 | 20.7 | 12 |
| **Matched filter, no hint** | **13 / 15** | **15** | **0.13** | 0 |
| **Matched filter, pixel size given** | **13 / 15** | **15** | **0.13** | 0 |
| **Matched filter + CTF fit** (either) | **15 / 15** | **15** | **0.0** | 0 |

The matched-filter reader's per-element contrast is within 0.5% of the truth on average (507 elements; 95% within 2.5%,
worst 4.1%). Its two misses are both G6E2, where the true contrast is 20.45% and it measured 19.97%. The CTF fit gets
both right: it uses every element at once, so one element measured just under 20% doesn't decide the answer. Its
crossing frequency is within 1.6% of the true one (mean 0.5%), and the fitted blur σ within 0.04 µm of the truth.

**This test is unfair to YOLO and SIFT.** The simulated slide comes from `../generate_usaf_target.py`. Measured from
the large square, its element positions are 7–15% closer in than the positions hard-coded in the YOLO and SIFT code,
which match the physical slide in the STIMscope photos. Their scanlines therefore miss the elements, and the SIFT
classifier reports "unresolved" at the first element. These results show those readers depend on that one slide's
layout, not how accurate they are on it. The matched-filter reader uses only the layout's structure (which elements sit
next to each other, and the ¼-scale nesting), not exact distances.

### Team-labelled photos

| Reader | Exact | Within 1 element | Mean abs. error (elements) | No answer |
|---|---|---|---|---|
| YOLO | 1 / 6 | 1 | 5.5 | 0 |
| **SIFT, default** | **2 / 6** | **4** | **1.0** | 0 |
| SIFT, forced | 2 / 6 | 3 | 1.8 | 0 |
| Matched filter, no hint | 0 / 6 | 0 | 5.0 | 1 |
| Matched filter, pixel size given | 1 / 6 | 2 | 2.3 (always lower) | 0 |
| Matched filter + CTF fit, no hint | 0 / 6 | 0 | 5.4 | 1 |
| Matched filter + CTF fit, pixel size given | 1 / 6 | 2 | 2.5 | 0 |

This test favours the SIFT pipeline:
- these photos are in its own test folder, and its classifier was trained on images from the same setup
- the labels are the team's judgement, not a 20% contrast measurement
- the photos are heavily saturated (bars at 255 in 25 or more elements)

The matched-filter reader requires both line directions to reach 20%. On these photos the vertical lines fall off faster
(for example on `g6e1` the horizontal lines stay at 20% or more up to G6E3, but the vertical lines drop below 20% at
G5E4). That is why it reads 1–3 elements below the labels. The CTF fit doesn't change this, because the gap is in what is
measured (20% in both directions against a visual call), not in measurement noise.

Without a hint, `test_image_g3e6` has too few elements for the layout vote (it asks for `--pixel-size`), and
`test_image_g3e6_(1)` shows only one group pair, so the group number is assumed and comes out 2 groups too fine.

### Unlabelled photos

| Image | YOLO | SIFT, default | SIFT, forced | Matched filter | + CTF fit |
|---|---|---|---|---|---|
| STIMscopeLFOVImage.bmp | G6E4 | G7E6 | G7E1 | G5E5 | G6E3 (poorly defined) |
| SingleWell.PNG | G6E2 | G6E4 | G5E6 | G6E5 | G6E5 |
| USAF-Test-1.png | G5E2 | G5E6 | G5E6 | G5E5 | G5E6 |
| USAF-Test-2.png | G6E6 | G6E5 | G5E5 | G6E3 | G6E2 |
| USAF-Test-3.bmp | G6E2 | G6E2 | G6E2 | G6E1 | G6E1 |

The fit's crossing frequency and uncertainty for each photo are in `../output/usaf_results/<image>_usaf.json`
(`ctf_fit`). On the raw STIMscope image the contrast stays near 20% over a whole octave (stray light), so where it
crosses 20% is poorly defined (85 ± 10 lp/mm). On Test-2 the crossing (80.3 lp/mm) is 0.4% below G6E3's frequency, so
the two answers agree.

### Speed (median per image)

YOLO 2.0 s, SIFT 4.4 s, matched filter 14.1 s (14.3 s with the pixel size given). The matched-filter runs in
`results/` are from the current reader (with the CTF fit and the speed-up). They were first run at about 31 s per
image; rerunning all 47 gave the same answers, pixel sizes and per-element CSV values (see `../README.md`, Speed).

### Before and after the matched-filter reader fixes

The benchmark exposed two weaknesses in the matched-filter reader, which were then fixed:
- the group number without a pixel size (the finer-pair light check)
- a blurred, saturated group pair it couldn't detect (the guided search)

The first run is kept in `results/results_before_fix.jsonl` and
[`results/summary_before_fix.md`](results/summary_before_fix.md):

| Matched-filter reader | Before | After |
|---|---|---|
| Simulated, no hint: exact / within 1 / mean error | 6 / 8 / 5.7 | 13 / 15 / 0.13 |
| Labelled, no hint: mean error | 10.4 | 5.0 |
| Labelled, pixel size given: mean error | 2.5 | 2.3 |
| `test_image_g4e4`, pixel size given | G3E6 | G4E1 |

## Folder contents

```
images/synthetic/   15 simulated images (.png) + ground truth for each (.json)
images/labelled/    6 team-labelled photos from the usaf_target branch
results/
  results.jsonl               one line per (image, reader): answer, time, errors; matched-filter reader also stores
                              its per-element contrast
  results_before_fix.jsonl    the same, before the matched-filter reader fixes
  scores.json, summary.md     scored results (summary_before_fix.* for the first run)
  matched_filter_reader/<image>[_px]/   matched-filter reader output per run: element table (.csv) and contrast plot
                              (_ctf.png); real photos also have the overlay (_overlay.png)
scripts/
  make_synth.py   regenerate the simulated images and their truth (fixed seeds, so identical output)
  run_yolo.py     run the YOLO reader on one image in a fresh process
  run_sift.py     run the SIFT reader on one image in a fresh process
  run_all.py      run every reader on every image (resumable)
  score.py        score results against ground truth -> scores.json, summary.md
```

## Rerunning

The YOLO and SIFT readers live on other branches. Extract them outside the repository:

```bash
git archive origin/OmniTargetReader | tar -x -C /tmp/omni
git archive origin/usaf_target | tar -x -C /tmp/sift
```

The SIFT package uses Python 3.10 type-hint syntax. On Python 3.9, add `from __future__ import annotations` as the
first line of each file in `/tmp/sift/usaf_interface/usaf_registration/`. That changes nothing except how type hints
are parsed. Install `numpy scipy pillow matplotlib opencv-python ultralytics`, then from this folder:

```bash
python scripts/make_synth.py
python scripts/run_all.py --omni /tmp/omni --sift /tmp/sift/usaf_interface
python scripts/score.py
```

`run_all.py` skips (image, reader) pairs already in `results/results.jsonl`. To start from scratch, delete or rename
that file first.

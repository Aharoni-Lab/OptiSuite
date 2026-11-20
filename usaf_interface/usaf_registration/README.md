# USAF registration

Finds the highest resolved element of a USAF 1951 target in a photo. Every glyph's box and
scanline is placed by matching the photo to annotated templates with SIFT, one nested level at a
time, and every element is scored with a scanline checker.

```python
from usaf_interface.usaf_registration import UsafRegistration

reg = UsafRegistration()
best, scan_index, scanline_map, scores, image = reg.find_usaf_score("photo.png")
# best = [group, element]; reg.C.nested_result holds the full record of the run
```

## Pipeline

```
photo
  │
  ├─ 1. Normalize contrast
  ├─ 2. Find the white square            (size and position, used for scale)
  ├─ 3. YOLO 4-point model               (how many nested levels, mirrored or not)
  ├─ 4. Read the printed group numbers   (which group is the biggest in view)
  ├─ 5. Nested SIFT matching             (place every glyph box, one level at a time)
  ├─ 6. Scanline checker                 (score every element)
  └─ 7. Best element → lp/mm and line width
```

### 1. Normalize contrast

The photo is stretched to the full 0-255 range for matching. The original is kept for scoring.

### 2. Find the white square

`classic_warp.find_square_corners`. The square's size tells the matcher how big the target is in
the photo, and its position is used to catch matches that slipped one nested level (step 5).
Candidates come from Otsu's threshold plus three brighter cuts (50%, 65% and 80% of the brightest
level), so the square is still found on dark, blurry photos where its glow merges with nearby
bars. Each candidate must have four ~90° corners, near-equal sides and a white interior. If no
square is found, matching uses a centred guess.

### 3. YOLO 4-point model

`yolo_model.count_4pts_pattern` and `yolo_4pt_calculation`. The number of detected patterns is the
number of nested levels in view (1-3). The order of each pattern's four keypoints (clockwise or
not) says whether the target is mirrored; the pattern with the most keypoint confidence decides.
`FLIP_FIXED` makes `FLIPED_TARGET` win over YOLO (the app's "flipped" / "not flipped" setting).

### 4. Read the printed group numbers

`nested_match.read_start_group` finds the start group, the biggest group in view:

1. Match the whole photo to a template (layer 1 of step 5).
2. Cut out every printed group number through that match, upright and unmirrored.
3. Compare each cut-out with reference digits taken from the templates' own printed numbers
   (shape plus width/height ratio).
4. A reading with score ≥ 0.4 and a lead of ≥ 0.05 over the next digit votes for
   `digit read − template's number`.
5. A shift with at least 2 votes and no tie gives the start group: the smallest group read,
   rounded down to even.

Templates are tried in turn (the default for the pattern count first). If none agrees, the start
group falls back to `8 − 2 × pattern_count`. `NESTED_GROUP` sets it by hand.

### 5. Nested SIFT matching

`nested_match.nested_match_layers`. Templates live in `templates/`, with every glyph's box,
scanline and printed group number annotated in `nested_templates.json`:

| Template | Image | Groups | Levels |
|---|---|---|---|
| 3 | `new_SIFT_ref_image_bordered.png` | 2-7 | 3 |
| 4 | `sift_ref_group45_from_bordered.png` | 4-7 | 2 |
| 14 | `level_g6-7_relabeled_textured.png` | 2-3 (the image's printed numbers say 6-7) | 1 |
| 16 | `sift_ref_group89_degraded.png` | 8-9 | 1 |
| 17 | `sift_ref_group69_degraded.png` | 6-9 | 2 |

A template can be relabelled to other groups (`4@+2` = template 4 read as 6-9), since every
nested level has the same pattern. Each layer uses the template with exactly as many levels as
are left from there, preferring one whose own labels match, otherwise the first of 3, 4, 14, 17,
16 relabelled: a single 6-7 level uses `14@+4`, a single 8-9 level uses 16.

**Layer 1, the biggest level in view.** SIFT on the whole photo, scaled so its white square matches
the template's; Lowe ratio test (0.75), one-to-one matches, RANSAC homography (≥ 8 inliers). The
projected boxes must be finite, span at least 20 px, and none can be over 6× the median box size.
Then:
- If the template's square lands about 4× too small or too big, the match slipped one nested
  level; it is moved back one level and must then line up with the photo's square.
- If only one level is in view and the one-level template fails, the outer level of a two-level
  template is tried instead.
- If layer 1 fails, the match is retried mirrored (unless `FLIP_FIXED`).

**Deeper levels.** Each level is matched inside a cut-out of the photo around where the level above
predicts it (ratio 0.8, RANSAC 6 px, ≥ 6 inliers), with `NESTED_MATCH`:
- `own_template` (default): the level's own template, shrunk to the expected scale.
- `parent_crop`: a crop of the template one level up.

If a level fails, it and every deeper level reuse the last good match. Levels whose boxes land
mostly outside the photo are dropped.

### 6. Scanline checker

`nested_match.check_scanline`, for every element of every placed group (2-9), vertical and
horizontal glyph:

- **contrast** = 98th − 2nd percentile along the scanline, on the original photo scaled to 0-1
- **minima** = dark dips in the smoothed profile along the scanline extended 20% at each end
- **resolved** = at least 2 minima and contrast above `SCORE_THRESHOLD` (0.2)

### 7. Result

The best element is the highest group/element resolved in either direction.

- lp/mm = 2^(group + (element − 1) / 6)
- line width = 1 / (2 × lp/mm)

`score_image_routine` returns the same as `find_usaf_score` without the image, writes
`logs/usaf_log_<photo>.json`, and gives `None` for photos that can't be scored.

## Settings

`constants.UsafConfig`, per `UsafRegistration` instance (`reg.C`):

| Setting | Default | |
|---|---|---|
| `SCORE_THRESHOLD` | 0.2 | contrast needed (with ≥ 2 minima) to call a glyph resolved |
| `SCORE_METHOD` | `"min"` | how the vertical and horizontal scores are merged for the curve |
| `NESTED_MATCH` | `"own_template"` | how deeper levels are matched (`own_template` / `parent_crop`) |
| `NESTED_GROUP` | `None` | start group by hand; `None` reads the printed numbers |
| `FLIPED_TARGET` | `True` | mirrored target; set per photo by YOLO unless `FLIP_FIXED` |
| `FLIP_FIXED` | `False` | use `FLIPED_TARGET` as given, no YOLO direction or mirror retry |
| `DEBUG_MODE`, `PREVIEW_MODE` | `False` | debug plots / show the scored scanlines |

## In the app

`usaf_interface/analyzers/usaf.py`:
- **Probe:** YOLO finds patterns → 0.96, only the white square → 0.35, neither → 0.1.
- **Flip setting:** "auto" runs the pipeline once and lets it pick the mirror; "flipped" and
  "not flipped" force it.

## Checking matches

`nested_report.py` draws the projected glyph boxes and scanlines on each photo (green resolved,
red not resolved, yellow the best element) and saves every result:

```
python -m usaf_interface.usaf_registration.nested_report <images or folders> --out <folder>
```

## Files

| File | |
|---|---|
| `usaf_algo.py` | pipeline entry points: `find_usaf_score`, `score_image_routine` |
| `nested_match.py` | templates, SIFT matching, digit reading, scanline checker |
| `classic_warp.py` | white square detection |
| `yolo_model.py` | YOLO 4-point model: pattern count and mirror |
| `helper.py` | line sampling, contrast normalization, lp/mm |
| `constants.py` | settings and per-photo state |
| `nested_report.py` | drawings of the projected boxes |
| `nested_templates.json`, `templates/` | annotated templates |
| `models/` | `4p_detect_ultra_pro_max.pt` (4-point model), `best23.pt` (scanline detector, app default) |

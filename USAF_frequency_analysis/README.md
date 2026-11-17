# USAF frequency analysis

Tools to generate an ideal 1951 USAF target, look at its spectrum, and **read real
microscope images of the target**: identify every group/element and report the finest
element that still reaches a required contrast (default 20 %).

```bash
pip install -r requirements.txt
```

| Script | What it does |
|---|---|
| `generate_usaf_target.py` | Synthetic, anti-aliased USAF slide (groups 2–7 by default, bright bars on black) + JSON with every element's position and frequency |
| `fft_analysis.py` | 2-D FFT of any image: log spectrum, radial average, fx/fy profiles with USAF group frequencies marked |
| `usaf_reader.py` | Reads a microscope image of the target: group/element identification, contrast per element, resolution limit at a contrast threshold |
| `validate_usaf_reader.py` | Checks the reader against simulated microscope images with known ground-truth contrast |

## Reading a microscope image

```bash
python usaf_reader.py my_image.tif                       # 20 % contrast threshold
python usaf_reader.py my_image.tif --contrast 0.3
python usaf_reader.py my_image.tif --pixel-size 1.1      # µm/px at the sample, rough is fine
python usaf_reader.py my_image.tif --magnification 10 --camera-pixel 3.45
python usaf_reader.py my_image.tif --coarsest-group 4    # largest group visible
```

Results go to `usaf_results/` next to the image: a JSON and CSV with every element,
an overlay image (green = passes, red = fails, grey = cut off by the image border, purple/orange = located from the layout
rather than detected, blue = the reported limit, yellow = scan lines), and a
contrast-vs-frequency (CTF) plot.

As an independent check, the reader also takes **one scan line through the centre of every
bar set**, perpendicular to the bars, and reads the nearest raw pixel values (no
interpolation or averaging). `<stem>_scanlines.png` plots that scan line against the reader's
averaged profile for every element, with the ideal bar positions shaded, and gives both
contrasts in each panel title. The values behind the plot are in `<stem>_scanlines.csv`, and the
scan-line contrast is in the per-element CSV and JSON (`scanline_contrast_H/V`).
A single scan line is noisier and, at fine elements, usually a little lower than the reader's
value, because the pixel centres rarely land exactly on the bar and gap centres.

### How it works

A whole-image FFT mixes all elements together and can't say *which* element still has
20 % contrast, so the reader uses local, matched-frequency analysis:

1. **Orientation**: dominant edge angle; the image is de-rotated. Edges within 16 px of the image border (padding strips, frame edges) are ignored. 90° rotations and mirrored images work without extra steps.
2. **Matched filter**: normalised cross-correlation with an ideal 3-bar template over a bank of line widths. It ignores contrast, so faint elements are still found.
3. **Scale lattice**: USAF line widths step by exactly 2^(1/6), so all detections are indexed relative to each other without knowing the pixel size.
4. **Pairing**: each element needs a horizontal and a vertical bar set of equal width next to each other, which rejects digits and noise.
5. **Identification**: where consecutive elements do *not* sit next to each other on the slide (element 1 of every group, element 2 of even groups) fixes the element numbers. The remaining two-group ambiguity, because every group pair is a ¼-scale copy of the one around it, is settled by a rough pixel size (within ×/÷2), `--coarsest-group`, or, if neither is given, by assuming the finest visible pair is groups 6–7.
6. **Prediction**: elements too blurred to detect are located from the slide's geometry, so the contrast fall-off past the limit is measured.
   **Layout check**: every detected element is also compared with the position the other elements predict. If one of its
   bar sets is more than 4 line widths off while the other agrees, it was paired with the wrong feature (the reference
   square, a digit, a neighbouring element), so it is moved to its predicted position and re-snapped.
   **Cut-off elements**: a bar set that isn't fully inside the image can't be measured. It is drawn grey, never passes,
   and is stepped over when looking for the limit. Both cases are listed in the notes.
7. **Contrast**: profile across each bar set, averaged along the central 60 % of the bars, interpolated once with cubic splines on the original image.
   *Michelson contrast* = (I_bar − I_gap)/(I_bar + I_gap), using the 3 bar centres and 2 gaps. It is signed, so contrast reversal shows as negative. A lock-in (sine fit at the element's frequency) modulation is also reported.
   An element passes when **both** horizontal and vertical lines reach the threshold.
   The reported limit is the **last passing element before the first failure**, going from coarse
   to fine. One *isolated* failure, where the very next element passes again, is stepped over,
   because a single element at a blurry edge of the field shouldn't end the reading. The skipped
   element is named in the notes and in the JSON (`skipped_isolated_failures`). `--skip-isolated 0`
   stops at the very first failure; `--limit-rule finest-pass` reports the finest element that
   passes at all. Both answers are in the JSON (`result_first_fail`, `result_finest_pass`).
   Elements finer than the camera's Nyquist limit are flagged and excluded.
   The notes warn when bars reach the camera's full scale (clipped peaks bias contrast), and when the
   limit element has fewer than 2 px per line. There, contrast relies on averaging along tilted bars
   and a single row of pixels reads much lower, so the result is at the camera's sampling limit.

**Background (black level).** Contrast is always reported twice: on the raw image and after a
background correction. Both limits are printed, saved in the JSON (`background`) and drawn in the
CTF plot (the dashed lines are the non-primary result), and a note appears when they disagree.

- **Default: the raw image is the primary result.** Stray light and glare that lift the gaps are
  part of the system's performance, so they are kept. The comparison is an automatic estimate of
  the black level (the darkest 0.5 % of the median-filtered image). That estimate can't tell camera
  offset from stray light, so it is shown for reference only.
- **Recommended correction: a dark frame.** Take one or more frames with the light blocked, at the
  same exposure and gain, and pass them with `--dark-frame dark1.tif dark2.tif ...`. They are
  averaged and subtracted pixel by pixel, which removes only the camera offset. The corrected
  result then becomes the primary one.
- `--black-level <value>` subtracts a known offset; `--black-level auto` makes the automatic
  estimate the primary result.

```bash
python usaf_reader.py my_image.tif --dark-frame dark_01.tif dark_02.tif
```

### Accuracy (`validate_usaf_reader.py`)

Simulated images (Gaussian PSF σ = 1.2–2.5 µm, 1 µm pixels, rotated and mirrored, vignetting, offset, noise; one case with a dark frame):
group/element identification correct, fitted pixel size within 0.4 %, contrast error ≤ 2 %
(mean 0.2–0.6 %), and the resolution limit matched the ground truth in every case.

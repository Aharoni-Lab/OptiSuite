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
an overlay image (green = passes, red = fails, purple/orange = located from the layout
rather than detected, blue = the reported limit), and a contrast-vs-frequency (CTF) plot.

### How it works

A whole-image FFT mixes all elements together and can't say *which* element still has
20 % contrast, so the reader uses local, matched-frequency analysis:

1. **Orientation**: dominant edge angle; the image is de-rotated. 90° rotations and mirrored images work without extra steps.
2. **Matched filter**: normalised cross-correlation with an ideal 3-bar template over a bank of line widths. It ignores contrast, so faint elements are still found.
3. **Scale lattice**: USAF line widths step by exactly 2^(1/6), so all detections are indexed relative to each other without knowing the pixel size.
4. **Pairing**: each element needs a horizontal and a vertical bar set of equal width next to each other, which rejects digits and noise.
5. **Identification**: where consecutive elements do *not* sit next to each other on the slide (element 1 of every group, element 2 of even groups) fixes the element numbers. The remaining two-group ambiguity, because every group pair is a ¼-scale copy of the one around it, is settled by a rough pixel size (within ×/÷2), `--coarsest-group`, or, if neither is given, by assuming the finest visible pair is groups 6–7.
6. **Prediction**: elements too blurred to detect are located from the slide's geometry, so the contrast fall-off past the limit is measured.
7. **Contrast**: profile across each bar set, averaged along the central 60 % of the bars, interpolated once with cubic splines on the original image.
   *Michelson contrast* = (I_bar − I_gap)/(I_bar + I_gap), using the 3 bar centres and 2 gaps. It is signed, so contrast reversal shows as negative. A lock-in (sine fit at the element's frequency) modulation is also reported.
   An element passes when **both** horizontal and vertical lines reach the threshold.
   Elements finer than the camera's Nyquist limit are flagged and excluded.

Contrast is measured on the raw image by default. Use `--black-level auto` or `--black-level <value>` to subtract a camera offset first.

### Accuracy (`validate_usaf_reader.py`)

Simulated images (Gaussian PSF σ = 1.2–2.5 µm, 1 µm pixels, rotated and mirrored, vignetting, offset, noise):
group/element identification correct, fitted pixel size within 0.4 %, contrast error ≤ 2 %
(mean 0.2–0.6 %), and the resolution limit matched the ground truth in every case.

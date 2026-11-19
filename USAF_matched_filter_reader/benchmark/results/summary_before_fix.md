### Simulated images, exact ground truth

| Reader | Images | Exact | Within 1 element | Mean abs. error (elements) | Mean signed error | No answer |
|---|---|---|---|---|---|---|
| YOLO (OmniTargetReader) | 15 | 0 | 1 | 8.4 | -7.87 | 0 |
| SIFT pipeline, default (auto) | 15 | 0 | 0 | 22.0 | -22.0 | 12 |
| SIFT pipeline, forced SIFT | 15 | 0 | 0 | 20.67 | -20.67 | 12 |
| Matched-filter reader, no hint | 15 | 6 | 8 | 5.73 | 5.47 | 0 |
| Matched-filter reader, pixel size given | 15 | 13 | 15 | 0.13 | -0.13 | 0 |

| Image | Truth | YOLO (OmniTargetReader) | SIFT pipeline, default (auto) | SIFT pipeline, forced SIFT | Matched-filter reader, no hint | Matched-filter reader, pixel size given |
|---|---|---|---|---|---|---|
| synA_s2.0.png | G7E1 | G4E4 | no answer | no answer | G7E1 | G7E1 |
| synA_s3.0.png | G6E4 | G4E4 | no answer | no answer | G6E4 | G6E4 |
| synA_s4.0.png | G6E2 | G4E5 | G2E2 | no answer | G6E2 | G6E2 |
| synA_s5.5.png | G5E5 | G4E4 | no answer | no answer | G7E5 | G5E5 |
| synA_s7.0.png | G5E3 | G4E4 | no answer | no answer | G7E3 | G5E3 |
| synA_s9.0.png | G5E1 | G4E4 | no answer | no answer | G7E1 | G5E1 |
| synB_s2.0.png | G7E1 | G4E5 | no answer | no answer | G7E1 | G7E1 |
| synB_s3.0.png | G6E4 | G4E5 | no answer | no answer | G6E4 | G6E4 |
| synB_s4.0.png | G6E2 | G3E6 | no answer | no answer | G6E1 | G6E1 |
| synB_s5.5.png | G5E5 | G3E5 | no answer | no answer | G7E5 | G5E5 |
| synB_s7.0.png | G5E3 | G4E4 | no answer | G2E2 | G7E3 | G5E3 |
| synB_s9.0.png | G5E1 | G3E5 | no answer | G2E4 | G7E1 | G5E1 |
| synC_s2.0.png | G7E1 | G6E1 | G3E2 | G2E3 | G7E1 | G7E1 |
| synC_s4.0.png | G6E2 | G6E1 | no answer | no answer | G6E1 | G6E1 |
| synC_s7.0.png | G5E3 | G6E1 | G2E2 | no answer | G7E3 | G5E3 |

### Team-labelled photos (label from the file name)

| Reader | Images | Exact | Within 1 element | Mean abs. error (elements) | Mean signed error | No answer |
|---|---|---|---|---|---|---|
| YOLO (OmniTargetReader) | 6 | 1 | 1 | 5.5 | 4.83 | 0 |
| SIFT pipeline, default (auto) | 6 | 2 | 4 | 1.0 | -1.0 | 0 |
| SIFT pipeline, forced SIFT | 6 | 2 | 3 | 1.83 | -1.83 | 0 |
| Matched-filter reader, no hint | 6 | 0 | 0 | 10.4 | 9.2 | 1 |
| Matched-filter reader, pixel size given | 6 | 1 | 2 | 2.5 | -2.5 | 0 |

| Image | Truth | YOLO (OmniTargetReader) | SIFT pipeline, default (auto) | SIFT pipeline, forced SIFT | Matched-filter reader, no hint | Matched-filter reader, pixel size given |
|---|---|---|---|---|---|---|
| test_image_g3e6.png | G3E6 | G3E6 | G3E6 | G3E6 | no answer | G3E5 |
| test_image_g3e6_(1).png | G3E6 | G5E6 | G3E6 | G3E6 | G5E6 | G3E6 |
| test_image_g4e4.png | G4E4 | G6E1 | G4E3 | G4E3 | G7E6 | G3E6 |
| test_image_g5e4.png | G5E4 | G6E4 | G5E2 | G5E2 | G7E1 | G5E1 |
| test_image_g6e1.png | G6E1 | G6E5 | G5E5 | G5E5 | G7E3 | G5E3 |
| test_image_g6e6.png | G6E6 | G6E4 | G6E5 | G5E6 | G6E3 | G6E3 |

### Unlabelled photos (no ground truth)

| Image | YOLO (OmniTargetReader) | SIFT pipeline, default (auto) | SIFT pipeline, forced SIFT | Matched-filter reader, no hint |
|---|---|---|---|---|
| STIMscopeLFOVImage.bmp | G6E4 | G7E6 | G7E1 | G5E5 |
| SingleWell.PNG | G6E2 | G6E4 | G5E6 | G6E5 |
| USAF-Test-1.png | G5E2 | G5E6 | G5E6 | G5E5 |
| USAF-Test-2.png | G6E6 | G6E5 | G5E5 | G6E3 |
| USAF-Test-3.bmp | G6E2 | G6E2 | G6E2 | G6E1 |

### Contrast accuracy of the matched-filter reader (simulated images, per element)

| Run | Elements | Mean abs. error | Median | 95th percentile | Max |
|---|---|---|---|---|---|
| Matched-filter reader, no hint | 507 | 0.005 | 0.002 | 0.025 | 0.041 |
| Matched-filter reader, pixel size given | 507 | 0.005 | 0.002 | 0.025 | 0.041 |

### Median time per image (s)

| Reader | Seconds |
|---|---|
| YOLO (OmniTargetReader) | 2.0 |
| SIFT pipeline, default (auto) | 4.4 |
| SIFT pipeline, forced SIFT | 3.9 |
| Matched-filter reader, no hint | 29.7 |
| Matched-filter reader, pixel size given | 30.6 |

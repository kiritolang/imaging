# benchmarks — imaging vs Pillow vs OpenCV

Compares imaging's wall-time on a common set of image operations against Pillow (PIL) and
OpenCV, decoding the same PNG fixture in all three libraries and running each operation N times
(best-of-N is reported). This is intended as a **calibration** — not a claim that pure-Kirito
can match libjpeg/libopencv, but a "how much do I pay for interpreted per-pixel work?" reference.

## How to run

Prereqs:

```sh
pip install pillow opencv-python-headless numpy
```

Then:

```sh
benchmarks/run.sh                # 128x128, 5 reps
benchmarks/run.sh 256 10         # 256x256, 10 reps
KI=/path/to/ki benchmarks/run.sh # use a specific ki binary (else /tmp/ki, else fetched fresh)
```

`run.sh` downloads the latest `ki` release if it isn't already at `/tmp/ki`, regenerates the PNG
fixture with `_make_fixture.py`, runs `bench_imaging.ki` and `bench_pillow_opencv.py`, and pivots
their tab-separated output into a Markdown table.

## Sample results

`ki 1.12.1` vs Pillow 12.3.0 vs OpenCV 5.0.0, 128×128 RGB, best of 5. Times in ms:

| operation         |    imaging |     pillow |     opencv |   vs pil |    vs cv |
|-------------------|------------|------------|------------|----------|----------|
| flip_horizontal   |       1.58 |       0.01 |       0.00 |   145.1x |   523.2x |
| flip_vertical     |       1.61 |       0.00 |       0.00 |   434.7x |   609.9x |
| rotate_90         |       2.25 |       0.01 |       0.01 |   186.8x |   335.1x |
| rotate_180        |       3.18 |       0.01 |       0.00 |   332.2x |  1033.5x |
| translate_paste   |      22.08 |       0.06 |       0.11 |   359.3x |   196.2x |
| gaussian_blur_r2  |     105.49 |       0.39 |       0.03 |   268.9x |  3254.1x |
| box_blur_r2       |     100.96 |       0.14 |       0.01 |   727.5x |  7373.4x |
| median_3x3        |     103.44 |       0.95 |       0.02 |   109.4x |  4874.0x |
| find_edges        |     102.22 |       0.23 |       0.05 |   445.9x |  2040.2x |
| convert_rgb_to_l  |      10.16 |       0.01 |       0.01 |   694.8x |  1360.7x |
| resize_half_bilin |      10.74 |       0.08 |       0.01 |   126.6x |  1653.8x |
| resize_2x_bilin   |      81.33 |       0.42 |       0.08 |   195.1x |  1037.4x |
| invert            |       4.70 |       0.05 |       0.00 |    90.8x |  1743.0x |
| autocontrast      |      48.93 |       0.15 |       0.00 |   324.5x | 21101.3x |
| equalize          |      79.00 |       0.14 |       0.05 |   560.2x |  1545.0x |

`vs pil` / `vs cv` show how many times **slower** imaging is; `1.0x` would be a tie.

## What to make of the numbers

- **The absolute time is small on 128×128** — every op under 110 ms — so a script that processes
  a handful of images per minute won't notice. What suffers is a script that touches thousands
  of images in a loop.
- **Kirito's vectorised paths (filters, resize, convert) are within ~100–500× of Pillow.** That
  reflects Kirito's interpreter overhead per tensor op — the actual arithmetic runs in C, but
  every op dispatch pays for name lookup + result construction + GC roots. Pillow is C from top
  to bottom.
- **Simple flips are the closest match** because they compile to one tensor call and Pillow's
  own transpose is a memcpy. Both bottom out in memory bandwidth.
- **OpenCV is ~10× faster than Pillow again** on almost everything because it's SIMD-vectorised
  through libjpeg-turbo, IPP, and (where available) OpenCL. Nothing pure-Python can match it.
- **The imaging → Pillow gap widens on rank filters (median, min, max).** Our impl stacks the
  shifted windows into a (K², H, W, C) tensor and calls `median(axis=0)` — the memory allocation
  is expensive relative to Pillow's per-pixel C loop. That's the operation to optimise if
  someone wants to profile.

## Files

```
_make_fixture.py            deterministic 128x128 gradient + salt-and-pepper noise (Pillow)
bench_imaging.ki            imaging ops timed via time.perfcounterns()
bench_pillow_opencv.py      matching Pillow + OpenCV ops timed via time.perf_counter_ns()
run.sh                      driver: fixture -> run both -> pivot into a table
fixture.png                 the generated fixture (regenerated on each run)
```

## Fairness notes

- **Same input.** All three libraries load the exact same PNG. Decode is done ONCE per library,
  before the timing loop, so codec speed does not leak into the numbers.
- **Same intent per op.** Where APIs differ (e.g. "translate" — Pillow uses `ImageChops.offset`,
  OpenCV uses `warpAffine`, imaging uses `paste-onto-blank`) we pick the canonical way each
  library documents. See `bench_pillow_opencv.py` for the exact mapping.
- **Best of N.** GC pauses and page faults dominate the first run; the min removes them cleanly.
  Bump `reps` if you want tighter confidence.
- **Not tested cross-mode.** Every op runs on RGB. Some libraries (imaging in particular) are
  faster on L than RGB because the tensor is 3× smaller.

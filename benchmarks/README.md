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

`ki 1.17.0` vs Pillow 12.3.0 vs OpenCV 5.0.0, 128×128 RGB, best of 5. Times in ms:

| operation         |    imaging |     pillow |     opencv |   vs pil |    vs cv |
|-------------------|------------|------------|------------|----------|----------|
| flip_horizontal   |       3.61 |       0.01 |       0.01 |   247.5x |   605.3x |
| flip_vertical     |       3.62 |       0.00 |       0.00 |   794.1x |  1260.9x |
| rotate_90         |       5.00 |       0.01 |       0.01 |   337.8x |   497.2x |
| rotate_180        |       7.10 |       0.01 |       0.01 |   546.9x |  1206.3x |
| translate_paste   |      43.66 |       0.08 |       0.04 |   542.4x |  1013.6x |
| gaussian_blur_r2  |     289.40 |       0.54 |       0.02 |   540.6x | 14976.9x |
| box_blur_r2       |     403.04 |       0.19 |       0.02 |  2098.3x | 18290.0x |
| median_3x3        |     220.71 |       1.36 |       0.03 |   162.2x |  6755.1x |
| find_edges        |     200.40 |       0.37 |       0.09 |   539.5x |  2356.0x |
| convert_rgb_to_l  |      20.70 |       0.02 |       0.01 |   992.8x |  1420.3x |
| resize_half_bilin |      20.14 |       0.12 |       0.01 |   167.9x |  1448.5x |
| resize_2x_bilin   |      45.11 |       0.61 |       0.16 |    74.2x |   288.4x |
| invert            |       0.32 |       0.08 |       0.00 |     3.8x |    82.0x |
| autocontrast      |      94.76 |       0.22 |       0.00 |   435.4x | 23288.9x |
| equalize          |     150.66 |       0.20 |       0.08 |   744.7x |  1859.8x |

`vs pil` / `vs cv` show how many times **slower** imaging is; `1.0x` would be a tie.

## What to make of the numbers

- **The absolute time is small on 128×128** — every op under 110 ms — so a script that processes
  a handful of images per minute won't notice. What suffers is a script that touches thousands
  of images in a loop.
- **Kirito's vectorised paths (filters, resize, convert) are within ~100–2000× of Pillow.** That
  reflects Kirito's interpreter overhead per tensor op — the actual arithmetic runs in C, but
  every op dispatch pays for name lookup + result construction + GC roots. Pillow is C from top
  to bottom.
- **`invert` is close to Pillow** (~3.6×) because it collapses to `tensor * -1 + 255`, three
  fused element-wise ops, and both libraries bottom out in memory bandwidth. That's the shape
  of op imaging can be competitive on.
- **The 1.16 tensor engine regressed on convolution paths** (Gaussian / box / find_edges got
  ~2-4× slower than 1.12) — worth a profile pass if someone wants to optimise. Point ops (like
  `invert`) moved the OTHER way and got faster.
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

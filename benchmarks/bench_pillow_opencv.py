"""Match imaging's benchmark operations for Pillow and OpenCV.

    python3 bench_pillow_opencv.py fixture.png [reps]

Prints one TAB-separated line per (library, operation):

    pillow  OP_NAME    BEST_MS
    opencv  OP_NAME    BEST_MS

`reps` defaults to 5; we report the fastest of `reps` runs (min = the least noisy sample). Every
library reads the SAME PNG (already round-tripped through Pillow when the fixture was written),
so decode differences don't leak into the measurements -- we load once, outside the timing.
"""
import sys
import time
import os

from PIL import Image, ImageOps, ImageFilter, ImageChops
import cv2
import numpy as np

fixture = sys.argv[1] if len(sys.argv) > 1 else "fixture.png"
reps = int(sys.argv[2]) if len(sys.argv) > 2 else 5

pil = Image.open(fixture).convert("RGB")
# OpenCV wants BGR, ndarray, (H, W, C). Convert the same pixel data over.
cv_rgb = np.array(pil, dtype=np.uint8)                       # HxWx3, RGB
cv_bgr = cv_rgb[:, :, ::-1].copy()                           # HxWx3, BGR (OpenCV's native order)
print(f"pillow/opencv  {pil.width}x{pil.height} RGB  reps={reps}", file=sys.stderr)

def best_ms(fn):
    """Return the wall time (ms) of the fastest of `reps` runs of fn()."""
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter_ns()
        _ = fn()
        t1 = time.perf_counter_ns()
        best = min(best, (t1 - t0) / 1e6)
    return best

def emit(lib, op, fn):
    print(f"{lib}\t{op}\t{best_ms(fn):.6f}")

# ---- Pillow ------------------------------------------------------------------
# Pre-instantiate the parametric filters so per-call cost measures the FILTER, not the ctor.
pil_gauss = ImageFilter.GaussianBlur(radius=2)
pil_box   = ImageFilter.BoxBlur(radius=2)
pil_med   = ImageFilter.MedianFilter(size=3)

emit("pillow", "flip_horizontal",   lambda: pil.transpose(Image.FLIP_LEFT_RIGHT))
emit("pillow", "flip_vertical",     lambda: pil.transpose(Image.FLIP_TOP_BOTTOM))
emit("pillow", "rotate_90",         lambda: pil.transpose(Image.ROTATE_90))
emit("pillow", "rotate_180",        lambda: pil.transpose(Image.ROTATE_180))
# Pillow's translate = ImageChops.offset (with zero fill on the wrapped edge). Same shape as
# imaging's "paste onto blank canvas at [dx, dy]".
emit("pillow", "translate_paste",   lambda: ImageChops.offset(pil, 16, 8))
emit("pillow", "gaussian_blur_r2",  lambda: pil.filter(pil_gauss))
emit("pillow", "box_blur_r2",       lambda: pil.filter(pil_box))
emit("pillow", "median_3x3",        lambda: pil.filter(pil_med))
emit("pillow", "find_edges",        lambda: pil.filter(ImageFilter.FIND_EDGES))
emit("pillow", "convert_rgb_to_l",  lambda: pil.convert("L"))
emit("pillow", "resize_half_bilin", lambda: pil.resize((pil.width // 2, pil.height // 2), Image.BILINEAR))
emit("pillow", "resize_2x_bilin",   lambda: pil.resize((pil.width * 2, pil.height * 2), Image.BILINEAR))
emit("pillow", "invert",            lambda: ImageOps.invert(pil))
emit("pillow", "autocontrast",      lambda: ImageOps.autocontrast(pil))
emit("pillow", "equalize",          lambda: ImageOps.equalize(pil))

# ---- OpenCV ------------------------------------------------------------------
def _translate_cv(im, dx, dy):
    # cv2.warpAffine is OpenCV's canonical "translate the image" API.
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(im, M, (im.shape[1], im.shape[0]), borderValue=(0, 0, 0))

emit("opencv", "flip_horizontal",   lambda: cv2.flip(cv_bgr, 1))
emit("opencv", "flip_vertical",     lambda: cv2.flip(cv_bgr, 0))
emit("opencv", "rotate_90",         lambda: cv2.rotate(cv_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE))
emit("opencv", "rotate_180",        lambda: cv2.rotate(cv_bgr, cv2.ROTATE_180))
emit("opencv", "translate_paste",   lambda: _translate_cv(cv_bgr, 16, 8))
emit("opencv", "gaussian_blur_r2",  lambda: cv2.GaussianBlur(cv_bgr, (5, 5), 0))    # radius=2 -> ksize=5
emit("opencv", "box_blur_r2",       lambda: cv2.blur(cv_bgr, (5, 5)))
emit("opencv", "median_3x3",        lambda: cv2.medianBlur(cv_bgr, 3))
# OpenCV doesn't ship Pillow's exact FIND_EDGES kernel; the closest equivalent is the Laplacian
# with the same 3x3 -1/-1/-1, 8, -1/-1/-1 stencil (`cv2.Laplacian` with ksize=3 uses [0,1,0;1,-4,1;0,1,0]
# but with ddepth=CV_16S and per-channel; filter2D with the same kernel matches PIL).
_find_edges = np.array([[-1,-1,-1],[-1,8,-1],[-1,-1,-1]], dtype=np.int8)
emit("opencv", "find_edges",        lambda: cv2.filter2D(cv_bgr, -1, _find_edges))
emit("opencv", "convert_rgb_to_l",  lambda: cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY))
emit("opencv", "resize_half_bilin", lambda: cv2.resize(cv_bgr, (cv_bgr.shape[1] // 2, cv_bgr.shape[0] // 2), interpolation=cv2.INTER_LINEAR))
emit("opencv", "resize_2x_bilin",   lambda: cv2.resize(cv_bgr, (cv_bgr.shape[1] * 2, cv_bgr.shape[0] * 2), interpolation=cv2.INTER_LINEAR))
emit("opencv", "invert",            lambda: cv2.bitwise_not(cv_bgr))
# OpenCV: autocontrast per-channel is normalize with alpha=0, beta=255 (INF norm). Not identical
# to Pillow's cutoff-based stretch, but the same intent (map min->0, max->255 per channel).
emit("opencv", "autocontrast",      lambda: cv2.normalize(cv_bgr, None, 0, 255, cv2.NORM_MINMAX))
# OpenCV: histogram equalize is per-channel on greyscale; RGB uses equalizeHist per channel via YCrCb
def _equalize_cv(im):
    ycc = cv2.cvtColor(im, cv2.COLOR_BGR2YCrCb)
    ycc[:, :, 0] = cv2.equalizeHist(ycc[:, :, 0])
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)
emit("opencv", "equalize",          lambda: _equalize_cv(cv_bgr))

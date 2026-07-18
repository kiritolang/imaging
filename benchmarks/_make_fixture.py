"""Generate the shared benchmark fixture as a PNG on disk.

We author a deterministic pattern with a wide colour range and a clear high-frequency component,
so filter results are visually meaningful (a Gaussian blur removes the high-frequency noise, a
median filter kills salt-and-pepper spikes, ...). All three libraries load the SAME PNG, so any
differences in the reported timings come from the operation and not from decoding.

    python3 _make_fixture.py out.png [size]

`size` defaults to 256 (a 256x256 RGB image).
"""
import sys
import os

from PIL import Image
import numpy as np

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "fixture.png")
size = int(sys.argv[2]) if len(sys.argv) > 2 else 256

rng = np.random.default_rng(0xC0FFEE)
# Base gradient: R = x, G = y, B = x^y  (256 values across the whole 0..255 range on every channel).
xs = np.arange(size, dtype=np.uint16)
X, Y = np.meshgrid(xs, xs)
base = np.dstack([
    (X * 255 // (size - 1)).astype(np.uint8),
    (Y * 255 // (size - 1)).astype(np.uint8),
    ((X ^ Y) & 0xFF).astype(np.uint8),
])
# Pepper noise -- a few dozen bright/black spikes so a median filter has something to eat.
noise = rng.integers(0, size * size, size * size // 200)
flat = base.reshape(-1, 3).copy()
for i, k in enumerate(noise):
    flat[k] = (255, 255, 255) if i % 2 == 0 else (0, 0, 0)
im = Image.fromarray(flat.reshape(size, size, 3), "RGB")
im.save(out)
print(f"wrote {out}  {size}x{size} RGB, {os.path.getsize(out)} bytes")

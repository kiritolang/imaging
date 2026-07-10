# imaging — a Pillow-style image library in pure Kirito

A from-scratch image-processing library written entirely in Kirito (`.ki`), in the spirit of
[Pillow](https://python-pillow.org/) (PIL). Pixels are stored in a **`tensor`** of shape
`(height, width, channels)`, and the `tensor` standard library is the numerical backend: every
conversion, geometric transform, point operation and convolution filter is expressed as a vectorised
tensor operation rather than a per-pixel loop.

It is both a useful library and a substantial example program — and building it surfaced and fixed a
real interpreter bug (a GC-rooting gap in `tensor.tolist()` for Float tensors; see the repo history).

> Performance note: this runs on the Kirito interpreter, so work that is unavoidably per-pixel in
> Kirito (PNG un-filtering, `getpixel`/`putpixel` loops, histogram passes) is slow. Keep images
> modest (a few hundred pixels per side). The heavy numeric paths — conversions, resizing, flips and
> all the convolution filters — run through bulk tensor ops and stay fast.

## Install

It's a normal Kirito package. With `kpm` (the package manager) it installs straight from GitHub:

```
kpm install kiritolang/imaging
```

That drops the package into `~/.kirito/packages/imaging/` and puts its modules on the import path.
The public surface lives in the `img/` directory namespace (`ki` resolves `import("img/name")`
to `img/name.ki` under any dir on the import path):

```kirito
var Image      = import("img/image")     # the Image class + open/save/new/blend/merge
var ImageOps   = import("img/ops")       # ImageOps: invert, grayscale, autocontrast, ...
var ImageFilter = import("img/filter")   # convolution + rank filters
var ImageDraw  = import("img/draw")      # drawing primitives
var cv         = import("img/video")     # OpenCV-style VideoCapture
```

The three internal codecs (`img/_jpeg`, `img/_gif`, `img/_ffmpeg`) are private by convention —
their leading underscore says "not for direct use", reach them via `Image.open(...)` /
`Image.save(...)` / the video reader.

Pin a version or track a branch by appending `@ref`:

```
kpm install kiritolang/imaging@^1.5.0    # highest 1.x
kpm install kiritolang/imaging@main      # tip of main
```

In *this* repository you can run the scripts in place, because a script's own directory is on the
import path:

```
ki demo.ki          # writes a gallery of PNGs to the temp dir
ki test_imaging.ki  # the self-test (asserts; prints ALL TESTS PASSED)
```

## Layout

```
kirito.json             the kpm manifest (name/version/modules)
img/image.ki            Image class + new/open/save/fromtensor/merge/blend + PNG/PPM/PGM/BMP codecs
img/ops.ki              ImageOps: invert/grayscale/mirror/flip/posterize/solarize/autocontrast/equalize/...
img/filter.ki           ImageFilter: convolution kernels (BLUR/SHARPEN/...) + Gaussian/Box/rank filters
img/draw.ki             ImageDraw: point/line/rectangle/ellipse/polygon (mutating primitives)
img/video.ki            VideoCapture: MJPEG/GIF/Y4M/image-sequence/HTTP-MJPEG natively + MP4/H.264/RTSP via ffmpeg
img/_jpeg.ki            (internal) baseline JPEG decoder (Huffman + tensor IDCT + YCbCr->RGB)
img/_gif.ki             (internal) GIF87a/89a decoder (LZW + palette + animation compositing)
img/_ffmpeg.ki          (internal) ffmpeg subprocess wrapper (JPEG encode, MP4/RTSP transcode)
demo.ki / demo_video.ki tours that produce real PNGs / extract video frames
test_imaging.ki / test_video.ki   the self-tests (asserts; the nightly workflow runs both)
tests/                  per-symbol test suite (auto-discovered by tools/scripts/run_tests.sh)
compare_pillow.py / compare_video_pillow.py   pixel-for-pixel cross-validation against Pillow
testdata/               tiny committed MJPEG + GIF assets the video self-test decodes
```

## Quick start

```kirito
var io = import("io")
var Image = import("img/image")
var ImageFilter = import("img/filter")
var ImageOps = import("img/ops")

var im = Image.open("photo.png")        # PNG / PPM / PGM / BMP, sniffed from the header
io.print(im.mode, im.size)              # e.g. RGB [640, 480]

var small = im.resize([128, 96], Image.BILINEAR).convert("L")
var edges = small.filter(ImageFilter.FIND_EDGES)
ImageOps.autocontrast(edges).save("edges.png")
```

The module object *is* the `Image` namespace, so it reads just like `from PIL import Image`:
`Image.new(...)`, `Image.open(...)`, plus the `Image.FLIP_LEFT_RIGHT` / `Image.ROTATE_90` /
`Image.BILINEAR` constants.

## The `Image` class

| method | description |
|---|---|
| `Image.new(mode, size[, color])` | a blank image; `mode` is `"L"`/`"RGB"`/`"RGBA"`, `size` is `[w, h]` |
| `Image.open(path)` / `Image.frombytes(bytes)` | decode a file / an in-memory blob (format sniffed) |
| `img.save(path[, format])` / `img.tobytes(format)` | encode as PNG/PPM/PGM/BMP (by extension or explicit) |
| `img.size` / `img.width` / `img.height` / `img.mode` | dimensions and pixel mode |
| `img.getpixel([x, y])` / `img.putpixel([x, y], v)` | read / write one pixel (`putpixel` mutates) |
| `img.convert(mode)` | `L`↔`RGB`↔`RGBA` (RGB→L uses Pillow's ITU-R 601-2 luma) |
| `img.crop([l, u, r, b])` | a sub-image (right/lower exclusive) |
| `img.resize([w, h][, resample])` | `NEAREST` (default) or `BILINEAR` |
| `img.thumbnail([w, h])` | shrink to fit, preserving aspect ratio |
| `img.transpose(method)` | `FLIP_LEFT_RIGHT`/`FLIP_TOP_BOTTOM`/`ROTATE_90`/`180`/`270`/`TRANSPOSE`/`TRANSVERSE` |
| `img.rotate(angle)` | a multiple of 90° (counter-clockwise, Pillow's convention) |
| `img.paste(other, [x, y])` | composite another image in place |
| `img.point(fn)` | remap every channel value through `fn` (via a 256-entry LUT) |
| `img.split()` / `Image.merge(mode, bands)` | separate / recombine channels |
| `img.histogram()` | per-channel 256-bin histogram |
| `img.filter(flt)` | apply an `img/filter` (see below) |
| `img.tensor()` / `Image.fromtensor(t, mode)` | the **tensor bridge** — drop to raw `(H,W,C)` and back |
| `img.tolist()` | a nested List of Integer pixels |
| `Image.blend(a, b, alpha)` | linear cross-fade of two same-size images |

## ImageOps, ImageFilter, ImageDraw

```kirito
var ImageOps = import("img/ops")
# invert, grayscale, mirror, flip, posterize(bits), solarize(threshold), autocontrast(cutoff),
# equalize, expand(border, fill), colorize(black, white), scale(factor), fit(size)

var ImageFilter = import("img/filter")
# kernels: BLUR, SHARPEN, SMOOTH, SMOOTH_MORE, DETAIL, EDGE_ENHANCE(_MORE), FIND_EDGES, EMBOSS, CONTOUR
# parametric: GaussianBlur(radius), BoxBlur(radius), MedianFilter(size), MinFilter(size), MaxFilter(size)
# custom:     Kernel(size, flat_kernel[, scale[, offset]])

var ImageDraw = import("img/draw")
var d = ImageDraw.Draw(img)
d.line([0, 0, 99, 99], [255, 0, 0])
d.rectangle([10, 10, 40, 30], [0, 0, 80], [255, 255, 0])   # fill, outline
d.ellipse([20, 20, 60, 50], [0, 128, 0])
d.polygon([5, 5, 60, 8, 30, 55], [80, 80, 80], [200, 200, 200])
```

Convolution filters are the showcase of the tensor backend: an image is edge-padded once, then for
each of the kernel's *K×K* taps the **whole** shifted window is scaled and accumulated — `K*K`
vectorised tensor operations, no per-pixel loop. Rank filters (`Min`/`Max`/`Median`) stack the
shifted windows and reduce along the new axis.

## The tensor backend, and a note on mutation

`img.tensor()` hands you the underlying `(H, W, C)` Float tensor, so you can compute with the full
`tensor` library and wrap the result back with `Image.fromtensor(t, mode)`:

```kirito
var T = import("tensor")
var d = img.tensor()
# boost contrast around mid-grey, purely in tensor ops
var stretched = ((d + (-128.0)) * 1.4 + 128.0).clip(0.0, 255.0)
var out = Image.fromtensor(stretched, img.mode)
```

Kirito tensors are **immutable** under arithmetic — every op returns a new tensor. The one in-place
operation is element assignment (`t[i, j] = v`), and that is exactly what `putpixel`, `paste` and the
`ImageDraw` primitives use, so they can mutate an image in place like Pillow. Everything else
(`convert`, `crop`, `resize`, `filter`, the `ImageOps`) is functional and returns a **new** image.

## Formats

| format | read | write | notes |
|---|---|---|---|
| PNG | ✓ | ✓ | 8-bit, colour types 0/2/6 (L/RGB/RGBA); decodes all five scanline filters incl. Paeth; zlib via the stdlib |
| PPM/PGM | ✓ | ✓ | binary Netpbm (P6/P5); handles `#` comments on read |
| BMP | ✓ | ✓ | 24-bit uncompressed, bottom-up BGR |
| JPEG | ✓ | ✓* | decode: baseline (sequential-DCT, Huffman); grey + YCbCr 4:4:4/4:2:2/4:2:0, restart markers (`img/_jpeg.ki`). encode: `.save("x.jpg")` / `.tobytes("jpeg")`, quality 0..100 (default 90), via ffmpeg subprocess (`img/_ffmpeg.ki`). |
| GIF | ✓ | — | GIF87a/89a, static + animated (LZW, palette, interlace, transparency, disposal) (`img/_gif.ki`) |

`✓*` = requires an `ffmpeg` binary on `PATH` at runtime (or `$IMG_FFMPEG`). Everything else is pure Kirito with no external dependency.

PNG is the interesting one: encoding writes signature + IHDR + zlib-compressed filtered scanlines +
IEND, with CRC-32 per chunk (both from the `zlib` and `hash` stdlib modules); decoding parses the
chunks, inflates the IDAT stream and reverses the per-row filters into a tensor. JPEG decoding adds a
full baseline pipeline — Huffman entropy decode, dequantise, an 8×8 inverse DCT (as two `tensor`
matmuls per block) and a vectorised YCbCr→RGB — which is what makes MJPEG video readable.

**JPEG encoding is delegated to a local `ffmpeg` binary via `sys.createprocess`.** A pure-Kirito
JPEG encoder (Huffman-table construction + baseline sequential quantisation) is heavier than the
decoder and duplicates what every ffmpeg install already ships — and once we depend on ffmpeg for
compressed video anyway, one dependency covers both. If ffmpeg is not on `PATH`, the JPEG save
paths throw a clear error pointing at how to install it; the other formats keep working.

## Video — an OpenCV-style `VideoCapture`

`img/video.ki` reads video as a sequence of frames, in the spirit of `cv2.VideoCapture`, from every
source it can reach — the pure-Kirito backends (MJPEG / GIF / Y4M / image-sequence / HTTP-MJPEG)
plus an ffmpeg-backed path for **compressed video and RTSP** (MP4 / MKV / MOV / AVI / WebM / FLV /
TS / H.264 / HEVC / AV1 / RTSP / RTMP …):

```kirito
var cv = import("img/video")

# Pure-Kirito backends -- no external dependency.
var cap = cv.VideoCapture("clip.mjpeg")            # or "anim.gif", "clip.y4m",
                                                    #    "frames/f_%04d.png", or
                                                    #    "http://camera/stream" (MJPEG-over-HTTP)

# ffmpeg-backed backends -- require an `ffmpeg` binary on PATH.
var mp4 = cv.VideoCapture("in.mp4")                #    file: transcoded to MJPEG at open()
var rtsp = cv.VideoCapture("rtsp://cam/stream",    #    live: capped at duration seconds
                           duration = 30)          #          (default 30 s for rtsp:// / rtmp://)

io.print(cap.get(cv.CAP_PROP_FRAME_COUNT), cap.width, cap.height, cap.get(cv.CAP_PROP_FPS))
var frame = cap.read()                              # -> Image, or None at end-of-stream
while frame != None:
    discard frame.filter(import("img/filter").FIND_EDGES)
    frame = cap.read()
cap.release()

# Or the iterator, which unwraps for you:
for frame in cap:
    discard frame.filter(import("img/filter").FIND_EDGES)
```

`read()` returns an `img/image` `Image` on success and `None` at end-of-stream — that reads
naturally as `while frame != None:` or as a `for frame in cap:` iterator. OpenCV's older
`[ok, frame]` tuple shape is intentionally NOT what we return; the `None` sentinel is easier to
work with in Kirito. `grab()` (advance without decoding, returns Bool) and `retrieve()` (return
the last `grab()`'d Image, or None) are still exposed for the seek-fast cases. Every capture also
carries `.kind` (the container type — `"mjpeg"` / `"gif"` / `"y4m"` / `"seq"` / `"http"`) and
`.backend` (`"native"` for the pure-Kirito paths, `"ffmpeg"` when we transcoded) so a program can
tell how a source is being decoded, plus the usual `isopened` / `release` / `get` / `set` with
the `CAP_PROP_*` ids (random-access seek on file backends).

> **MP4 / H.264 / RTSP** are handled by transcoding the source into an in-memory MJPEG buffer at
> `open()` time (via `sys.createprocess(binary=True)` piping bytes through ffmpeg — no disk
> staging), then reading that with the native MJPEG backend. This works because `ffmpeg` is a
> synchronous one-shot — Kirito has no async subprocess to keep an ffmpeg pipe alive across
> `grab()`s. For a live RTSP camera pass `duration=…` to control how many seconds get captured
> (default 30 s). If `ffmpeg` is not installed, the ffmpeg-backed backends throw a clear error;
> the pure-Kirito backends keep working with zero external dependency.

## Cross-validation against Pillow

`compare_pillow.py` proves the output is genuinely compatible: it has the Kirito side write a base
image and a set of operation results, then re-computes the same operations with Pillow and asserts a
**pixel-exact** match (a one-count tolerance only for the greyscale luma rounding). It also has
Pillow author adaptively-filtered PNGs (RGB/RGBA/L) and checks that Kirito decodes them exactly.
`compare_video_pillow.py` does the same for video — Pillow authors JPEG / animated-GIF / MJPEG / Y4M /
image-sequence assets (and serves a local MJPEG-over-HTTP stream), and the Kirito `VideoCapture`
decodes each: GIF and the image sequence match **exactly**, JPEG/MJPEG/Y4M within a ±3 tolerance
(float-vs-integer IDCT and chroma upsampling).

```
pip install pillow
python3 compare_pillow.py        # images
python3 compare_video_pillow.py   # video
# -> CROSS-VALIDATION PASSED -- Kirito imaging matches Pillow
```

## Serialization & inspection

Because an `Image` is an ordinary Kirito class wrapping a (serializable) tensor and a string, it
round-trips through both `serialize` (text) and `dump` (binary) with no extra work, and `inspect(img)`
lists its full method surface — the same guarantees every Kirito value carries.

## Performance vs Pillow / OpenCV

`benchmarks/run.sh` times a common set of operations (flips, rotate, translate, Gaussian/box/median
filters, resize, convert, autocontrast, equalize, invert) against Pillow and OpenCV on the same PNG
fixture. Sample numbers on 128×128 RGB with `ki 1.12.1` — see `benchmarks/README.md` for the full
table and methodology:

| operation         | imaging (ms) | Pillow (ms) | OpenCV (ms) | vs Pillow | vs OpenCV |
|-------------------|-------------:|------------:|------------:|----------:|----------:|
| flip_horizontal   |         1.58 |        0.01 |        0.00 |     145x |     523x  |
| rotate_180        |         3.18 |        0.01 |        0.00 |     332x |    1033x  |
| gaussian_blur_r2  |       105.49 |        0.39 |        0.03 |     269x |    3254x  |
| median_3x3        |       103.44 |        0.95 |        0.02 |     109x |    4874x  |
| resize_2x_bilin   |        81.33 |        0.42 |        0.08 |     195x |    1037x  |

Reads: absolute times are small at 128 px per side (every op under ~110 ms), but the gap widens
linearly with pixel count and quickly with kernel size. Kirito interprets the top of every tensor
op while Pillow and OpenCV are compiled C/C++ — the vectorised paths (filters, resize, convert)
stay within ~100–500× of Pillow because the arithmetic runs in the C tensor backend; flips are
closer because they collapse to a single memcpy on all three sides. Use imaging when the pixel
count is modest and the code should stay in one language; reach for Pillow/OpenCV via `sys.createprocess`
if you need to hammer millions of pixels.

Run it yourself:

```
pip install pillow opencv-python-headless numpy
benchmarks/run.sh                # 128x128, best of 5
benchmarks/run.sh 256 10         # 256x256, best of 10
```

## Limitations (room to grow)

- 8-bit channels only (no 16-bit / float-HDR images); palette PNGs (colour type 3) aren't decoded.
- `rotate` covers 90° multiples only; arbitrary-angle resampling isn't implemented.
- JPEG **decode** is baseline-only (progressive/arithmetic are rejected); chroma is upsampled
  nearest-neighbour, so subsampled JPEGs differ from libjpeg's "fancy" upsampling by a few counts
  at colour edges. JPEG **encode** and the compressed-video / RTSP backends need `ffmpeg` on `PATH`
  at runtime (or `$IMG_FFMPEG`) — no in-process encoder.
- No GIF *encoder*.
- The ffmpeg-backed video path transcodes to a MJPEG temp file at `open()` and reads back through
  the native MJPEG backend — a live RTSP stream is capped by `duration=`, defaulting to 30 s.
- No text rendering (Pillow's `ImageFont`).
- `GaussianBlur` is a true discrete Gaussian rather than Pillow's box-approximation, so blurred
  output is visually equivalent but not bit-identical.

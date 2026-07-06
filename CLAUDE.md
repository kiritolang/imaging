# CLAUDE.md - Claude Code Instructions (imaging)

**Read this file in full at the start of every session before doing anything else.** This repo is
the `imaging` package — a pure-Kirito, Pillow-style image + video library. It runs on the standalone
`ki` interpreter; there is **no C++ in this repo**.

## Hard rule: never touch the interpreter repo

Under **no circumstances** may you make, commit, or push edits to
[`kiritolang/kiritolang.github.io`](https://github.com/kiritolang/kiritolang.github.io) from this
repo — not to its source, not to its tests, not to its docs, not to its CI, not to any file it owns.
That repo is the Kirito interpreter (`ki`) itself and is out of scope for this project. If a bug in
the interpreter surfaces here, report it and work around it — do not "fix" it upstream from this
side. This applies even if you happen to have a local clone of `kiritolang.github.io` on disk:
treat it as read-only reference material only.

The one exception: **reading** the interpreter's docs and headers for reference is fine and
encouraged (see the Reference section below). Reading is not editing.

## The Kirito language — reference

The interpreter's own documentation is the source of truth for the language, the standard library,
and `kpm`:

- **Docs (Markdown source):** https://github.com/kiritolang/kiritolang.github.io/tree/main/docs
- **Docs (rendered site):** https://kiritolang.github.io/

Both go to the same content; when you need to look up a builtin (`import`, `inspect`, `isinstance`,
`hasattr`, ...), a standard-library module (`io`, `path`, `tensor`, `zlib`, `hash`, `net`, `math`,
`serialize`, `dump`, ...), or a language rule (indentation, unpacking, exceptions, class model,
special methods like `_init_`/`_str_`/`_getitem_`), start there. Do **not** guess syntax or
behaviour from Python analogy — Kirito's dunder names use *single* underscores, `catch`/`throw`
replace `except`/`raise`, `Function(...):` declares a callable, and so on.

## Git

**ONLY commit and push to `claude-branch`.** That branch is Claude's own scratch branch and the
only place Claude's work lives while it is in flight; pushing to `main` (or any other branch) is
forbidden. The cycle is: base `claude-branch` off the current `main`, do the work, open a pull
request, wait for the human to merge; on the next task, restart `claude-branch` from `main` again.

```sh
git fetch origin main
git checkout -B claude-branch origin/main
```

A `PreToolUse` hook (`.claude/hooks/enforce_claude_branch.py`, wired in `.claude/settings.json`)
enforces this — it blocks any `git commit` off `claude-branch` and any `git push` that touches
`main` or leaves `claude-branch`. If it fires, switch back to `claude-branch` and retry, do not
bypass.

Opening and updating a pull request from `claude-branch` is fine; no other GitHub write is.

## What this repo is

`imaging` is a Pillow (PIL)-style image library plus an OpenCV-style `VideoCapture`, written
entirely in Kirito (`.ki`), built on the interpreter's `tensor` standard library. Pixels are a
`(H, W, C)` Float `tensor`; conversions, resizes, filters and point ops are vectorised tensor
operations rather than per-pixel loops.

### Module layout (namespace)

Kirito's import path resolves `import("a/b")` to `a/b.ki` on any dir on the import path, so we
layer the package under an `img/` directory. Two tiers:

- **`img/*`** — the public surface. Each module is imported directly:
  - `img/image` — the `Image` class + `open`/`save`/`new`/`fromtensor`/`merge`/`blend` +
    PNG/PPM/PGM/BMP codecs (and JPEG save when ffmpeg is available).
  - `img/ops` — Pillow-style `ImageOps` (invert, grayscale, autocontrast, equalize, ...).
  - `img/filter` — convolution + rank filters (`BLUR`, `SHARPEN`, `GaussianBlur(r)`, ...).
  - `img/draw` — 2-D drawing primitives (line/rectangle/ellipse/polygon).
  - `img/video` — an OpenCV-style `VideoCapture` (MJPEG/GIF/Y4M/image-sequence/HTTP-MJPEG in pure
    Kirito; MP4 / H.264 / HEVC / AV1 / RTSP / RTMP via ffmpeg transcode).
- **`img/_*`** — internal modules, marked by a leading underscore inside the same directory. This
  is a private-by-convention marker, NOT a language-level access check; the convention is that a
  user's program never types a module path with a `_` component. Reach these only via
  `img/image.open(...)` / `img/image.save(...)` / `img/video`.
  - `img/_jpeg` — baseline JPEG decoder (pure Kirito).
  - `img/_gif` — GIF87a/89a decoder (pure Kirito).
  - `img/_ffmpeg` — subprocess wrapper for the external `ffmpeg` binary. All JPEG encode and
    compressed-video / RTSP paths go through here. If ffmpeg is not on `PATH` (or `$IMG_FFMPEG`),
    the ffmpeg-backed paths throw a clear installation message; every pure-Kirito path keeps
    working with no external dependency.

**Rule:** anything that is not a supported public entry point goes under `img/_*.ki`. A user's
program should only ever type module paths of the form `img/<name>` with no leading underscore on
the last component.

_Historical note: releases up through 1.3.x used a flat namespace (`img_image`, `_img_o6769_jpeg`,
…) because `import` didn't accept slashes. `ki 1.12+` supports directory imports, so `img_*.ki` was
folded into `img/*.ki`. The internal `_img_o6769_` random-suffix mangling was there to avoid a
flat-namespace clash with sibling packages, which the `img/` directory already gives us._

### Optional runtime dependency: `ffmpeg`

`ffmpeg` is **optional** but required to enable two feature groups:

- **JPEG encoding** — `Image.save("*.jpg")` and `.tobytes("jpeg", quality=…)`.
- **Compressed video** — MP4 / MKV / MOV / AVI / WebM / FLV / TS / H.264 / HEVC / AV1 sources, plus
  RTSP / RTMP live streams, opened through `img/video.VideoCapture(...)`.

The subprocess is spawned via `sys.createprocess`. Because `sys.createprocess` decodes stdout as
UTF-8 (mangling binary), everything routes through temp files (`io.open(...,"rb"/"wb")`) rather
than pipes — see `img/_ffmpeg.ki`.

### Style

- Public identifiers in Kirito use **lowercase, no underscores** (`putpixel`, `getbbox`,
  `filter`, `resize`, `frombytes`, `tobytes`) — same convention as the interpreter's own stdlib.
- Comments explain **why**, not what. If a comment is only describing what the code does, delete it
  and improve the name instead.
- Every new function/method/attribute gets a test in the same change (see `tests/` and the
  post-work checklist). Every fixed bug gets a regression test.

## Post-work check

See `.claude/POST_WORK_CHECKLIST.md`. Short version: run `tools/scripts/run_tests.sh`, which
downloads the latest `ki` release binary and runs every test script in the repo. A change is done
only when it prints `ALL GREEN` and every test file's last line is `ALL TESTS PASSED`. The same
suite is run by the nightly workflow at 03:00 UTC.

## Keep this file current

When a decision changes the package layout, module naming rules, git policy, or test workflow,
update this file in the same change. It must always describe imaging as it *is*.

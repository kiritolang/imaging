#!/usr/bin/env bash
# Run the imaging vs Pillow vs OpenCV benchmark and print a comparison table.
#
#   benchmarks/run.sh                # 128x128, 5 reps
#   benchmarks/run.sh 256 10         # 256x256, 10 reps
#   KI=/path/to/ki benchmarks/run.sh # override the ki binary (else /tmp/ki, else fetched)
#
# All three implementations decode the SAME PNG fixture, run each operation `reps` times, and
# report the fastest (min) wall time. Kirito timings come from time.perfcounterns(); Python
# uses time.perf_counter_ns(). The comparison isn't apples-to-apples down to the microsecond
# -- Kirito is a tree-walked interpreter, Pillow is C, OpenCV is heavily-vectorised C++ -- but
# it's a fair one-to-one on what an application programmer sees: same input, same output shape,
# same intent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH_DIR="$REPO_ROOT/benchmarks"
cd "$REPO_ROOT"

SIZE="${1:-128}"
REPS="${2:-5}"
KI="${KI:-/tmp/ki}"

if [ ! -x "$KI" ]; then
    echo "==> downloading latest ki release into $KI" >&2
    curl -fsSL -o "$KI" \
        https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64
    chmod +x "$KI"
fi

# Prereq check: Pillow + OpenCV + numpy in the Python env we'll use.
python3 - <<'PY' >/dev/null 2>&1 || { echo "install: pip install pillow opencv-python-headless numpy" >&2; exit 1; }
import PIL, cv2, numpy
PY

echo "==> ki $($KI --version 2>&1 | head -1 | sed 's/ki //')  vs  Pillow $(python3 -c 'import PIL; print(PIL.__version__)')  vs  OpenCV $(python3 -c 'import cv2; print(cv2.__version__)')" >&2
echo "==> fixture ${SIZE}x${SIZE} RGB, reps=$REPS" >&2

FIXTURE="$BENCH_DIR/fixture.png"
python3 "$BENCH_DIR/_make_fixture.py" "$FIXTURE" "$SIZE" >&2

# Collect all three streams into one temp file: `LIB\tOP\tMS`.
TMP="$(mktemp -t imaging_bench_XXXXXX)"
trap 'rm -f "$TMP"' EXIT
"$KI" "$BENCH_DIR/bench_imaging.ki" "$FIXTURE" "$REPS" >>"$TMP" 2>&1 || {
    echo "kirito bench failed" >&2; cat "$TMP" >&2; exit 1; }
python3 "$BENCH_DIR/bench_pillow_opencv.py" "$FIXTURE" "$REPS" >>"$TMP" 2>&1 || {
    echo "python bench failed" >&2; cat "$TMP" >&2; exit 1; }

# Pivot to columns and print a Markdown-ish table.
python3 - "$TMP" <<'PY'
import sys, collections
lines = [l for l in open(sys.argv[1]).read().splitlines()
         if "\t" in l and not l.startswith(("imaging  ", "pillow/opencv"))]
data = collections.defaultdict(dict)                    # op -> {lib: ms}
for line in lines:
    lib, op, ms = line.split("\t")
    data[op][lib] = float(ms)

# Preserve the natural insertion order (imaging.ki emits its list, Pillow follows the same).
ordered_ops = list(dict.fromkeys(l.split("\t")[1] for l in lines))
LIBS = ["imaging", "pillow", "opencv"]

# Width auto-fit.
w_op = max(len("operation"), max(len(o) for o in ordered_ops))
w_col = 10
def cell(x): return f"{x:>{w_col}}" if isinstance(x, str) else f"{x:>{w_col}.2f}"

print(f"| {'operation':<{w_op}} | {' | '.join(cell(l) for l in LIBS)} | {'vs pil':>8} | {'vs cv':>8} |")
print(f"|-{'-'*w_op}-|-{('|'.join('-'*(w_col+2) for _ in LIBS))[1:-1]}-|-{'-'*8}-|-{'-'*8}-|")
for op in ordered_ops:
    row = [data[op].get(l, float('nan')) for l in LIBS]
    ki_ms, pil_ms, cv_ms = row
    vs_pil = f"{ki_ms/pil_ms:>7.1f}x" if pil_ms else "  n/a"
    vs_cv  = f"{ki_ms/cv_ms:>7.1f}x"  if cv_ms  else "  n/a"
    cells = " | ".join(cell(x) for x in row)
    print(f"| {op:<{w_op}} | {cells} | {vs_pil:>8} | {vs_cv:>8} |")
print()
print("times are wall-clock ms per operation (best of the run); "
      "vs pil / vs cv show how many times SLOWER imaging is (1.0x = tied, 10x = 10 times slower).")
PY

#!/usr/bin/env bash
# Run every test script in this repo against a fresh release build of `ki`.
#
#   tools/scripts/run_tests.sh              # download ki if missing, run all tests + demos
#   tools/scripts/run_tests.sh --refresh    # re-download ki even if /tmp/ki exists
#   tools/scripts/run_tests.sh --no-demos   # skip demo.ki / demo_video.ki (faster inner loop)
#   KI=/path/to/ki tools/scripts/run_tests.sh   # use a specific interpreter
#
# Contract for a test file: exits 0 AND prints `ALL TESTS PASSED` as its last line. A missing
# marker is an error even if the script exits 0 -- that is how a silently truncated run is caught.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

KI="${KI:-/tmp/ki}"
REFRESH=0
RUN_DEMOS=1
for arg in "$@"; do
    case "$arg" in
        --refresh)  REFRESH=1 ;;
        --no-demos) RUN_DEMOS=0 ;;
        -h|--help)  sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "run_tests.sh: unknown option '$arg'" >&2; exit 2 ;;
    esac
done

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

# -------- interpreter --------
if [ ! -x "$KI" ] || [ "$REFRESH" = "1" ]; then
    say "downloading latest ki release into $KI"
    curl -fsSL -o "$KI" \
        "https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64"
    chmod +x "$KI"
fi
say "using $($KI --version)"

# -------- test discovery --------
# A test is either:
#   - any .ki file under tests/, OR
#   - a top-level test_*.ki  (test_imaging.ki, test_video.ki -- the historical two).
# Order is stable (sorted); a helper file starting with `_` is not a test on its own.
declare -a TESTS=()
if [ -d tests ]; then
    while IFS= read -r -d '' f; do
        base="$(basename "$f")"
        case "$base" in _*) continue ;; esac
        TESTS+=("$f")
    done < <(find tests -type f -name '*.ki' -print0 | sort -z)
fi
while IFS= read -r -d '' f; do TESTS+=("$f"); done \
    < <(find . -maxdepth 1 -type f -name 'test_*.ki' -print0 | sort -z)

if [ "${#TESTS[@]}" -eq 0 ]; then
    err "no test scripts found (looked under tests/ and ./test_*.ki)"
    exit 2
fi

# -------- run --------
FAIL=0
for t in "${TESTS[@]}"; do
    say "running $t"
    out="$("$KI" "$t" 2>&1)" || { err "$t exited non-zero"; echo "$out" | tail -30 >&2; FAIL=$((FAIL+1)); continue; }
    if ! printf '%s\n' "$out" | tail -1 | grep -q 'ALL TESTS PASSED'; then
        err "$t did not print 'ALL TESTS PASSED' on its last line"
        echo "$out" | tail -10 >&2
        FAIL=$((FAIL+1)); continue
    fi
    # bubble up the test's own summary lines to stdout
    printf '%s\n' "$out" | tail -3
done

# -------- demos as smoke tests --------
if [ "$RUN_DEMOS" = "1" ]; then
    for d in demo.ki demo_video.ki; do
        [ -f "$d" ] || continue
        say "smoke: $d"
        if ! "$KI" "$d" >/dev/null 2>&1; then
            err "$d failed"
            FAIL=$((FAIL+1))
        fi
    done
fi

if [ "$FAIL" -ne 0 ]; then
    err "$FAIL failure(s)"
    exit 1
fi
say "ALL GREEN (${#TESTS[@]} test file(s))"

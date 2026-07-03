# Post-work checklist

The routine to run **after every change, before declaring it done**. This is a pure-Kirito library —
no C++, no CMake — so the check is: run every test script under a freshly-downloaded release
build of the `ki` interpreter and confirm each one prints `ALL TESTS PASSED`.

## The routine

1. **Add or update tests for what changed.** Every new function/method/attribute and every fixed bug
   gets a focused check in `tests/`. Prefer many small tests over one big one:
   - Happy path (typical usage).
   - Edge cases (empty input, 1-pixel image, out-of-range indices, extreme sizes, ...).
   - Adversarial input (malformed PNG/JPEG/GIF bytes, negative sizes, unknown modes, ...).
   - Improper usage (calling a method on the wrong type, missing required args, ...).
   Every `.ki` under `tests/` is expected to exit `0` and print `ALL TESTS PASSED` as its last line.

2. **Fetch the current release binary.** The library targets whatever version of `ki` is currently
   published — it is not tied to any WIP interpreter branch:

   ```sh
   curl -fsSL -o /tmp/ki https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64
   chmod +x /tmp/ki
   /tmp/ki --version           # sanity-check that it ran
   ```

   `tools/scripts/run_tests.sh` does this for you (skips the download if `/tmp/ki` already exists;
   pass `--refresh` to force a re-download).

3. **Run the whole suite** against that binary:

   ```sh
   tools/scripts/run_tests.sh
   ```

   The script auto-discovers every `.ki` file under `tests/` and every top-level `test_*.ki` (so a
   new test file is picked up without editing the script), runs each one under the release binary,
   and fails loudly on the first non-zero exit or missing `ALL TESTS PASSED` marker. It also runs
   `demo.ki` and `demo_video.ki` as smoke tests — a demo that no longer runs is a regression too.

4. **Commit + push.** Once every check is green (`ALL GREEN`), commit and push to `claude-branch`
   (see `CLAUDE.md`'s `## Git` section; the `.claude/hooks/enforce_claude_branch.py` hook enforces
   it). The nightly workflow (`.github/workflows/nightly.yml`) reruns the same suite at 03:00 UTC on
   `main` against whatever the current release binary is — so a release of `kiritolang.github.io`
   that regresses us shows up there without any change here.

## Not in scope

- **No C++ build**, no `cmake`/`ninja`, no `ctest`, no sanitizer variants. Those live in the
  interpreter repo (`kiritolang.github.io`) and are that project's responsibility. Under no
  circumstances edit or commit anything to `kiritolang.github.io` from this repo — see the top of
  `CLAUDE.md`.
- **No Pillow cross-validation** in the required check. `compare_pillow.py` /
  `compare_video_pillow.py` are useful ancillary tools (they need `pip install pillow`), but a run
  here is not gated on them.

## What "green" means

- `run_tests.sh` exits `0`.
- Every script printed `ALL TESTS PASSED` on its last line.
- `demo.ki` and `demo_video.ki` ran to completion.
- No script produced stray output on stderr (a warning line is an error to investigate).

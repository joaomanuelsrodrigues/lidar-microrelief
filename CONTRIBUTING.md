# Contributing

These are the process rules this repository holds to. They are not the science: the science is in
`RUBRIC.md`, `CALIBRATIONS.md` and `ATTRIBUTION.md`.

## Rules

1. **Test first.** RED, GREEN, REFACTOR. No production code before a failing test exists for it.
2. **Refusal over guessing.** When an input is ambiguous, out of range, or otherwise cannot be
   processed with a defensible answer, the pipeline refuses explicitly and puts the reason in the
   message. It never silently guesses or falls back to a plausible looking default.
3. **CRS is never inferred.** Any code that touches geometry or a raster or point cloud CRS must
   verify it explicitly and reproject as needed. If the CRS is ambiguous or missing, refuse rather
   than assume.
4. **Every hardcoded number is declared.** A new threshold or magic constant lands in
   `CALIBRATIONS.md` in the same commit that introduces it, with its value, where it is used, its
   origin, and what would replace it with an empirical calibration.
5. **No credentials in this repository, ever.** No tracked `.env` file, no tokens, no keys, not
   even placeholders. Data source credentials, if ever needed, live outside the tracked tree.
   `.gitignore`'s `.env*` is where a local one may sit, and `scripts/neutrality.sh` refuses any
   tracked file the **staged** root `.gitignore` excludes, by git's own evaluation of that copy.
   So a force added `.env`, `.env-prod` or `.env/secret` at any depth is caught; a `!` negation
   there exempts by design; nested `.gitignore` files are not consulted; and the line `.env*` must
   be present or the gate refuses to run.
6. **Mocked tests prove wiring, not behaviour.** Any reader or client that touches a real file or a
   real network endpoint is unvalidated until it has been exercised end to end against the real
   source at least once, with the result recorded.
7. **The gate is `.github/workflows/ci.yml`, not a remembered command.** It runs the commands
   listed under *Commands* below: lint, format, types, tests, the version bump guard and the
   neutrality scan over tracked files. Run all of them before calling a change clean. Invoke each
   binary by path (`.venv/bin/ruff`, never a bare name, which can resolve to a shell function and
   diverge from the runner in silence), and report each exit code separately, because `&&` hides
   which step failed. Where a check's silence is its pass condition, prove it can still fail: a
   check that scanned nothing exits 0 exactly like a check that found nothing.
8. **No private identifiers in the live files.** Working notes from wherever a change was drafted
   stay out of the files a reader acts on: no session numbers, no internal task, finding or
   experiment identifiers, no `Task <n>` or `Session <n>` plan references.
   `tests/test_no_private_ids.py` enforces this over every tracked text file outside
   **`docs/judge/`**, which is exempt because those files are an outside reviewer's own words at a
   fixed commit, quoted unedited, and `docs/judge/README.md` is the legend that names these shapes
   on purpose.

## Where things live

- `RUBRIC.md` is the pre-registered evaluation rubric.
- `CALIBRATIONS.md` lists every uncalibrated threshold.
- `ATTRIBUTION.md` covers source data attribution and licensing.
- `skills/microrelief/SKILL.md` documents *using* the CLI. This file is about *changing* the code.
- `scripts/neutrality.sh` and `scripts/histscan.sh` are the two publication scans: what the
  current tree publishes, and what the history does. The second is not in the gate — see below.

## Commands

The block below mirrors `.github/workflows/ci.yml` step for step, and
`tests/test_contributing_commands.py` locks it: same install line, `uv run <tool>` becomes
`.venv/bin/<tool>`, no `&&`. When they disagree, `ci.yml` is the gate and this block is wrong.

    uv sync --locked --extra dev --extra site
    .venv/bin/ruff check src tests scripts
    .venv/bin/ruff format --check src tests scripts
    .venv/bin/mypy
    .venv/bin/pytest -q
    bash scripts/check_version_bump.sh      # warn-class
    bash scripts/neutrality.sh --self-test
    bash scripts/neutrality.sh

Run each separately and report each exit code. `--locked` fails when `uv.lock` has drifted from
`pyproject.toml`, which is what CI does; an unlocked `uv sync` would rewrite the lock in silence.
Add `--extra dgt` only to exercise the DGT catalogue commands.

### One scan the gate cannot run

```
bash scripts/histscan.sh --must-find microrelief
```

(Fenced, not indented: the block above is read line by line by
`tests/test_contributing_commands.py`, and a second indented block under this heading would be
mistaken for a CI step this repository does not run.)

`scripts/neutrality.sh` reads the index: what the current tree publishes. `scripts/histscan.sh`
reads every blob of every ref — what the history publishes, including files deleted releases ago.
CI cannot run it, because it checks out with `fetch-depth: 2` and the script refuses a shallow
repository rather than print a denominator over a history that is not there. Its `--self-test`
does run in the suite, so the instrument is checked on every push; the scan itself is a human
step.

Run it before anything that publishes history — making the repository public, or any change to
what the refs contain — and read the denominators, never the silence. A run is stale the moment a
commit lands, so it is re-run on the exact history being published and compared against the last
recorded run in `docs/live-smoke.md`.

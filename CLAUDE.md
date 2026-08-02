# CLAUDE.md — dev contract

This file is the dev contract for this repository. It states process rules only, not the
science — the science lives in `RUBRIC.md`, `CALIBRATIONS.md`, and `ATTRIBUTION.md`.

## Rules

1. **TDD always.** RED → GREEN → REFACTOR. Do not write production code before a failing test
   exists for it.
2. **Refusal over guessing.** When an input is ambiguous, out of range, or otherwise cannot be
   processed with a defensible answer, the pipeline refuses explicitly with the reason in the
   message. It never silently guesses or falls back to a plausible-looking default.
3. **CRS is never inferred.** Any code that touches geometry or a raster/point-cloud CRS must
   verify it explicitly and reproject as needed. If the CRS is ambiguous or missing, refuse —
   do not assume.
4. **Every hardcoded number is declared.** A new threshold or magic constant lands in
   `CALIBRATIONS.md` in the same commit that introduces it — value, where it is used, its origin,
   and what would replace it with an empirical calibration.
5. **No credentials in this repository, ever.** No `.env` file, no tokens, no keys, not even
   placeholders. Data source credentials, if ever needed, live outside this repo.
6. **Mocked tests prove wiring, not behaviour.** Any reader or client that touches a real file or a
   real network endpoint is unvalidated until it has been exercised end-to-end against the real
   source at least once, with the result recorded.
7. **The gate is `.github/workflows/ci.yml`, not a remembered command.** It runs five steps —
   `ruff check src tests scripts`, `ruff format --check src tests scripts`, `mypy`, `pytest -q`,
   and a neutrality grep over tracked files. Run all five before calling a change clean; invoke
   each binary by path (`.venv/bin/ruff`, never a bare name, which can resolve to a shell function
   and diverge from the runner in silence); and report each exit code separately, because `&&`
   hides which step failed. Where a check's silence is its pass condition, prove it can still
   fail — a check that scanned nothing exits 0 exactly like a check that found nothing.

## Where things live

- `RUBRIC.md` — the pre-registered evaluation rubric.
- `CALIBRATIONS.md` — every uncalibrated threshold, declared.
- `ATTRIBUTION.md` — source-data attribution and licensing.

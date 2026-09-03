# Wiring SMRF as the default: what the sample must produce, written before it is wired

2026-09-03. Lands **before** the commit that changes `cli.py`.

## Why this file exists

The shipped sample's record is a **golden fixture**: `tests/test_sample.py` runs the CLI and
compares the result against `examples/sistelo-sample/expected/provenance.json`. When the filter
changes, that file is regenerated from the same run it is supposed to check — so a wrong
implementation and its regenerated fixture pass together, and the suite stays green over a
product nobody measured. Regeneration cannot be its own acceptance.

So the numbers the wired CLI must produce are fixed here first, measured by a **different code
path**: a script calling `read_laz` → `Accumulator` → `classify_ground_smrf` → `compute_basis` →
`honesty_report` → `agreement` directly, with no CLI involved.

**This is a cross-path replication target, not a blind pre-registration.** The figures below were
already observed on the library path; what is unexercised, and what this file binds, is the
*wired* path — the composition root, the grid the CLI builds, the parameters it pins and passes,
and the record it writes. The distinction matters and is stated rather than glossed: a blind
pre-registration would be stronger, and this is not one.

The control that makes the probe worth anything: run on the **same** inputs, the same script
reproduced the *current* filter's published record exactly — `measured 56.2189%`,
`interpolated 43.1067%`, `undetermined 0.6744%`, `recall_ground 0.9988`,
`recall_nonground 0.7227`, `accuracy 0.8367`, `fp 14327` — every one of which matches
`examples/sistelo-sample/expected/provenance.json` at 0.4.4. A probe that reproduces the shipped
record on the arm being replaced is running the shipped path.

## The target

`examples/sistelo-sample`, 300 × 300 cells of 0.5 m, EPSG:3763, one tile
(`sistelo-terraces-150m.laz`), SMRF at PDAL's defaults (`cell = 1.0`, `slope = 0.15`,
`scalar = 1.25`, `threshold = 0.5`, `window = 18 * cell = 18.0 m`, `cut = 0`).

| Quantity | Required |
|---|---|
| `honesty.fraction_measured` | 0.515600 |
| `honesty.fraction_interpolated` | 0.423411 |
| `honesty.fraction_undetermined` | 0.060989 |
| `agreement.recall_ground` | 0.9768 |
| `agreement.recall_nonground` | 0.7884 |
| `agreement.accuracy` | 0.8661 |
| `agreement.tp / fp / fn / tn` | 35470 / 10934 / 844 / 40730 |
| `agreement.n_cells` | 87978 |

Tolerance: the fractions and the confusion counts are **exact** — same inputs, same arithmetic,
same order. A difference of one cell is a difference, not noise, and is investigated rather than
absorbed into a tolerance.

## What a failure means

- **The counts differ** → the wired path is not the measured path. The composition root is
  passing something the probe did not: a different grid, a different surface, a different
  parameter. Find which before touching the fixture.
- **The counts match but the record differs** → the defect is in what the record *says*, not in
  what ran, which is the narrower and more likely failure.

Either way the golden fixture is not regenerated until the table above is satisfied.

## What this file does not cover

The full 3,960 × 3,960 run. Its figures are unmeasured at the time of writing and no honest
target can be set for them here. Its acceptance is **self-replay** — two runs, byte-identical
across every band and every record field but the three a version bump is permitted to move —
plus a stated old→new delta table in `docs/live-smoke.md`.

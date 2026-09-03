# P4, the terrace predicate — the measured result

**2026-09-03. VERDICT: PASS.** Both predicates of `docs/p4-terrace-preregistration.md`, which was
committed at `7429761` before the terrace population was computed once, are met:

| | predicate | bound | measured |
|---|---|---|---:|
| **P4a** | our measured ground the in-repo SMRF keeps | ≥ 85.0% | **91.078%** |
| **P4b** | of those, the ones on a step > 2.5 m it keeps | ≥ 80.0% | **95.082%** |

**SMRF does not eat the terraces.** On the window this tool publishes, it keeps nine in ten of the
cells the current filter calls measured ground, and — on this population — it keeps the steep ones
slightly *better* than the flat ones, not worse.

## The table

Window: `examples/sistelo-sample/aoi.geojson`, 150 m around the tallest verified riser (2.98 m),
bounds -20210…-20060 x 256245…256395 (EPSG:3763), 300 x 300 cells at 0.5 m, built from the whole
delivery tile `LO-179557-07-2025` (27,720,324 points,
sha256 `244cf8242f2923703625edcc9f5e5f35b756e71fceeca4a91903f999c19786d1`).

    population                                               cells   SMRF ground   PDAL ground
    ------------------------------------------------------------------------------------------
    P4a: our measured ground                                50,596         91.1%         91.8%
    P4b: ... on a step > 1.5 m                              27,637         95.4%         95.7%
    P4b: ... on a step > 2 m                                16,482         95.4%         95.5%
    P4b: ... on a step > 2.5 m  (GATE)                       7,625         95.1%         95.1%

    reported, with nothing riding on it:
      P4b at > 2.5 m requiring >= 10 finite cells: 7,426 cells, SMRF 95.4%, PDAL 95.4%
      where both our filter and PDAL call a cell ground: 46,427 cells,
        median difference +0.000 m, 0.03% differ by more than 0.5 m

The reference column is **PDAL 2.10.2 re-run for this measurement**, not quoted: `pdal --version`
reports `2.10.2 (git-version: e8618b)`, the version the record names, and the pipeline is the
tracked `docs/p4-reference-pipeline.json` (sha256-16 `8e328b1ba0a2d949`, recorded in the cache's
provenance). Control before the comparison, because a filter that silently did not run would look
like an excellent one: on this tile SMRF moves **3,217,933** returns into ground that the delivery
calls non-ground and **42,068** the other way, so the output is its verdict and not the delivery's
labels read back.

## What reproduced from 2026-08-31, and what did not

The pre-registration said the old figures would be re-derived rather than cited, and that if they
disagreed, **this population is the one that counts, because it is the one that is defined**. Both
things happened, and where they split is the informative part.

| figure | `docs/ground-filter-diagnosis.md` | here | |
|---|---:|---:|---|
| PDAL's share of our measured ground | 91.8% | **91.8%** | reproduces to the precision stated |
| cells where both call ground | 46,449 | **46,427** | 22 cells apart, 0.05% |
| median surface difference there | +0.000 m | **+0.000 m** | reproduces |
| share differing by more than 0.5 m | 0.03% | **0.03%** | reproduces |
| PDAL's share on a step > 2.5 m | 86.5% | **95.1%** | **does not reproduce** |

So the base population and the surface control land on the old numbers, and the *step*
population does not. The disagreement is localised in the phrase the old record left undefined —
"cells sitting on a real vertical step in 3.5 m" — and not elsewhere in the construction.

**One alternative explanation was raised in review and tested rather than dismissed:** that this
population is the anomalous one, because its ramp-permissiveness (below) admits smooth slope the
old one may have excluded. Measured, that cannot account for the gap — the near-planar cells are
**1.2%** of the population and retain at 94.6%, so removing all of them moves P4b by less than a
point, while the gap to be explained is 8.6. What the old population actually held is not
recoverable either way: its script was never in this tree. The 22-cell residual on the
both-ground control is likewise unexplained and was not investigated.

The direction differs too, not only the value. The old record reports retention **falling** with
steepness (90.7% at > 1.5 m, 89.3% at > 2.0 m, 86.5% at > 2.5 m) and reads that as "the steeper
the cell, the more SMRF drops". On the population defined here retention is **flat to slightly
rising** (95.4%, 95.4%, 95.1%) and sits *above* the base 91.1% at every threshold. These are not
the same object, and no attempt is made here to say which cells the old one held: its script was
never in this tree and cannot be recovered. The 22-cell residual on the both-ground control is
likewise unexplained and was not investigated.

**Consequence for the claim.** The sentence "SMRF costs about one in eight of the steepest cells"
in `docs/ground-filter-diagnosis.md` rests on the figure that did not reproduce. It is left in
place as the dated record it is, and this document is what a current claim about terrace cost
cites.

## The controls, run before the verdict was read

- **Must-fire.** The gate population is **not empty**: 7,625 cells at > 2.5 m. An empty population
  would make P4b's share `nan` rather than 100%, and the instrument exits 2 with a message rather
  than reporting a pass. On synthetic surfaces, a 3.0 m wall reads 3.0 m at the wall and 0.0 m two
  cells away (`tests/test_compare_ground_filters.py::TestStepMagnitude`).
- **Must-not-fire.** A flat surface produces an empty mask at every threshold; a window holding one
  observed cell is undefined, not a step of zero.
- **The predicate can fail.** Re-run with a deliberately terrace-eating parameterisation
  (`--smrf-slope 0.01 --smrf-threshold 0.05`) the same command reports
  **P4a 58.601% FAIL · P4b 60.197% FAIL · VERDICT: FAIL**, exit 1. The gate is measuring
  something.
- **Mutation.** 10 of 10 mutants of `step_magnitude` were caught — border exclusion removed,
  the two-finite-cell floor dropped to one, either NaN seed changed from ±inf, the range
  inverted, the even-window guard weakened, `STEP_WINDOW_CELLS` widened, the margin computed one
  cell short, the counts kernel narrowed, and undefined reported as flat.

  **Corrected 2026-09-03, after review.** That list overstated what it demonstrated. The
  "widened window" mutant changed the *constant*, which a test asserts directly (`7 × 0.5 =
  3.5`), so it was killed by arithmetic on a literal rather than by any test of what the window
  does. A mutant widening only the two extremum filters — leaving the constant, the counts
  kernel and the border margin alone — **survived all eight tests**, which means the extent the
  range is taken over was not pinned at all. Found by `/code-review`, not by me, and reproduced
  before being believed. `TestTheWindowExtentIsPinned` now places a wall four cells away, where
  the declared 7-wide window must read 0.0 m and a 9-wide one must read 3.0 m; the surviving
  mutant is caught by it.

## The confound this population has, found after the run

`step_magnitude` is a range in a window, so **it cannot tell a riser from a smooth slope steep
enough to span the threshold.** The pre-registration's must-not-fire control was a *flat*
surface, which is the easy case; the ramp is the input that fires while holding no step, and it
was not among the controls. Raised by `/code-review` after the verdict, reproduced before being
accepted.

**And the window is square, which matters twice.** A 7 × 7 window separates cells by 3.0 m along
an axis but by 3.0 √2 = **4.243 m** across the diagonal, so a planar ramp enters the population
from **30.5°**, not the 39.8° an axis-aligned reading gives. Hillsides are not grid-aligned, so
the diagonal is the number that governs. Measured on planar ramps at 0.5 m cells, holding no step
anywhere — share of cells over 2.5 m:

    slope     axis-aligned     diagonal
     28deg            0.0%         0.0%
     30deg            0.0%         0.0%
     31deg            0.0%       100.0%
     35deg            0.0%       100.0%
     40deg          100.0%       100.0%

**This correction is itself a review finding.** The first version of this section reported only
the axis-aligned column and stated the limitation as 39.8°, understating it by about nine
degrees, and the test pinning it used a 30° axis-aligned ramp — which passes while a 35° diagonal
ramp fires 100%, so it did not bound what its own docstring claimed.

**How much of the real denominator this is, measured rather than argued.** By
`scripts/measure_ramp_confound.py`, which is tracked: the first version of these numbers lived in
a session scratchpad, which is precisely the loss this branch exists to stop, and a review caught
it being reintroduced for the figures that answer the review. Fitting a
least-squares plane to the observed cells of each window and taking the RMS residual separates
the two by construction: a uniform ramp is planar at any steepness, a riser is not. Calibration —
a 45° ramp gives a median residual of **0.000 m**, a 2.6 m wall on flat ground gives **0.719 m**.
The real gate population sits far closer to the wall: median **0.381 m**, and only **1.2%** of
cells fall below 0.10 m.

**The verdict does not rest on it.** SMRF's retention over the gate population, restricted by how
planar the window is:

    subset                                          cells     SMRF     PDAL
    all gate cells (the measured P4b)               7,625    95.1%    95.1%
    residual >= 0.10 m  (drop the near-planar)      7,506    95.2%    95.2%
    residual >= 0.20 m                              6,218    94.7%    94.6%
    residual >= 0.30 m  (clearly not a ramp)        4,954    94.2%    94.1%
    residual >= 0.50 m  (wall-like)                 2,646    92.1%    92.1%
    residual <  0.10 m  (the ramp-like cells)          93    94.6%    94.6%

Purging every cell that could be smooth slope leaves **92.1%**, twelve points clear of the 80.0%
bound, with PDAL identical. So the confound is real by construction and is now a declared
limitation pinned by a test (`TestTheRampIsADeclaredLimitation`), but P4b's verdict is not
sensitive to it.

**This is not a redefinition.** The population measured above is the one fixed before the run,
and it stays the population of record; changing it after seeing the result is what the
pre-registration forbids. A riser-only population — range plus a curvature or planarity term —
would be a better instrument and is available as a **new dated pre-registration**, not an edit to
this one.

## The commands

    pdal pipeline docs/p4-reference-pipeline.json \
        --readers.las.filename=<tile-dir>/LO-179557-07-2025.laz \
        --writers.las.filename=<ref-dir>/LO-179557-smrf.laz

    python scripts/compare_ground_filters.py reference --tiles <tile-dir> --smrf <ref-dir> \
        --aoi examples/sistelo-sample/aoi.geojson --out <cache>.npz \
        --pipeline docs/p4-reference-pipeline.json

    python scripts/compare_ground_filters.py terraces --reference <cache>.npz

## What this does and does not license

**Does.** P4 is measured, which is the condition
`docs/smrf-build-preregistration.md` set on moving the pipeline default to SMRF: *"the pipeline
default does not move to SMRF until P4 has been measured, whatever P1-P3 say."* With P1-P3 PASS
(`docs/smrf-build-result.md`) and P4 PASS, that condition is discharged.

**Does not.** Nothing is wired. The CLI default is untouched, no output changes and no record hash
moves in this branch. The wiring, the version bump and the re-run that carries the
`cli.py` limitation-string correction are separate work, and the numbers this tool publishes will
move when they land.

**And the bound's provenance is still the weaker half.** 85 and 80 were set as slack below 91.8 and
86.5 — and 86.5 is the figure that did not reproduce. P4b passes here by 15 points, so the verdict
does not turn on it; but a bound derived from a measurement nobody can reproduce is a bound whose
margin is not known, and that is said here rather than left for a reader to notice.

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

So the base population and the surface control land on the old numbers, and the *step* population
does not. That is as sharp a localisation as this could have given: the disagreement sits exactly
in the phrase the old record left undefined — "cells sitting on a real vertical step in 3.5 m" —
and nowhere else in the construction.

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
- **Mutation.** 10 of 10 mutants of `step_magnitude` were caught by the tests above — border
  exclusion removed, the two-finite-cell floor dropped to one, either NaN seed changed from
  ±inf, the range inverted, the even-window guard weakened, the window widened by two cells, the
  margin computed one cell short, the counts kernel narrowed, and undefined reported as flat.

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

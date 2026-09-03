# The in-repo SMRF, measured against PDAL's

**2026-09-03.** Verdict rule fixed before the run in `docs/smrf-build-preregistration.md`
(commit `4fdc82b`, which also carries the code). The instrument is
`scripts/compare_ground_filters.py smrf`; the commands and their real output are in
`docs/live-smoke.md` under this date.

## Verdict: PASS on all four predicates

| | predicate | bound | measured | |
|---|---|---:|---:|---|
| **P1** | plain-ground control called ground | ≥ 97.0% | **99.410%** | **PASS** |
| **P2** | row B (class 6, no class 2) called ground | ≤ 30.0% | **16.426%** | **PASS** |
| **P3** | cell-by-cell agreement with the reference | ≥ 90.0% | **99.662%** | **PASS** |
| **P3** | Cohen's κ | ≥ 0.60 | **0.991** | **PASS** |

Over 23,058,525 measured cells: both filters call 16,720,892 ground and 6,259,678 object; they
disagree about 77,955 cells, 0.34% — 42,055 ground only here, 35,900 ground only there.

Every audited population lands on the reference to the first decimal:

| population | cells | ours | reference |
|---|---:|---:|---:|
| A: any class-6 return | 4,738,087 | 24.6% | 24.6% |
| B: class-6, no class-2 | 4,270,425 | **16.4%** | **16.4%** |
| C′: B eroded by 2 cells (our reading) | 2,223,855 | 19.3% | 19.3% |
| control: canopy | 2,493,967 | 19.5% | 19.5% |
| control: plain ground | 12,062,527 | 99.4% | 99.4% |

**What that buys.** On the same populations and the same cache, the filter shipping today
publishes **87.7%** of row B as measured terrain where this one calls **16.4%** of it ground — the
71.3-point gap the ruling was made to close, closed to within 0.03 points of the reference, at
99.4% on plain ground against the reference's own 99.4%.

## Why the agreement is believable

A table matching the reference on every population to one decimal is either a result or a
tautology, and the difference is whether it can fail. Run with the parameters wrong:

| | row B called ground | agreement | κ | verdict |
|---|---:|---:|---:|---|
| `--smrf-window 1.0` | 88.0% | 83.30% | 0.482 | **FAIL** |
| `--smrf-slope 1.5` | 86.3% | 82.54% | 0.452 | **FAIL** |
| `--smrf-threshold 5.0` | 52.2% | 86.86% | 0.611 | **FAIL** |

So the comparison discriminates, and a badly parameterised SMRF collapses into precisely the
failure mode of the filter shipping today: it publishes roofs as ground. Note also that P1 passes
in all three of those runs — a one-sided bound on plain ground is satisfied by *any* filter that
over-preserves, which is why it is not the only predicate.

The reference itself is the one from `docs/reference-instrument-result.md`, rebuilt with three
additions. The rebuild reproduces its controls exactly (`into_ground` 15,892,932 · `out_of_ground`
322,530 · `passed_through_class2` 7,345 · `judged` 100,323,464) and the same six tile sha256s, and
the old filter re-run on the new cache reproduces every published figure of that record. The
recorded pipeline sha256 `8055f03add32c1b0` was matched back to its file by `sha256sum`, which is
what says this is the same environment rather than a similar one. (Called a sha256 and not a hash
because the repository's partition guard reads "hash + twelve hex" as a published *record* hash and
fired on this sentence: the guard was right about the shape and this is the more accurate word.)

## The three side-measurements, which were declared before the run

**1. The cell-level membership test is not costing anything here.** This package tests each cell's
*lowest* return against the provisional DEM; the reference calls a cell ground if *any* judged
point passes. Measured over the cells the reference calls ground, its verdict came from a point
more than 0.05 m above the cell minimum in **0.02%** of them, more than 0.25 m in 0.01%, and more
than 1.00 m in 0.00%. The two tests are asking the same question about the same point almost
everywhere — which is the assumption the whole design rests on, now measured rather than argued.

**2. The input rule is not the residual.** Handing the filter the minimum over the returns the
reference itself reads (last/only, class 7 excluded) instead of the pipeline's minimum over all
returns moves agreement from 99.662% to 99.684% and κ from 0.991 to 0.992. The 0.34% of cells the
two disagree about are not an artefact of which returns feed the surface.

**3. Tile seams account for about a fifth of the residual.** Excluding 20 m either side of every
delivery-tile edge — where the reference ran per tile on its own bounds and this package runs on
one AOI grid — leaves 21,607,897 cells at **99.73%** agreement and κ **0.993**, against 99.662%
and 0.991 over everything.

## What is not claimed

- **Not parity.** The differences named in the pre-registration are real and unmeasured
  individually: the per-tile versus AOI grid, this reader dropping ASPRS 18 where the recorded
  pipeline ignores only 7, tie-breaking in the fill. Together with the membership test they are
  what the remaining 0.34% is made of; this run apportions only the seam part of it.
- **Not the terraces.** P4 is unmeasured and Valongo cannot answer it: a filter that removed
  buildings by removing every abrupt step would destroy the artefact this tool exists to publish.
  **The pipeline default does not move to SMRF until P4 is measured on Sistelo**, whatever the
  four predicates above say.
- **Not shipped.** Nothing is wired. The CLI default is still the old filter, no output changes,
  and no record hash moves.

## Found while sweeping, and not fixed here

The limitation string shipped in the record — `src/microrelief/cli.py`, mirrored in
`scripts/compare_runs.py` and baked into `examples/sistelo-sample/expected/provenance.json` —
names row B's population ("cells holding official building returns and no ground return") and
gives **89.7%**, which is row C's figure, and row C is the population
`docs/reference-instrument-result.md` records as not re-derivable. The right number for the
population it names is **87.7%**.

It is not corrected in this commit because correcting a string inside the shipped record changes
the record's hash, which demands a version bump and a full re-run — the ritual the wiring session
must perform anyway. It is written down here rather than left to be re-found. Note the direction:
the error overstates a limitation the tool declares against itself, so nothing a reader relies on
is inflated by it. The two live claims that could be fixed without a re-run — both in `README.md`
— were fixed in this session.

## What the pre-merge review changed, 2026-09-03

`/code-review high` on PR #4, run after the record above was written. It re-derived the algorithm
against `filters/SMRFilter.cpp` @2.10.2 line by line and reported **no fidelity findings**, which
is the part of this build that most needed an outside instrument. Eight findings elsewhere; what
was done with each:

- **The README's Sistelo half was still wrong after I "fixed" it.** I corrected the Valongo figure
  to 87.7% and left `77.2%` in the same sentence under the same row-B phrase — but 77.2% is a
  *roof-interior* figure, the population whose erosion is not re-derivable. Fixed: each figure now
  names its own population, and the sentence says the two are not the same measurement. A count
  was also paired with the wrong share (86,759 cells is 0.55% of that AOI; the 0.43% belongs to the
  ~67,000-cell falsely-measured subset), so the share is gone rather than restated — 0.55% has no
  source in this repository's record and quoting it there would be inventing one.
- **The lock on the acceptance bounds was a substring test and passed under real drift.** Measured:
  loosening P1 from 97.0 to **10.0** passed silently, because "10" occurs in the prose. Each bound
  is now read from the table row that *names* it, and the control mutates a bound and requires a
  failure instead of asserting that an unrelated string is absent. Verified by changing the
  constant: the old lock stayed green, the new one goes red.
- **`seam_cells` did not compute what its docstring said** — it unioned a row band with a column
  band, marking cells deep inside one tile because another tile's edge shared their row, and the
  single-tile test could not tell the definitions apart. Now a frame per tile, with a two-tile test
  that fails against the old definition. **The published figure did not move**: re-run, the seam
  exclusion is still 21,607,897 cells at 99.73% and κ 0.993, because six tiles in a regular grid
  make every tile edge a full AOI row or column. Measured, not assumed.
- **A mistyped `--pipeline` now refuses.** It used to fall through to an empty
  `reference_pipeline_sha256_16`, attributing the acceptance run to an unidentified reference.
- **`CellStats.min_z_ground_asprs` was being handed `min_z_all`.** Harmless only while
  `compute_basis` reads `n_all` alone. The cache now carries the real array, and a cache built
  before it refuses rather than running over a substitution.

**Declared, not fixed:** the instrument reads tiles with `footprint=None` while the pipeline passes
the catalogue's declared bbox, so a corrupted return of the kind measured on 2026-08-05 would be
refused by the product and accepted here. The instrument has no catalogue selection to derive that
bbox from; closing it properly belongs with the wiring session. Also still open, and unchanged: the
limitation string in `cli.py` described above.

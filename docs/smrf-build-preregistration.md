# What would count as a working SMRF — fixed before the first run

**2026-09-03.** Written and committed **before** `scripts/compare_ground_filters.py smrf` was run
against the Valongo reference cache even once. The result goes to `docs/smrf-build-result.md`
whichever way it lands.

The thing being tested is `src/microrelief/smrf.py`: SMRF (Pingel et al. 2013) re-implemented in
this repository, against the same algorithm as PDAL 2.10.2 runs it. The reference cache, its
controls and its provenance are the ones described in `docs/reference-instrument-result.md`.

## Why a pre-registration and not just a comparison

Because the tempting failure here is not getting a bad number — it is getting a bad number and
then adjusting the filter until it agrees with the reference. That is fitting the instrument, and
it would produce a filter that matches PDAL on this AOI and means nothing anywhere else. So the
bounds are fixed first, and **on failure the result is recorded and the work stops**; parameters
are not tuned toward the reference afterwards. Any later change to these bounds is a new dated
entry, never an edit to this one.

## The predicates

All three must hold. Populations are defined from the delivery's ASPRS classification, which
decides no cell in either filter — it names who is being audited, the role it already has in
`agreement()`.

| | predicate | bound | why it is not passed by a degenerate filter |
|---|---|---|---|
| **P1** | share of the plain-ground control (class 2, no class 5, no class 6) this filter calls ground | **≥ 97.0%** | a filter that calls everything object scores 0 |
| **P2** | share of row B (class 6, no class 2) this filter calls ground | **≤ 30.0%** | a filter that calls everything ground scores 100 |
| **P3** | cell-by-cell agreement with the reference over all measured cells | **≥ 90.0%** | — |
| **P3** | Cohen's κ over the same cells | **≥ 0.60** | κ is what catches the all-ground filter: most cells here are ground, so it posts high raw agreement while agreeing about nothing, and scores κ ≈ 0 |

Where the bounds come from, so they can be argued with rather than only accepted:

- **P1 at 97.0%.** PDAL's own SMRF calls 99.4% of this population ground and the filter shipping
  today calls 100.0%. The point of the change is to not lose plain ground; 3 points of slack
  absorbs the declared differences below, and anything worse is a real loss.
- **P2 at 30.0%.** PDAL calls 16.4% of row B ground; the filter shipping today calls 87.7%. The
  gap being bought is 71.3 points, and 30.0% still keeps at least 57.7 of them. A filter that got
  halfway would fail.
- **P3 at 90.0% and κ ≥ 0.60.** These two are a pair on purpose. Raw agreement alone is satisfied
  by the prevalence of ground on this AOI; κ alone is hard to read. Both are set where a
  re-implementation that follows the published algorithm should land comfortably, and a plausible
  misreading of it should not.

## Reported beside the predicates, with nothing riding on them

These are measurements, not gates, and they exist so that a number that looks like disagreement
between the two filters can be attributed instead of averaged over:

1. **Agreement excluding 20 m either side of every tile edge.** The reference ran once per tile,
   on that tile's own bounds; this package runs on one AOI grid. That difference lands on the
   seams and nowhere else.
2. **How often the reference's ground verdict for a cell came from a point above the cell's
   minimum**, at 0.05 m, 0.25 m and 1.00 m. This is the load-bearing assumption of a cell-level
   membership test: the reference calls a cell ground if *any* judged point passes, this package
   tests the lowest one. If those are usually the same point, the two tests ask the same question.
3. **The same table run on both input surfaces** — the pipeline's own minimum over all returns,
   and the minimum over the returns the reference itself reads (last/only, class 7 excluded) — so
   that a difference in the *input* is never read as a difference between the *filters*.

## Declared differences, so they are not discovered later

Exact parity with PDAL is not claimed and is not reachable:

- the reference ran **per tile**; this runs on one AOI grid, with a different cell partition;
- this package's reader drops ASPRS 7 **and 18**, while the recorded pipeline ignores only 7;
- the membership test is per **cell** here and per **point** there (measurement 2 above);
- `knn_fill` resolves exact distance ties by whatever the KD-tree returns first;
- net cutting (`cut > 0`) is not implemented and is refused rather than ignored.

## P4, the terrace predicate, is deferred — and it gates the flip, not this build

Valongo has terraces only incidentally, so this AOI cannot answer the symmetric risk: a filter
that removes buildings by removing every abrupt step would destroy the artefact this tool exists
to publish. On the Sistelo window around the tallest verified riser (2.98 m, tile LO-179557), the
re-implementation must keep **≥ 85%** of the cells the current filter calls measured ground, and
**≥ 80%** of those sitting on a step above 2.5 m — against PDAL's measured 91.8% and 86.5%
(`docs/ground-filter-diagnosis.md`). **The pipeline default does not move to SMRF until P4 has
been measured**, whatever P1-P3 say.

## The commands

```
python scripts/compare_ground_filters.py smrf --reference <cache>.npz
python scripts/compare_ground_filters.py smrf --reference <cache>.npz --surface min_z_judged
```

The bounds above are also constants in that script (`P1_PLAIN_GROUND_MIN` and its siblings), and
`tests/test_compare_ground_filters.py` fails if the two sets of literals ever disagree.

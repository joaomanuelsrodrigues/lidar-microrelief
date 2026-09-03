# P4, the terrace predicate — what would count as passing, fixed before the first run

**2026-09-03.** Written and committed **before** the terrace population was computed even once.
The result goes to `docs/p4-terrace-result.md` whichever way it lands.

P4 was deferred out of `docs/smrf-build-preregistration.md` because Valongo has terraces only
incidentally. It is the symmetric risk to the one that build measured: a filter that removes
buildings by removing every abrupt step would destroy the artefact this tool exists to publish.
P1–P3 said SMRF stops publishing roofs as terrain. P4 asks what it costs on the thing worth
keeping. **The pipeline default does not move to SMRF until P4 has been measured**, whatever
P1–P3 say.

## The bounds, unchanged

Quoted from `docs/smrf-build-preregistration.md`, which fixed them on 2026-09-03 before the build
was run. This document does not touch them; it defines the population they are evaluated over.

> On the Sistelo window around the tallest verified riser (2.98 m, tile LO-179557), the
> re-implementation must keep **≥ 85%** of the cells the current filter calls measured ground, and
> **≥ 80%** of those sitting on a step above 2.5 m — against PDAL's measured 91.8% and 86.5%.

## What is not re-derivable, said before the run and not after it

Those two reference figures, 91.8% and 86.5%, come from `docs/ground-filter-diagnosis.md`. **They
have no artefact.** All four commits that wrote that document (`57a3c1c`, `1464cf6`, `765d9db`,
`240db1e`) are documentation-only; the script that produced them was never in this tree, and the
PDAL environment it ran against died with a session scratchpad. The same class of loss the
instrument's own docstring records for the roof table.

Two consequences, both of which constrain what this run may claim:

1. **The bounds' provenance is weaker than it reads.** 85 and 80 were set as a few points of slack
   below 91.8 and 86.5 — numbers measured over a population defined only in prose. The bounds are
   still the gate, because they were fixed first and are not being moved; but their derivation
   rests on a measurement that cannot be reproduced.
2. **This run therefore re-derives the reference column** rather than citing it. PDAL 2.10.2 —
   the version the record names, verified by `pdal --version` reporting
   `2.10.2 (git-version: e8618b)` — is installed again and run over the same tile, and its share
   is reported on **the same operational population** as ours. If the re-derived PDAL figures land
   near 91.8/86.5 that is evidence the prose population and this one are close. If they do not,
   **this document's population is the one that counts**, because it is the one that is defined.
   Agreement with the old numbers is context. It is not a check, and it may not be used as one.

## The surface the step is measured on, and why it is not ours

`min_z_ground_asprs` — the per-cell minimum of the delivery's own ASPRS class-2 returns.

Not our DTM, for the same reason `scripts/measure_risers.py` refuses it: `max_elevation_m` is the
parameter that decides whether a riser survives our filter, so a surface shaped by our filter
would select the population by the very thing being audited. The delivery's classification decides
no cell in either filter here. It names who is being audited — the role it already has in
`agreement()` and in `populations_of()`.

## The step operation

For each cell `c` on the AOI grid (0.5 m cells):

- take the **7 x 7 cell window** centred on `c` — 3.5 m across, at 0.5 m cells;
- over the cells of that window where `min_z_ground_asprs` is **finite**, take
  `step(c) = max - min`;
- `step(c)` is **undefined**, and `c` is excluded, where the window holds **fewer than 2 finite
  cells** (a range needs two points) or where `c` lies **within 3 cells of the grid border**
  (its neighbourhood was not observed — the reasoning `interior()` already applies with
  `border_value=0`).

`c` **sits on a step above T** iff `step(c) > T`.

**The reading of "in 3.5 m" this takes, and the one it does not.** The record's phrase is *"cells
sitting on a real vertical step in 3.5 m"*, with 1.5 / 2.0 / 2.5 as the heights. This reads 3.5 m
as the **horizontal extent** over which the vertical height is measured, which is why the window
is 3.5 m across. The alternative reading — 3.5 m as the height *cap*, i.e. `max_elevation_m`, the
parameter under calibration — is named here so that it is on record as considered and declined
**before** any number was seen, not rationalised after one. It is declined because the sentence
gives the heights separately, as the thresholds swept.

## The populations

| | population |
|---|---|
| **P4a** | cells the **current filter** publishes as measured ground: `compute_basis(...) == BASIS_MEASURED` under `classify_ground` at its shipped defaults |
| **P4b** | P4a intersected with `step(c) > 2.5 m` |

The metric in both rows is the share of that population the **in-repo SMRF** also calls ground.
The reference column is the share PDAL's `filters.smrf` calls ground, over the identical cells.

## The predicates

Both must hold.

| | predicate | bound | why it is not passed by a degenerate filter |
|---|---|---|---|
| **P4a** | share of P4a the in-repo SMRF calls ground | **≥ 85.0%** | a filter that calls everything object scores 0 |
| **P4b** | share of P4b the in-repo SMRF calls ground | **≥ 80.0%** | the steep cells are where an over-cutting filter loses the terraces first; P4a alone is dominated by the flat treads and would pass while the risers were eaten |

P4b is the predicate with the work in it. P4a is reported and gating, but a filter can hold P4a
comfortably while destroying exactly what this tool publishes, which is why the pair is the gate
and not the first row alone.

## Reported beside the predicates, with nothing riding on them

1. **The sweep at > 1.5 m and > 2.0 m**, as the record swept it. Only > 2.5 m gates.
2. **P4b recomputed requiring >= 10 finite cells in the window** instead of >= 2, so a reader can
   see whether the result is driven by sparse neighbourhoods, where two distant points on a slope
   can produce a large range without a step being present.
3. **The population sizes**, beside every share. A share travels with its denominator.
4. **PDAL's share on P4a and P4b**, the re-derived reference column.
5. **The surface agreement where both filters call a cell ground**, as the consistency control on
   the construction of the SMRF surface — the check `docs/ground-filter-diagnosis.md` reports as
   46,449 cells at median +0.000 m.

## Controls, because a population that cannot fail is not a population

Run and recorded **before** the verdict is read:

- **Must-fire.** The step mask must select cells on the known riser. A synthetic surface holding a
  step of known height must produce `step` equal to that height at the step and `0` on the flat,
  and the real window's mask must be non-empty at > 2.5 m. An empty P4b is not a pass; it is a
  broken instrument, and it would make P4b's share `nan` rather than 100%.
- **Must-not-fire.** A flat synthetic surface must produce an empty mask at every threshold.
- **The predicate must be able to fail.** The verdict is computed with a deliberately
  terrace-eating parameterisation as well, and that run must report **FAIL**. A gate that passes
  under every input is not measuring.

## On failure

**The result is recorded and the work stops.** Parameters are not tuned toward the bound
afterwards — that is fitting the instrument, and it would produce a filter that passes here and
means nothing anywhere else. Any later change to the bounds or to the population is a new dated
entry, never an edit to this one.

## The commands

    pdal pipeline <pipeline>.json            # LO-179557, delivery -> SMRF-classified counterpart
    python scripts/compare_ground_filters.py reference --tiles <tile-dir> --smrf <ref-dir> \
        --aoi examples/sistelo-sample/aoi.geojson --out <cache>.npz --pipeline <pipeline>.json
    python scripts/compare_ground_filters.py terraces --reference <cache>.npz

The window is the committed one: `examples/sistelo-sample/aoi.geojson`, 150 m around the tallest
verified riser, bounds -20210...-20060 x 256245...256395 (EPSG:3763), cut from `LO-179557-07-2025`.
The reference cache is built over that AOI from the **whole** delivery tile, so that PDAL's filter
sees the tile it would see in production and no edge of the 150 m cut becomes an edge of its input.

The bounds above are also constants in `scripts/compare_ground_filters.py`
(`P4A_TERRACE_MIN`, `P4B_STEEP_MIN`), and `tests/test_compare_ground_filters.py` fails if the two
sets of literals ever disagree.

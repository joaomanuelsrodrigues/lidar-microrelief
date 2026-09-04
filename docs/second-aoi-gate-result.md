# Second-AOI gate — result, 2026-08-31

Pre-registration: `docs/second-aoi-preregistration.md`, committed at `181d95d` **before** this run.
Code: 0.4.3. AOI: Valongo / Paredes, six tiles, `aoi/valongo.geojson`.

## Verdict: **FAIL**

Under the pre-registered rule (ii) — *a product plausible but wrong*. Four of the five hazards
pass and one is inconclusive; the FAIL is not one of them. It is the product itself:

**The DTM publishes buildings as terrain.** Over the cells that hold official ASPRS class-6
(building) returns, the CHM has a median of **0.06 m** and **79.8%** of them sit below 0.5 m — the
surface says the top of the object and the ground are the same thing. The record does not say so.
Its `agreement` block reports ground recall **1.000** and accuracy **0.700** against a
majority-class null of 0.594, and none of the ten `known_limitations` mentions it.

Two controls, in the same tile, say this is the filter and not the instrument:

| official class | cells | CHM median | p90 | share < 0.5 m |
|---|---:|---:|---:|---:|
| 2 ground | 2,193,895 | 0.05 m | 3.01 m | 78.4% |
| 5 high vegetation | 353,419 | **5.87 m** | 19.97 m | 8.9% |
| 6 **building** | 575,771 | **0.06 m** | 3.15 m | **79.8%** |

> **Correction, 2026-08-31: the counts in this table do not reproduce.** Re-measured on
> the run's own grid, no tile gives 575,771 class-6 cells -- the closest is LO-162471 at 540,893
> AOI-clipped and 558,442 unclipped, 6.1% and 3.1% below. Two populations were tried and neither
> matches, so the row is not re-derivable from the method as described here. What *does* reproduce
> is the finding: over the whole AOI, class-6 cells have a median CHM of 0.08 m with **79.5%** below
> 0.5 m against the 79.8% recorded, and class-5 vegetation 6.34 m with 6.0% below -- so the verdict
> and its control stand on a bigger denominator than the one printed above.
> Full measurement: `docs/ground-filter-diagnosis.md`.

Vegetation is removed from the DTM. Buildings are not. A surface that were simply collapsed
everywhere would fail the vegetation row too, and it does not.

## It is not this AOI's defect — it is the published one's

The same measurement on Sistelo (`outputs_0.4.2`, tile LO-179557) gives building cells a median CHM
of **0.17 m** with **66.5%** below 0.5 m. The failure is already in the piece that is about to be
published. What differs is only how much of the scene is built: **32,937** building cells in the
Sistelo tile against **575,771** in the Valongo one, seventeen times more. Sistelo is a terraced
valley with a hamlet in it, so the defect had almost nothing to land on.

This is the whole argument for running a second AOI, made concrete: a site chosen for what it
shows can also hide what it does not contain.

## The mechanism, measured rather than argued

`max_window_m` is declared uncalibrated in the record, and `CALIBRATIONS.md` names its calibration
target as *"largest object to be removed (tree crown, building) at the chosen site"* — a target that
was never discharged for buildings, because Sistelo barely has any. Re-running the same AOI at
`--max-window-m 40` (windows to 32.5 m, against 4.5 m at the default -- **corrected**, see below) moves it:

| | default 4.0 | diagnostic 40 |
|---|---:|---:|
| building cells below 0.5 m CHM | 79.8% | **61.8%** |
| non-ground recall | 0.262 | 0.540 |
| accuracy (null 0.594) | 0.700 | 0.810 |
| undetermined cells | 0.1% | **7.5%** |

So the parameter is load-bearing and the shipped default is far from adequate here — **and no
tested value fixes it**. A morphological opening cannot see an object wider than its window, and
this AOI has industrial buildings wider than 16.5 m. The repair is a calibration plus a declared
limit, not a changed default.

> **Corrected 2026-08-31, and the mechanism above is wrong twice.** First the number:
> `windows_for(40.0, 0.5)` returns `(1.5, 2.5, 4.5, 8.5, 16.5, 32.5)` -- the radius doubles to 32
> cells and a window is `2r+1` across, so the largest is **32.5 m**, not 16.5 m. Second, and worse,
> the table's two shares are computed over populations that differ by more than a factor of two:
> over cells holding class-6 returns the CHM-valid count falls from **4,214,090** at the default to
> **1,831,895** at `w40`, because 7.5% of the AOI becomes `undetermined`. Widening the window does
> not remove buildings; it mostly stops answering over them. On the population that cannot be
> argued with -- roof interior, class-6 cells holding no class-2 return and at least two cells
> inside the footprint -- the flat share moves only **91.6% -> 87.1%**.
>
> The conclusion *"no tested value fixes it"* survives, on better evidence than the sentence that
> carried it: measured over 2,062 components, the best single **height** threshold separates
> survivors from caught at balanced accuracy **0.712** and the best single **width** threshold at
> **0.528**. Neither property the filter can key on separates a roof from terrain.
> `docs/ground-filter-diagnosis.md`.

## The five hazards

**H1 — the Sistelo-calibrated cap.** Pre-registered predicate: PASS. Ground recall **1.000** ≥ 0.90,
accuracy **0.700** > null **0.594**. *The predicate was weak, and this is recorded rather than
rewritten*: "recall ≥ 0.90" is satisfied perfectly by a filter that calls everything ground, which
is close to what happened. The number that carried the information was the one beside it —
non-ground recall fell from **0.495** at Sistelo's full AOI to **0.262** here.

**H2 — a different classification.** PASS on what this AOI could exhibit: CHM maximum **55.78 m**
(predicate < 60 m), p99.9 29.38 m; noise exclusion reported per tile (299 to 3,610 returns).
**INCONCLUSIVE** on the missing-class-2 branch — class 2 is present here, so the `agreement: null`
path was never reached. Declared, not rounded up.

**H3 — the network path off Sistelo's tiles.** PASS. `select` and `precheck` completed against the
live catalogue, and the record publishes `point_count_catalogue` beside `point_count_measured` for
all six tiles; they agree exactly, having been derived independently.

**H4 — read instability.** PASS. Two runs at identical parameters over a grid 1.5x Sistelo's
(23,058,525 cells) are **byte-identical**: same `reproducibility_hash`
(`ee05b4e174a92a10...`), same `grid`/`honesty`/`agreement`, 6 of 6 raster file digests matching.
Peak RSS 3.21 GB, 33-34 s. The declared instability did not reproduce.

**H5 — the common grid across six tiles.** PASS. AOI-wide non-measured share 12.72%; in the three
columns either side of each internal seam it is 17.04% (1.34x), 11.34% (0.89x) and 9.05% (0.71x).
Predicate was < 2.00x. No seam line.

## One refusal worth recording

Pointing `--laz` at a directory holding tiles outside the selection was refused: *"LO-179556-07-2025
is not in the selection ...; refusing to publish catalogue facts for some tiles and none for
others"*. Operator error, correct refusal, exit 2, and the message named the offending tile and the
selection it was checked against.

## What this changes

The gate reads FAIL, so it does not clear the flip. Nothing here alters the published Sistelo
numbers; deciding what to do about the building defect is a separate ruling.

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
`--max-window-m 40` (windows to 16.5 m, against 4.5 m at the default) moves it:

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

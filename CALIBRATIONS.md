# Uncalibrated thresholds (Regra 14)

Every number here is declared, not justified by taste. `origin` says where the value came from;
`calibration target` says what would replace guessing with measurement.

| Parameter | Value | Where | Origin | Calibration target |
|---|---|---|---|---|
| `cell` | 0.5 m | CLI default | Matches the finest DGT published product | Terrace tread width at the chosen site (Task 6) |
| `k_min_returns` | 1 | `density.py` | Weakest defensible bar: one return is a measurement | Sensitivity sweep 1/2/4 against terrace legibility |
| `d_max_interp_m` | 2.0 m | `density.py` | 4 cells at 0.5 m; beyond it "nearby" stops meaning anything | Semivariogram of the measured DTM at the site |
| reference `ground_fraction` in `honesty_report` | 1.0 | `density.py` | **Fixed by the definition of the comparison, not a tunable.** The report puts the measured void share beside what a Poisson process of the same density would leave empty *if every return reached the ground*. Tuning it toward the real canopy would make the two numbers agree by construction and destroy the only thing the pair says: the gap between them is the combined effect of canopy interception and the filter's own rejections (a cell is measured only when the filter calls it ground) | Nothing replaces it — it is the null. What gets measured against it is the site's actual ground-return fraction (Task 9) |
| `max_void_fraction` | 0.35 | `precheck.py` | Above ~1/3 the DTM is majority-invented under canopy (F-047) | Measured void fraction vs terrace legibility |
| `ground_fraction` in `estimate_tiles` | 0.4 (illustrative) — **measured 0.2448 at the chosen site** | `precheck.py`, triage only | Declared illustrative from the start, and now measurable: 25,939,422 ASPRS-ground of 105,971,852 returns over the Sistelo AOI (2026-08-04, `docs/live-smoke.md`). The triage table quoted this candidate's void at `f=0.4` as **8.2%**; at the measured fraction the honest expectation is **19.1%**, still inside `max_void_fraction`. **The default understates the void by more than a factor of two under closed canopy** — a triage run is a lower bound on emptiness, not an estimate of it | One measured ground fraction per land-cover regime, rather than one number for all of them; this is n=1 and heavily wooded |
| `max_window_m` | 4.0 m (unmeasured default) | `ground.py` | A ceiling on the radius search, **not a width the filter ever uses**: the radius doubles, so at 0.5 m cells this yields windows (1.5, 2.5, 4.5) m, and 4.0 and 6.0 are the same setting — see `windows_for()`. Sets the scale at which objects are found; measured, it does **not** decide whether risers survive | Largest object to be removed (tree crown, building) at the chosen site |
| `slope_threshold` | 0.3 (unmeasured default) | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs the official classification (`agreement()`) |
| `elevation_threshold_m` | 0.3 m (unmeasured default) | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs the official classification (`agreement()`) |
| `max_elevation_m` | 3.0 m | `ground.py` | **The parameter that decides whether terraces survive.** It caps every tolerance, so a riser is excused exactly when the cap exceeds it, at any window. At 3.0 m the filter tolerates two 1.5 m risers | **Largest true riser (or terrace wall) measured at the site** — the value has to stay above it |
| `max_cells` | 200,000,000 | `grid.py` | Memory ceiling: one float64 array of that many cells is ~1.6 GB, and the AOI is meant to be ~4 km² | Largest AOI that fits in the working machine's RAM at the chosen cell size |
| `limit` | 500 | `tiles.py` | Far above any anticipated AOI's tile count; otherwise arbitrary. Controls the STAC page size and truncation guard threshold. | Largest real AOI tile count actually observed in production queries |
| `min_coverage` | 0.999 | `tiles.py`, `select_tiles()` | Policy: the AOI defines the working area strictly and partial coverage is a refusal, not a shortfall to report — but **1.0 is unsatisfiable against this catalogue** (see below), so the bar sits just under it. Measured band: any value in (0.99, 0.999998] accepts the declared seams and still refuses the smallest real hole | The smallest genuine gap worth refusing, once one has been seen in real data rather than constructed |
| `max_area_km2` | 200.0 | `tiles.py`, `select_tiles()` | Found in DGT's own QGIS plugin source code (via project design spec); client-code claim, not published spec | Confirm against actual provider behaviour by requesting above the limit |
| `ASPRS_NOISE` | (7, 18) | `read.py` | **Not a tunable — the standard's own noise classes**, Low Point and High Noise. Excluded from every surface after being measured on the delivery: over the four Sistelo tiles class 7 spans **84.2 m to 1752.5 m** while classified ground tops out at **506.1 m**, and *every* return above 1000 m is class 7. Kept, it lifted the DSM to a **1524.55 m CHM** and — worse — dropped `min_z_all` below the terrain, which is the surface the ground filter reads and the DTM publishes. The count dropped per tile is published as `point_count_noise_excluded`, and `point_count_measured` stays the file's own total so the record remains comparable with the catalogue | Nothing replaces the class list. What is worth measuring is whether the provider's use of class 7 is consistent across survey blocks — here it carries noise at *both* extremes, which the class name does not suggest |
| `FOOTPRINT_TOLERANCE_M` | 0.01 m | `read.py` | Slack around a tile's declared `proj:bbox` before a return is called impossible. The catalogue's box is the box of the returns, so a real tile's extremes lie *on* it and zero slack refuses every tile. **Added after the first real run disagreed with its own replay**: one return of 109,312,003 came back with a coordinate far outside its tile, which collapsed that tile's measured density and moved one return across the AOI boundary. The excursion's magnitude was **not measured directly** — it was inferred from the density falling below 1e-6 pts/m², which puts the exploded bounding box above 1e15 m² | The distribution of real return positions relative to the declared box across a whole survey block. One centimetre is a guess bounded below by the scale/offset round trip and above by the only excursion seen; nothing yet measures what a *legitimate* tile's worst overshoot is |
| `sortie_gap_hours` | 6.0 h | `tiles.py`, `group_sorties()` | Longest gap between two acquisition stamps still counted as one flight. **The observed data does not discriminate inside a wide band** (see below): any value above ~3.2 min and below 24 h groups all four candidate sites identically. 6 h is the middle of that band in log terms, and cannot merge two date-only stamps, which the catalogue publishes at midnight | Distribution of within-sortie and between-sortie gaps across a whole DGT survey block, rather than four AOIs |

## Encoding conventions, not thresholds (`export.py`)

Three numbers in `export.py` are magic in the literal sense and none of them is a threshold: nothing
is compared against them to decide anything, and no measurement would ever replace them. They are
listed here because "no magic number without a label" does not make an exception for sentinels.

| Value | Band | Why this one |
|---|---|---|
| `NODATA_FLOAT = -9999.0` | `mdt`, `mds`, `chm` | The convention every GIS reads. It cannot collide with a real value: these are metres in EPSG:3763, and −9999 m is not a terrain elevation. NaN is *not* used on disk — it reads as missing in some tools and as a number in others |
| `NODATA_UINT8 = 255` | `basis` | Deliberately **not 0**. Zero is `undetermined`, which is a published state — we looked and there was nothing to measure — and declaring it NoData would erase exactly the admission the band exists to make. 255 is a code the band never produces |
| `NODATA_INT32 = -1` | `n_all`, `n_ground_asprs` | No count can be negative, so this cannot collide with a real value either. Again not 0, which is a true count: zero returns fell in that cell |

## What was measured, and what it corrected

The two `ground.py` rows above said something different until 2026-08-03, and the correction is worth
keeping because the original reading is the intuitive one. The claim was that `max_window_m` must stay
below the terrace tread or the filter eats the step. Three measurements against the synthetic fixtures
say otherwise:

- **`max_window_m` is a bound the filter never reaches.** The radius doubles (1, 2, 4, 8, 16 cells), so
  `max_window_m=24` at 0.5 m cells runs windows up to 16.5 m and never 24, and `4.0` and `6.0` are
  indistinguishable. Pinned by `test_max_window_m_is_a_ceiling_on_the_radius_search_not_a_window`.
- **A monotone staircase cannot be damaged at any window.** A morphological opening removes local
  maxima, and a slope that only ever climbs has none: `terraced` reads as entirely ground at 1 m, 4 m
  and 24 m windows against a 6 m tread. That is why the fixture used for the acid test is `hillside`,
  which has a crest. Pinned by `test_a_monotone_staircase_cannot_be_damaged_by_any_window`.
- **The cap is what governs.** On `hillside`, holding the window at `max_window_m=24`: at
  `max_elevation_m=3.0` the ground fraction is 1.0000 with all five terrace levels intact; at
  `max_elevation_m=1.0` it is 0.7700, one whole level is lost, and the removed cells straddle the
  crest (columns 39–61 of 0–99, crest at 50). Only the cap moved.

One artefact to not rediscover: at windows far past the AOI's own scale (100 m on a 50 m fixture) cells
*are* marked, but they are a contiguous strip against the high-x border with identical counts on riser
and non-riser columns alike. That is `mode="nearest"` clamping the array edge, not terraces being eaten.

## The sortie tolerance, and the band the data actually pins

`sortie_gap_hours` exists because the catalogue stamps each tile with the moment it was acquired, so
one pass appears as several stamps: Manteigas publishes four, spanning 6m23s of the same night, and
`select_tiles` read them as four epochs and refused a perfectly uniform AOI. Grouping by UTC day would
fix that case and break the one that matters — a night flight crossing midnight is one acquisition.

The value was measured rather than picked, by running the same three checks under four mechanisms
(2026-08-04, all four candidate sites' real stamps):

| Mechanism | Manteigas = 1 sortie | midnight crossing = 1 | Sistelo (1 day apart) = 2 |
|---|---|---|---|
| gap 3 min | **FAIL** (n=2) | **FAIL** (n=2) | PASS |
| **gap 6 h (landed)** | PASS | PASS | PASS |
| gap 30 h | PASS | PASS | **FAIL** (n=1) |
| UTC day (rejected) | PASS | **FAIL** (n=2) | PASS |

Two things this says. The tolerance is **not load-bearing** anywhere between ~3.2 min (Manteigas's
largest internal gap) and 24 h (the finest separation the date-only stamps can express) — every value
in that band gives the same answer on every candidate, so 6 h is a declaration, not a discovery. And
the midnight row is what makes `test_a_flight_across_midnight_is_one_sortie_and_not_two_days` a real
test rather than a green one: it is the only check the rejected mechanism fails.

## Why coverage cannot be required to be exactly 1.0

DGT publishes `proj:bbox` as the bounding box of the **returns**, not of the tile. Measured
2026-08-04, the far corner lands about a millimetre inside the lattice — a tile runs
`-21000.0 .. -20000.001` while its neighbour starts at `-20000.0` — so every internal seam leaves an
uncovered strip 1 mm wide. Over the chosen 2 km AOI that is 3.97 m² of 3,942,464 m², and over the
Manteigas candidate 8.07 m². `min_coverage = 1.0` therefore refuses **every multi-tile AOI in this
catalogue**, and its message read `covers 1.00 of the AOI, need 1.00`: a refusal that contradicts
itself on the page.

Two changes, both measured:

- **Coverage is the union, not the sum of per-tile overlaps.** The old sum double-counted where
  footprints overlap, which they do — the Pinhão tiles overlap by 0.1 m in y — and reported
  `1.00040004` for an AOI that is merely fully covered. `_covered_fraction` compresses the tile edges
  into elementary rectangles, so the answer is exact and cannot exceed 1.
- **The bar moved to 0.999,** which the two tests pin from both sides: seams measure `0.99999800`
  and the smallest single-tile hole (a corner tile, 200 m × 200 m of a 2 km box) measures
  `0.99000000`. Values of 0.98 and 0.99 accept that hole; 1.0 rejects the seams. Four orders of
  magnitude separate the artefact from the defect, which is the room the threshold works in.

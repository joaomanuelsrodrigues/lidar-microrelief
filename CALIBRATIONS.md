# Uncalibrated thresholds (Regra 14)

Every number here is declared, not justified by taste. `origin` says where the value came from;
`calibration target` says what would replace guessing with measurement.

| Parameter | Value | Where | Origin | Calibration target |
|---|---|---|---|---|
| `cell` | 0.5 m | CLI default | Matches the finest DGT published product | Terrace tread width at the chosen site (Task 6) |
| `k_min_returns` | 1 | `density.py` | Weakest defensible bar: one return is a measurement | Sensitivity sweep 1/2/4 against terrace legibility |
| `d_max_interp_m` | 2.0 m | `density.py` | 4 cells at 0.5 m; beyond it "nearby" stops meaning anything | Semivariogram of the measured DTM at the site |
| `max_void_fraction` | 0.35 | `precheck.py` | Above ~1/3 the DTM is majority-invented under canopy (F-047) | Measured void fraction vs terrace legibility |
| `max_window_m` | 4.0 m (unmeasured default) | `ground.py` | A ceiling on the radius search, **not a width the filter ever uses**: the radius doubles, so at 0.5 m cells this yields windows (1.5, 2.5, 4.5) m, and 4.0 and 6.0 are the same setting — see `windows_for()`. Sets the scale at which objects are found; measured, it does **not** decide whether risers survive | Largest object to be removed (tree crown, building) at the chosen site |
| `slope_threshold` | 0.3 (unmeasured default) | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs the official classification (`agreement()`) |
| `elevation_threshold_m` | 0.3 m (unmeasured default) | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs the official classification (`agreement()`) |
| `max_elevation_m` | 3.0 m | `ground.py` | **The parameter that decides whether terraces survive.** It caps every tolerance, so a riser is excused exactly when the cap exceeds it, at any window. At 3.0 m the filter tolerates two 1.5 m risers | **Largest true riser (or terrace wall) measured at the site** — the value has to stay above it |

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
| `max_cells` | 200,000,000 | `grid.py` | Memory ceiling: one float64 array of that many cells is ~1.6 GB, and the AOI is meant to be ~4 km² | Largest AOI that fits in the working machine's RAM at the chosen cell size |
| `limit` | 500 | `tiles.py` | Far above any anticipated AOI's tile count; otherwise arbitrary. Controls the STAC page size and truncation guard threshold. | Largest real AOI tile count actually observed in production queries |
| `min_coverage` | 1.0 | `tiles.py`, `select_tiles()` | Policy: 100% coverage required by default. The AOI defines the working area strictly; partial coverage is a refusal, not a shortfall to report. | Weakest defensible coverage per biome / survey season |
| `max_area_km2` | 200.0 | `tiles.py`, `select_tiles()` | Found in DGT's own QGIS plugin source code (via project design spec); client-code claim, not published spec | Confirm against actual provider behaviour by requesting above the limit |

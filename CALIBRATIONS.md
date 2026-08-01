# Uncalibrated thresholds (Regra 14)

Every number here is declared, not justified by taste. `origin` says where the value came from;
`calibration target` says what would replace guessing with measurement.

| Parameter | Value | Where | Origin | Calibration target |
|---|---|---|---|---|
| `cell` | 0.5 m | CLI default | Matches the finest DGT published product | Terrace tread width at the chosen site (Task 6) |
| `k_min_returns` | 1 | `density.py` | Weakest defensible bar: one return is a measurement | Sensitivity sweep 1/2/4 against terrace legibility |
| `d_max_interp_m` | 2.0 m | `density.py` | 4 cells at 0.5 m; beyond it "nearby" stops meaning anything | Semivariogram of the measured DTM at the site |
| `max_void_fraction` | 0.35 | `precheck.py` | Above ~1/3 the DTM is majority-invented under canopy (F-047) | Measured void fraction vs terrace legibility |
| `max_window_m` | TBD Task 12 | `ground.py` | Must be **smaller than the terrace tread** or the filter eats the step (spec §4.1) | Measured tread width at the chosen site |
| `slope_threshold` | TBD Task 12 | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs official classification |
| `elevation_threshold_m` | TBD Task 12 | `ground.py` | Progressive morphological filter, Zhang et al. 2003 | Agreement per class vs official classification |
| `max_elevation_m` | 3.0 m | `ground.py` | Caps the slope-dependent tolerance so a single wide window cannot excuse any drop | Largest true riser measured at the site |
| `max_cells` | 200,000,000 | `grid.py` | Memory ceiling: one float64 array of that many cells is ~1.6 GB, and the AOI is meant to be ~4 km² | Largest AOI that fits in the working machine's RAM at the chosen cell size |
| `limit` | 500 | `tiles.py` | Far above any anticipated AOI's tile count; otherwise arbitrary. Controls the STAC page size and truncation guard threshold. | Largest real AOI tile count actually observed in production queries |
| `min_coverage` | 1.0 | `tiles.py`, `select_tiles()` | Policy: 100% coverage required by default. The AOI defines the working area strictly; partial coverage is a refusal, not a shortfall to report. | Weakest defensible coverage per biome / survey season |
| `max_area_km2` | 200.0 | `tiles.py`, `select_tiles()` | Found in DGT's own QGIS plugin source code (via project design spec); client-code claim, not published spec | Confirm against actual provider behaviour by requesting above the limit |

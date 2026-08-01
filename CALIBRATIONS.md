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

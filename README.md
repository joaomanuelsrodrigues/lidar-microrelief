# microrelief

Microrelief over the terraces of Sistelo (Arcos de Valdevez, Portugal), derived from raw airborne
LiDAR — a 0.5 m DTM, DSM and CHM in which **every cell declares what it is made of**: measured,
interpolated from the nearest measured cell, or undetermined. Undetermined cells are published as
holes,
deliberately. The inputs are the four raw DGT LAZ tiles of the AOI (845,372,695 bytes, one sortie,
flown 2026-03-30); DGT's own published rasters are **not an input** to anything here — nothing in
this repository reads them at all. The only official product used is the ASPRS classification the
LAZ returns already carry: it gates acceptance (a tile with no official ground class is refused),
names the noise classes excluded from every surface (7 and 18), travels per cell as the published
`n_ground_asprs` band, and anchors the comparison below. What it never does is decide which cells
are ground in these surfaces — that decision is re-derived from the raw returns by our own filter.

## The picture

Open `viewer/index.html` and drag the wipe between any two of DSM, DTM, CHM and basis. Each band
is transparent exactly where it has nothing it can honestly publish, and the rules differ by band:
the **DTM** on undetermined cells — nothing in the cell qualifies as measured ground, either no
return at all or only returns the filter rejects, and no measured cell lies within 2 m to borrow
from; the **CHM** wherever the cell's own ground was not measured, because a height against
borrowed ground is a difference between a measurement and somewhere else; the **DSM** only where
no return landed at all. The holes are on purpose. The basis layer is the exact per-cell answer:
green = measured, orange = interpolated, red = undetermined.

## How to reproduce

```
microrelief select   --aoi aoi/aoi.geojson --out outputs/selection.json
microrelief precheck --aoi aoi/aoi.geojson --cell 0.5 --ground-fraction 0.4
microrelief run      --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs/ \
                     --cell 0.5 --selection outputs/selection.json
```

`select` and `precheck` reach the DGT STAC catalogue and need no account; `run` touches no network
at all. Only the LAZ download itself needs an account, and it is manual: the provider's direct
token grant is closed to this client, so acceptance was the artefact — each file's size checked
byte-for-byte against the catalogue's `file:size` — never a status code (`SITE.md` §Acquisition).

## The numbers, from the run of 2026-08-08 (0.3.0)

Every figure below is quoted from `docs/live-smoke.md`, which carries the commands and their
verbatim output. The machine-readable record is `viewer/provenance.json` (a tracked copy of the
run's `outputs/provenance.json`). The values are unchanged from the 2026-08-05 run — 0.3.0
widened the footprint guard and recalibrated a cap the default windows never reach, and the
run's byte-identity with its own second pass, plus value-identity with 0.2.0's bands, is
demonstrated in the record.

| What | Value |
|---|---|
| Grid | 3960 × 3960 cells of 0.5 m (3.9204 km²), EPSG:3763, one common grid for everything |
| Cell basis | measured 74.6% · interpolated 25.2% · undetermined 0.2% |
| Closed-form void expectation | 0.117% of cells empty, given the measured 27.0 pts/m² and every return reaching the ground — read beside the cells with no measured basis (the 25.2% interpolated plus the 0.2% undetermined); the gap between the two is the combined effect of canopy interception and the ground filter's own rejections — a cell is measured only when the filter calls it ground (`density.py`) |
| Agreement with the official classification | ground recall 0.999 · non-ground recall 0.495 · accuracy 0.749 · **majority-class null 0.503** |
| Reproducibility hash | `c69dd559d915c3f02d00f91bda65759c7cafce48f2a3bfd6c64c2badc0192f33` |
| Cost | 41.3 s wall clock, 4.4 GiB peak resident |

ASPRS noise classes 7 and 18 (Low Point / High Noise) are excluded from every surface and counted
per tile as `point_count_noise_excluded` — 0.228% of returns here. This delivery's class 7 spans
both extremes (84.2 m to 1752.5 m, against classified ground topping out at 506.1 m); kept, it
produced a 1524.55 m CHM and pushed the minimum surface below the terrain.

## Ground classification

A progressive morphological filter (Zhang et al., 2003) over the per-cell minimum surface — our
own implementation, so that every derived product is re-derived from the raw returns. The
parameters, and what is actually known about them (`CALIBRATIONS.md`):

- The window search doubles its radius, so under `max_window_m = 4.0` the filter runs windows of
  1.5, 2.5 and 4.5 m at 0.5 m cells; the ceiling is a bound the search never reaches.
- `slope_threshold = 0.3` and `elevation_threshold_m = 0.3` are starting values declared
  **uncalibrated** rather than presented as tuned. The tolerance formula follows Zhang et al.
  (2003) with one declared variant: its slope term uses the full window width where the paper's
  eq. (7) uses the increment between consecutive windows, so the tolerance is systematically
  larger — more permissive toward ground. The values themselves are not the paper's: Zhang's
  experiments set them per site (s = 0.08 on flat urban terrain, 1.2 in mountains; dh0 = 0.25 m
  and 0.2 m), which is the case for declaring rather than borrowing them.
- `max_elevation_m = 3.5` is the parameter that decides whether terrace risers survive: it caps
  every tolerance, so a riser is excused exactly when the cap exceeds it, at any window. Measured
  on the synthetic hillside fixture: at 3.0 m all five terrace levels survive every window tried;
  at 1.0 m a whole level is lost. **The cap is now site-calibrated:** the tallest verified
  terrace riser at Sistelo measures **2.98 m** (16,596 candidates, top-12 verified one by one —
  everything taller is built walls, a gully edge, or steps carried by one or two returns), and a
  cap 2 cm above a riser is not above it within the 0.2–0.3 m LiDAR error band, so it moved from
  3.0 to 3.5. Method, figures and the ruling: `docs/riser-measurement.md`. At the default
  windows the cap is unreached (largest tolerance 1.65 m), so the change alters no output here.

The comparison against the official ASPRS classification exists to **quantify the difference, not
to beat the DGT** — the official ground class never decides a cell in these surfaces; here it is
the reference being quantified against, **not an input** to the filter. Two other official labels
*are* inputs upstream of it: classes 7 and 18 are removed before the minimum surface the filter
reads is formed, and a tile carrying no class 2 at all is refused outright (`read.py`). Ground recall 0.999,
non-ground recall 0.495, accuracy 0.749, majority-class null 0.503; the number to read beside
those is `fp = 3,889,074` — 0.2505 of compared cells are cells where this filter says ground and
the official classification has no ground return, which is the expected shape of a minimum-surface
filter under canopy, declared rather than tuned away.

## What this does not support

- **Byte-identical replay on real data is not established — now with a measured bound.** The
  2026-08-05 session saw, in four reads of the 845 MB dataset, one single corrupted coordinate
  and one outright `IoError: failed to fill whole buffer` (source files intact, `sha256sum`
  stable). A pre-registered hunt (2026-08-08, `docs/live-smoke.md`) then ran **192 controlled
  re-reads** — parallel and single-thread backends, idle and under 20 GiB of active memory
  pressure, warm and cold page cache — and reproduced **neither**: zero events, byte-agreement
  everywhere, so no code remedy (such as pinning a backend) is justified by the data. The
  **root cause stays open**: whatever fired that day was state-dependent, and the candidates the
  experiment could not exercise — that day's host-side pressure, a one-off non-ECC memory event,
  an in-process interaction — remain named rather than excluded. The 0.3.0 run and its second
  pass are byte-identical across all six bands and the record minus its `created_utc` timestamp
  (deliberately excluded from the hash, and the one field two honest runs cannot share); two
  clean passes are two clean passes, not a stability proof. `read_laz` refuses any return outside its tile's declared box
  (as of 0.3.0, noise classes included), which converts a silent corruption into a loud failure;
  it does not make replay stable.
- **Cross-machine replay is not verified.** Byte-identity holds on this machine's clean reads and
  on the synthetic goldens; no second machine has reproduced the run.
- **The reproducibility hash cannot see a code change by itself.** It covers package version,
  grid, parameters and input digests; the only thing that makes a *code* change visible is
  `__version__`, and nothing enforces bumping it. A run whose code changed without a version bump
  would reuse a hash. A warn-class CI step (`scripts/check_version_bump.sh`) now flags a commit
  that touches `src/` without a version change — it narrows the gap without closing it, and its
  blindness (multi-commit pushes, dirty-tree runs) and over-reach (comment-only edits flag too)
  are declared in its header.
- **The ground-fraction term of the void expectation is a reference model, not a measurement** —
  it is the null the measured void share is read against, and tuning it to match would destroy the
  comparison.
- **Ground is decided per cell, not per return.** `n_ground_asprs` is the official per-cell count,
  not ours.
- **Interpolation is nearest-measured with no smoothing**, never farther than 2 m. The
  borrowed-from cell indices exist only inside the run; they are not among the six published
  bands.
- The AOI is a single sortie (2026-03-30), so `mixed_epochs = false`. An AOI mixing flight dates
  would be a mosaic of moments; the pipeline refuses one unless told to accept it, and the record
  declares it.

## Attribution

Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, licensed
**CC BY 4.0**. Derived products (ground classification, DTM, DSM, CHM) produced by `microrelief`;
**not reviewed or endorsed by DGT**. The attribution travels inside every exported GeoTIFF's tags
and in `viewer/provenance.json`, so it reaches whoever holds the file, not only whoever found this
page.

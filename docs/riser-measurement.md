# Measuring Sistelo's tallest real riser

`CALIBRATIONS.md` declares `max_elevation_m = 3.0` with the calibration target *"largest true riser
(or terrace wall) measured at the site — the value has to stay above it"*. This document is that
measurement. The method below was written and committed **before** any elevation data was examined
for this purpose; everything under "Results" was filled in afterwards, and nothing above it was
edited once measurement began (corrections, if any, land beside the original, dated).

## Why this surface, and why not the DTM

The measurement runs on the per-cell minimum of **official ASPRS class-2 returns**
(`min_z_ground_asprs`, recomputed from the four tiles with `scripts/measure_risers.py`). Not on our
DTM, and not on the surface our filter classifies — deliberately: `max_elevation_m` is the parameter
being calibrated, so any surface our own filter shaped is circular here. If the current cap already
eats a real riser, the DTM shows a smoothed interpolation exactly there, and measuring the DTM would
confirm the cap with the cap. The official classification is independent of every parameter in this
pipeline (it is produced by the provider), which is what makes it usable as a reference — the same
reason `agreement()` compares against it.

Cost of that choice, declared: official ground is sparse under dense canopy (24.5% of returns
AOI-wide), so profiles break where there is no class-2 return, and coverage inside the measurement
zone is reported alongside the result.

## Zone, fixed from documentary facts only

The claim being calibrated concerns the **documented amphitheatre terraces** around the village
(SITE.md, criterion 3: named in Decreto n.º 4/2018 / Portaria n.º 45/2018). The zone is fixed from
facts already in `SITE.md` — the AOI centre (−20000, 256000) sits 22 m from the OSM village point
and 186 m from the church at (−19916, 256166) — and not from any inspection of relief:

> **Zone Z:** the square 800 m × 800 m centred on (−20000, 256000), i.e. x ∈ [−20400, −19600],
> y ∈ [255600, 256400], EPSG:3763.

This contains the village core, the church, and the amphitheatre slopes around them. It may also
contain river banks and road cuts; those are real terrain steps but not terrace risers, and the
verification step classifies them rather than letting the definition silently absorb them.
Steps outside Z are reported as context only and carry no weight in the verdict.

## Step definition (the instrument)

On 1-D profiles extracted through Z along four directions (rows, columns, both diagonals; diagonal
sample spacing √2 · 0.5 m), a **riser candidate** is a contiguous run of samples where the local
slope between consecutive valid samples is ≥ `s_steep`, bounded on both sides by **treads**: runs of
≥ `tread_len` where |slope| ≤ `s_tread`. Its **height** is the elevation difference across the steep
run. Profiles break at cells with no official-ground return (NaN); a run containing a break is
discarded, not bridged.

Instrument parameters — these shape what the instrument can see, so they are declared here and are
**not** production thresholds (none of them ships in `src/`):

| Parameter | Value | Why |
|---|---|---|
| `s_steep` | 0.8 (≈ 38.7°) | A wall face sampled at 0.5 m appears as slope ≥ ~1.5 head-on; 0.8 keeps oblique crossings (worst in-plane obliquity of 4 directions ≈ 22.5°) while excluding ordinary steep hillside (< 38°) |
| `s_tread` | 0.27 (≈ 15°) | A tread is a worked platform; 15° is generous for one |
| `tread_len` | 2.0 m (4 samples) | Shorter flats occur mid-slope by chance |
| `max_riser_width` | 3.0 m (6 samples) | A degraded/battered wall spreads; wider than 3 m of continuous steep is a slope, not a wall |
| `min_height` | 0.5 m | Below the LiDAR error band + step-of-interest floor; keeps the candidate list finite |
| cluster radius | 5 m | The same wall crossed by adjacent profiles is one riser, not many |

**What this instrument cannot see, stated up front:** a riser whose treads slope more than 15°
(terraces cut into very steep ground), a wall spread wider than 3 m, and anything under canopy dense
enough to leave no class-2 returns. To bound the miss, the **unconditional short-range relief** is
reported beside the conditional measure: for lags of 1–4 samples along the same profiles, the
distribution of |Δz| — the tallest riser cannot exceed the tallest short-range relief, so if the
conditional maximum sits far below the unconditional one, the gap is examined and explained rather
than ignored.

## Verification of candidates

Top clusters by height (at least the top 5, and always enough to establish the tallest *verified*
riser plus two more) are each verified against: (a) position — river course, roads, buildings
(class-6 counts in the neighbourhood); (b) form — a terrace riser runs roughly along contour with
tread above and below, a river bank follows the drainage line, a road cut pairs with a bench;
(c) support — number of official-ground cells in the steep run and its treads (a step carried by
one or two returns is reported as unsupported, not counted). Each verified candidate is labelled
`terrace riser` / `river bank` / `road cut` / `other` / `unsupported`, with its coordinates kept in
this document so the labelling can be re-done by a reader.

## Pre-registered verdict rule

Let H = the tallest **verified terrace riser** in Z.

- **H < 2.5 m** — the cap passes its own rule with margin; the `max_elevation_m` row in
  `CALIBRATIONS.md` moves from unmeasured target to measured, citing this document.
- **2.5 m ≤ H < 3.0 m** — the cap technically holds but the margin is thinner than the measurement
  is precise; surfaced to the operator before the final run.
- **H ≥ 3.0 m** — the cap fails its own rule ("the value has to stay above it"); STOP, operator
  decision, since the parameter is inside the reproducibility hash and re-parameterising is a
  result, not a tweak.

Additionally, for the top verified risers: if the published DTM shows those cells as `interpolated`
rather than `measured` (basis band), the current cap is already biting a real riser, and that is
reported regardless of H.

## Results

*(filled in after the method above was committed)*

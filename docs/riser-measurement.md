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

*(filled in after the method above was committed at `738fc59`; nothing above this line was edited
since)*

**Commands** (2026-08-08):

```
PYTHONPATH=src .venv/bin/python scripts/measure_risers.py build \
    --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --cache .../riser_surface.npz
PYTHONPATH=src .venv/bin/python scripts/measure_risers.py measure \
    --cache .../riser_surface.npz --basis outputs/basis.tif --out docs/figures/riser/report.json
```

**Zone coverage:** 1,291,705 of 2,560,000 cells carry at least one official-ground return
(50.5%) — the other half is canopy dense enough, or built enough, to leave no class-2 return at
0.5 m, and profiles broke there rather than bridging.

**Distribution:** 16,596 candidates, 2,145 clusters. Heights p50 **1.67 m**, p90 **2.66 m**,
max 6.51 m. Unconditional short-range relief (the bound the conditional measure cannot exceed)
reaches 11.19 m at 2 m lag — the gap between 6.51 and 11.19 is exactly the steps the definition
excludes: gorge banks and walls flanked by slopes rather than 2 m treads.

**Verification of the top 12** (full table in `report.json`; figures in `docs/figures/riser/`):
every cluster above 4.6 m failed verification as a terrace riser —

| Ranks | Evidence | Label |
|---|---|---|
| 1, 2, 3, 5, 12 (6.51–4.62 m) | 1–3 aligned detections in 8 m; official-ground support median 1–4 returns per 5×5 cells; sit at edges of class-2 voids | **unsupported** — one or two returns carry the step |
| 4, 11 (5.26, 4.64 m) | 78/37 aligned detections: a long straight E–W edge with rectangular class-2 voids (building footprints) against it, 200 m S of the church | **built** — road/retaining-wall line, not terrace fabric |
| 8 (4.78 m) | 7.8 m from the church | **built** — churchyard wall |
| 10 (4.72 m) | 40 aligned detections on a sharp sinuous channel edge | **gully/lane edge** |
| 6, 7, 9 (4.97–4.74 m) | 6–10 aligned detections at the village margin among class-2 voids | **built/unsupported** |

**The tallest verified terrace riser is 2.98 m** (−20132.8, 256319.2), on a regular NE–SW
staircase in the north-west amphitheatre with 43 aligned detections and 2–4 official-ground
returns per cell; its across-step profile reads 271.05 → 270.88 | step | 267.90 → 267.69 —
flat tread, one-cell drop, flat tread. Its neighbours on the same flank measure 2.88, 2.86 and
2.81 m. Figure: `f01-terrace-2.98m.png`.

**Basis check:** the top clusters' midpoint cells all publish as `measured` in the DTM's basis
band. That is consistent, not alarming: with the shipped default `max_window_m = 4.0` the
windows run (1.5, 2.5, 4.5) m and the largest tolerance is 0.3 × 4.5 + 0.3 = **1.65 m — the
3.0 m cap is never reached at the defaults**, and a step on a monotone slope survives any
window regardless (`CALIBRATIONS.md`: a morphological opening removes local maxima only). The
cap governs users who raise the window, which is exactly where the calibration target matters.

## Verdict, and the ruling

H = **2.98 m** falls in the pre-registered **2.5 m ≤ H < 3.0 m** band: the 3.0 m cap nominally
stays above it by 2 cm, which is inside the LiDAR vertical error band (0.2–0.3 m) — precisely
the "margin thinner than the measurement is precise" case. Surfaced to the operator before the
final run, as the rule requires, with both options and the fragile assumption declared (the
2.98 m flank's "terrace" label rests on morphology alone; were it a natural bench, the next
verified riser is 2.88 m — same band, same decision).

**Operator ruling (2026-08-08): raise `max_elevation_m` to 3.5 m.** The target's own rule is
"the value has to stay above it", and 3.0 over 2.98 is not *above* within measurement noise;
3.5 clears the tallest verified riser plus the noise band while staying well below the built
walls (4.6–6.5 m) the filter exists to reject. Declared cost: at larger-than-default windows,
built walls up to 3.5 m would be excused as ground. At the shipped defaults the change is
byte-invisible in the outputs (the cap is unreached); it lands in 0.3.0 with the version bump,
and `CALIBRATIONS.md` now records the measured origin.

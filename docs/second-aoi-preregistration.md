# Second-AOI gate — pre-registered 2026-08-31, before the run

Everything this repository has ever run was **Sistelo**: the site, the delivery, the sortie, the
density, the classification. A pipeline validated on one AOI is validated against *that* AOI. What
a public release promises is that it works on somebody else's LiDAR, so that promise gets one
honest attempt to fail before the release is made.

This document is written and committed **before** the run. Its purpose is that the outcome cannot
be read backwards into whatever the run happens to produce.

## What was already known when this was written

Choosing the AOI meant querying the catalogue, and that alone found a defect, which is recorded
here so this document is honest about its own starting point: `_crs_epsg_from_wkt2` read the CRS
off the last `AUTHORITY` in the WKT, so 428 of 91,292 mainland tiles — those whose `PROJCS` node
carries no authority — were read as EPSG:9001, a unit code that resolves to a geographic CRS. It
is fixed in 0.4.3 and documented in `CALIBRATIONS.md`. **The run below happens on the fixed code**,
and the fix is not what this gate is testing.

## The AOI, and why this one

Valongo / Paredes, east of Porto: a 3x2 km block of six tiles, inset 10 m, bounds
`[-39990, 169010, -37010, 170990]` in EPSG:3763.

    LO-160470-07-2025  LO-160471-07-2025  LO-161470-07-2025
    LO-161471-07-2025  LO-162470-07-2025  LO-162471-07-2025

It was chosen for its **capacity to fail**, not for convenience. It differs from Sistelo on five
axes at once:

| | Sistelo | this AOI |
|---|---|---|
| density | 25.1–28.3 pts/m² | 16.0–21.4 pts/m² |
| tiles / seams | 4 (2x2), 2 internal seams | 6 (3x2), **3 internal seams** |
| grid | 3960 x 3960 = 15.7 M cells | 5960 x 3960 = **23.6 M cells** |
| terrain | terraced valley, closed canopy | hill, quarry, urban and industrial fabric |
| delivery | 2026-03-30, WKT with a PROJCS authority | 2025-12-08, WKT **without** one |

## The commands, fixed in advance

    microrelief select   --aoi aoi/valongo.geojson --out <sel>.json
    microrelief precheck --aoi aoi/valongo.geojson
    microrelief run      --aoi aoi/valongo.geojson --laz ~/data/dgt-laz \
                         --out <out> --selection <sel>.json --attribution "<DGT CC BY 4.0>"

**No flag will be added to force a product.** Not `--allow-sparse`, not `--allow-mixed-epochs`, not
a widened `--max-void-fraction`. If the pipeline refuses, the refusal is the result.

## The verdict rule

- **PASS** — the products come out, the record is internally consistent, and every refusal that
  fires is correct and legible. *A refusal is not a failure; it is the behaviour the piece sells.*
- **FAIL** — a product that is **plausible but wrong** (the class that matters), or a refusal whose
  stated reason is not the real one, or a crash with no named reason.
- **INCONCLUSIVE** — this AOI could not exhibit the class. Declared as such, never rounded up to
  PASS: *"no new problem"* and *"this AOI could not have shown one"* are the same output and not
  the same thing.

Overall PASS requires every hazard below to be PASS or INCONCLUSIVE-with-its-reason, and no FAIL.

## The five hazards, each with what would refute it

**H1 — `max_elevation_m = 3.5` is a Sistelo measurement** (tallest verified riser 2.98 m). Somewhere
else it may excuse a real wall as ground, or reject a real step.
*PASS if* ground recall against the official ASPRS class 2 is **≥ 0.90** and overall agreement
**exceeds the majority-class null**. *FAIL if* accuracy ≤ the null — the filter would be doing no
better than guessing while still publishing a complete-looking surface. *INCONCLUSIVE if* class 2
is absent, since there is then nothing to score against.

**H2 — the classification may differ.** Class 2 may be missing; classes 7/18 may carry worse
extremes than Sistelo's 84.2–1752.5 m.
*PASS if* a missing class 2 publishes `agreement: null` rather than a fabricated number, the noise
exclusion is reported as `point_count_noise_excluded`, and the CHM's maximum is physically possible
for this terrain (**< 60 m**). *FAIL if* the CHM carries impossible values with nothing declaring
it — that is 0.2.0's class-7 bug returning in a new delivery.

**H3 — the network path has only ever been exercised for Sistelo's tiles.**
*PASS if* `select` and `precheck` complete against the live catalogue and the record publishes
both `point_count_catalogue` and `point_count_measured`, so any disagreement is visible rather than
smoothed. *FAIL if* the two are made to agree by construction, or the catalogue's facts are absent
without being declared absent.

**H4 — read instability at ~5 GiB has never had a root cause.** This grid is 1.5x Sistelo's.
*PASS if* the run is clean, **or** refuses with the reason named. *FAIL if* a corrupted read
produces a product anyway. The run is done **twice** and the two `reproducibility_hash` values and
per-band digests compared. Pre-registered reading: **if they differ, that is the declared open
limitation reproducing — a finding, not a FAIL of this gate**, and it is reported as such.

**H5 — the common grid and the seam, with six tiles instead of four.**
*PASS if* no internal seam is visible in the `basis` band: the share of non-measured cells in the
three columns either side of each internal seam (x = -39000, -38000; y = 170000) is within **2x**
the AOI-wide non-measured share. *FAIL if* a seam line of undetermined or interpolated cells runs
along a tile boundary — that is the multi-source common-grid failure this repository's own
constraint ledger names.

## What this run does not do

The published numbers stay Sistelo's. Nothing measured here enters `README.md` or the case study
without a separate ruling; the product of this run is a **verdict on readiness**, plus a
`docs/live-smoke.md` entry if it passes.

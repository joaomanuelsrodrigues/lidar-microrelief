# Self-check against the pre-registered rubric

2026-08-06. Written before calling the judge, per `RUBRIC.md`. Method: the five answers below were
written **from memory** in one sitting, using the numbers of our own run of 2026-08-05, with no
file opened mid-answer. The verification pass afterwards checks every number against the record
and logs misses instead of erasing them — a self-check with no failure mode on record is a
self-check no one should believe.

## 1. Ground filtering

A progressive morphological filter after Zhang et al. (2003), our own implementation in
`ground.py`, applied to the per-cell **minimum surface** (`min_z_all`, accumulated after excluding
ASPRS noise classes 7 and 18). Parameters of the run: `max_window_m = 4.0` — a ceiling on a radius
search that doubles, so the windows actually run are 1.5, 2.5 and 4.5 m at 0.5 m cells and the
ceiling is never reached; `slope_threshold = 0.3` and `elevation_threshold_m = 0.3` — the Zhang
defaults, declared **uncalibrated** in `CALIBRATIONS.md` rather than dressed as tuned;
`max_elevation_m = 3.0` — the parameter that actually governs terrace survival, because it caps
every tolerance: measured on the synthetic hillside, 3.0 m keeps all five terrace levels at any
window while 1.0 m loses a whole level. "Why those values": cell 0.5 m matches the finest DGT
published product; the window story was corrected by measurement (the intuitive "window must stay
under the tread" claim is false — a morphological opening cannot damage a monotone staircase);
the cap must stay above the site's largest true riser, which is declared as the calibration
target, not yet measured on site.

Agreement with the official classification, per class with the null beside it: **ground recall
0.999**, **non-ground recall 0.495**, **accuracy 0.749**, **majority-class null 0.503**. The
number to read beside those: `fp = 3,889,074` of `n_cells = 15,522,469` compared cells (0.2505) —
cells where we say ground and the official classification has no ground return, the expected
shape of a minimum-surface filter under canopy, declared rather than tuned away.

## 2. Common grid

`grid.py` defines `Grid` and `grid_for_bounds`; the run builds **one** grid from the AOI's
declared `bounds_epsg3763` (3960 × 3960 cells of 0.5 m, EPSG:3763, origin at the AOI's top-left) —
declared bounds, not a re-derivation through WGS84, which is exactly the defect the first CLI run
found (a 3961 × 3962 grid half a cell off, 11,882 cells outside every tile). No elementwise
arithmetic between per-tile windows can happen because **per-tile rasters never exist**:
`accumulate.py` streams every tile's returns directly into per-cell accumulator arrays indexed by
that one grid (`CellStats`: `min_z_all`, `max_z_all`, `n_all`, `n_ground_asprs`, …), and every
downstream product — ground mask, basis, DTM/DSM/CHM, agreement — reads those accumulated arrays.
The tiles are all natively EPSG:3763, verified per file from the LAZ VLR; an ambiguous CRS is a
refusal, not a default.

## 3. Voids

Of the grid's cells: **measured 74.6% · interpolated 25.2% · undetermined 0.2%** (record values
0.7460 / 0.2521 / 0.0019). A cell is *measured* when our filter's ground mask holds its own
minimum — consistency check by identity: `tp + fp = 7,809,752 + 3,889,074 = 11,698,826`, which is
exactly the count of measured cells in the basis band. *Interpolated* borrows the nearest measured
value within `d_max_interp_m = 2.0 m` and records which cell it borrowed from; *undetermined* has
nothing within reach and is published as a hole.

Closed-form expectation: with measured density ρ = 27.0 pts/m² and cell area 0.25 m², a Poisson
null with every return reaching the ground leaves `exp(−27.0 × 0.25) ≈ 0.117%` of cells empty.
The measured emptiness (25.4% = interpolated + undetermined) against that 0.117% is the point of
the pair: the gap **is the canopy** — only 0.2448 of returns are ground here, and the
ground-fraction term of the expectation is a reference model (the null), not a measurement.

## 4. Provenance and reproducibility

**Do two runs produce identical bytes?** On the synthetic goldens, yes — two fixtures
(`ramp_with_void`, `canopy_dense`) with locked hashes. On the real data, **not established**: of
four reads of the 845 MB, two were clean and byte-identical across all six exported bands, one
returned a single corrupted coordinate (visible only as second-order damage — a tile's measured
density collapsing because the bounding box it divides by exploded), and one failed outright with
`IoError: failed to fill whole buffer`. The sources are intact (`sha256sum` stable), and the root
cause is **not established** — parallel LAZ decompression, WSL2 memory pressure and non-ECC RAM
are all live candidates. What changed after: `read_laz` refuses any return outside the tile's
declared `proj:bbox` (+1 cm tolerance), converting the silent version into a loud failure. It
does not make replay stable, and the README says so in those words. Cross-machine replay:
unverified, declared in `known_limitations`.

**Can a stranger reproduce from the record alone?** The record (`viewer/provenance.json`, tracked
copy of the run's `outputs/provenance.json`) carries the input file names (never local paths),
their sha256 digests and per-tile counts (catalogue and measured, plus `point_count_noise_excluded`),
the grid, all seven parameters, the package version and the `reproducibility_hash`
(`e5e8eb9b031f…`). A stranger needs the LAZ from DGT — the download is manual, by account, and
`SITE.md` records why — after which the three CLI commands in the README re-run the product. The
hash's own limit is declared: it makes a *code* change visible only through `__version__`, and
nothing enforces bumping it.

**Does the CC-BY attribution reach the consumer?** Yes, by construction: the DGT CC BY 4.0
attribution string, with the "not reviewed or endorsed by DGT" clause, is written into every
exported GeoTIFF's tags and into `provenance.json` — it travels with the file, not with the page.

## 5. Refusals

Three, with the reason in the message:

1. **Mixed epochs.** `select_tiles` on the Côa candidate: *"AOI spans 3 sorties (2024-11-11…,
   2024-11-18…, 2024-12-11…); a mosaic of two epochs is a product made of two moments — pass
   allow_mixed_epochs to accept and declare it."* Verbatim in `SITE.md`'s triage output.
2. **Impossible return.** `read_laz` refuses a return outside the tile's declared `proj:bbox`
   (+`FOOTPRINT_TOLERANCE_M`): the catalogue's box is the box of the returns, so a return outside
   it is a corrupted read, not terrain. Added after the replay instability was measured; the
   refusal message names the tile and the offending coordinate.
3. **Silent truncation.** `tiles.py` refuses a STAC result that exactly fills its page limit with
   no way to know whether more exist — a full page with no `next` is a refusal, because a
   truncated tile list would quietly produce a partial mosaic. Same family: coverage below
   `min_coverage = 0.999` refuses with the measured fraction in the message.

Also on record (not needed for the three): ambiguous/missing CRS; non-finite x/y/z coordinates
(a NaN offset in a LAS header produces NaN coordinates with nothing formally invalid); a grid over
`max_cells`; an all-NoData band in the renderer; an unknown basis code in the renderer.

---

## Failing conditions, applied

- *"I used the published raster"* — does not occur: DGT's published rasters are an input to
  nothing here; the official classification appears **only** in the agreement comparison, and
  `n_ground_asprs` is declared as the official count, not ours.
- *"I did not verify"* — does not occur as an answer, but its honest sibling does: Q4's
  byte-replay is **verified-and-found-unstable** (four reads: two clean, two failed), which is a
  measured result with the root cause declared open, not an unverified claim.

## Verification pass (after writing, against the record)

Checked every number above against `viewer/provenance.json`, `docs/live-smoke.md`,
`CALIBRATIONS.md` and the code after the answers were written. **One miss, recorded:** the fp
share was first written as 0.2506 here, in the README and in the live-smoke correction note; the
recomputation says 3,889,074 / 15,522,469 = 0.25054 → **0.2505**. A rounding slip of mine,
propagated to three files before being caught by this pass, and fixed in all three in the same
commit that records it. Two imprecisions besides, named rather than silently tightened: (a) the
measured emptiness in Q3 is 25.4% by subtraction (1 − 0.746); the record's own split is
0.2521 + 0.0019 = 0.2540 — consistent, but the README quotes the split, not the sum; (b) in Q5.2
the refusal message's exact wording was not reproduced from memory (the verbatim text lives in
`read.py:139-143`; what was written matches its substance — tile named, corrupted read named).
The Q5.3 truncation message was verified verbatim-in-substance against `tiles.py:122`, and the
refusal inventory (CRS at `read.py:72-76`, finitude at `read.py:111-113`, coverage at
`tiles.py:310`) checks out.

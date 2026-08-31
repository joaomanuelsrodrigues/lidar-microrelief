---
name: microrelief
description: Build a DTM, DSM and CHM from a LAS/LAZ point cloud where every cell declares whether it is measured, interpolated or undetermined, with a provenance record. Use when a user asks for a terrain model, canopy height, ground classification or bare-earth surface from LiDAR and needs to know what the output does not know. Refuses an ambiguous CRS instead of guessing.
license: Apache-2.0
compatibility: Python 3.12+ and the microrelief package installed in the working repository (README, Install). The dgt extra is needed only for the DGT catalogue commands.
metadata:
  version: "0.4.4"
---

# microrelief — terrain products from LiDAR that say what they do not know

## When to use this

The user has a LAS/LAZ file (or a directory of them) and wants a DTM, DSM, CHM or a ground
classification — and the answer has to say where it is measured, where it borrowed a neighbour,
and where it has nothing. Not for orthophotos, not for point-cloud editing, not for reprojection
(`docs/recipes.md` shows PDAL or LAStools doing that first).

## The commands

1. `microrelief run --aoi <aoi.geojson> --laz <dir> --out <dir> --attribution "<source + licence>"`
   — the product. Reads every `.laz` directly inside `--laz`; touches no network.
2. Read `<out>/provenance.json` before reporting anything (section below).
3. DGT (Portugal) only: `microrelief select --aoi <aoi.geojson> --out <selection.json>` picks the
   tiles from the public catalogue, and `microrelief precheck --aoi <aoi.geojson> --cell 0.5`
   estimates the void before any download. Pass the selection to `run` with `--selection` so the
   record can compare what the provider claimed with what was measured; without it the record
   says it does not know what the provider claimed, which is correct, not an error.

Worked example in this repository — real data, about a minute:

    uv run microrelief run --aoi examples/sistelo-sample/aoi.geojson --laz examples/sistelo-sample \
        --out outputs/sample --attribution "$(cat examples/sistelo-sample/attribution.txt)"

On the author's machine and on GitHub's runner this gives a 300 × 300 grid of 0.5 m cells; basis
56.2 % measured, 43.1 % interpolated, 0.7 % undetermined; expected void 1.3 %; agreement with the
delivery's ground class: accuracy 0.837 against a majority-class null of 0.587 (recall ground
0.999, non-ground 0.723); record hash `f67b2f033d23…`. `tests/test_sample.py` locks the values and
`tests/case_study/test_readme_claims.py` locks this copy of the hash.

## Before running — the input contract (ask the user, never assume)

- Every `.laz` declares a CRS that resolves to an EPSG code, **projected, in metres**, and the AOI
  is in that same CRS. A bare WGS84 ring needs `--crs <epsg>`: **ask which** — never pick a
  national grid for the user.
- The AOI is a GeoJSON Polygon; `properties.bounds` + `properties.bounds_epsg` is what the CLI
  reads.
- `--attribution` is required and has no default: ask for the data source and licence, verbatim.
- ASPRS class 2 is optional (present, the record reports agreement against it); classes 7 and 18
  are excluded as noise and counted.
- Parameters the record declares **uncalibrated** (`CALIBRATIONS.md`): `--cell`,
  `--k-min-returns`, `--d-max-interp-m`, `--max-window-m`, `--slope-threshold`,
  `--elevation-threshold-m`. `--max-elevation-m` (3.5 m) is the one that was measured, at one
  site, against a 2.98 m terrace riser — re-measure at a new site. Change a parameter only when
  the user asks, and report the change.
- `precheck` has its own triage knobs (`--ground-fraction`, `--max-void-fraction`,
  `--allow-sparse`); `select` refuses tiles flown on different dates unless
  `--allow-mixed-epochs`.

## Reading the record — report these, in this order

- `honesty.fraction_measured` / `fraction_interpolated` / `fraction_undetermined` — the headline.
- `honesty.expected_void_fraction` beside the undetermined + interpolated share — the null.
- `agreement` (may be `null`): `recall_ground`, `recall_nonground`, `accuracy` **with**
  `majority_class_null` — never accuracy alone.
- `known_limitations` and `uncalibrated_thresholds` — quote them; they are part of the answer.
- `reproducibility_hash` and `inputs[].sha256` — what the user needs to reproduce the run.

## When it refuses

A non-zero exit with the reason on stderr. The reason is the message to relay — verbatim — and
the exit code only says who refused: **2** when the CLI refused the AOI's shape or a CRS it was
not told (`bounds` without `bounds_epsg`, a ring with no working CRS, a tile missing from the
selection); **1** for everything the package refused with a named error — `CRSError` for a
geographic or non-metre CRS (also when it comes from `--crs`), `ReadError` for a file that
declares no CRS or no EPSG code, non-finite coordinates, or a return outside the box its
catalogue entry declares. Do not retry with a guessed flag; ask the user.

## Output files

`mdt.tif` (DTM) · `mds.tif` (DSM) · `chm.tif` · `basis.tif` (0 undetermined · 1 measured ·
2 interpolated; NoData 255) · `n_all.tif` · `n_ground_asprs.tif` (NoData −1) · `provenance.json`.
Every GeoTIFF carries the attribution string in its tags. QGIS styles: `styles/*.qml`.

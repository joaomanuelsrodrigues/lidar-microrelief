# Recipes — your point cloud into `microrelief`, and its output into QGIS

`microrelief run` refuses rather than guesses: every `.laz` must declare a projected, metre-based
CRS that resolves to an EPSG code, and the AOI must be in that same CRS (`README.md`, *Your own
data*). These recipes do the preparation with tools you probably already have. Each one says
whether the author exercised it; the exercised ones have their output in `docs/live-smoke.md`.

## PDAL — reproject and clip (exercised 2026-08-26 with PDAL 2.10.2 — `docs/live-smoke.md`)

    { "pipeline": [
      "in.laz",
      { "type": "filters.reprojection", "out_srs": "EPSG:25829" },
      { "type": "filters.crop", "bounds": "([minx, maxx], [miny, maxy])" },
      { "type": "writers.las", "filename": "prepared/in.laz", "a_srs": "EPSG:25829",
        "compression": "laszip", "minor_version": 4, "dataformat_id": 8 }
    ] }

`pdal pipeline recipe.json`. Keep the classification dimension (PDAL does by default); drop the
`filters.crop` stage if the file is already the size you want. Then:

    microrelief run --aoi aoi.geojson --laz prepared/ --out out/ --attribution "<your source and licence>"

A reprojected file lands on a different grid, so its numbers differ slightly from a run in the
original CRS — that is the projection, not an error.

## LAStools — `las2las` (not exercised by the author)

    las2las -i in.laz -o prepared/in.laz -target_epsg 25829 -keep_xy minx miny maxx maxy

`-target_epsg` reprojects a file that already carries a CRS; `-epsg` only *labels* one that does
not — use it only when you know the CRS the coordinates are in. Ground classification is not
required (`microrelief` derives its own); if the file carries class 2, the record reports
agreement against it.

## CloudCompare (not exercised by the author)

Crop with *Edit → Segment* or *Tools → Clean → Crop*; save as LAS 1.4. CloudCompare does not
reproject between coordinate systems and may not write a CRS: run the file through `las2las
-epsg` or PDAL's `writers.las` with `a_srs` afterwards, otherwise `microrelief` refuses it as
declaring no CRS.

## QGIS — open the result (exercised 2026-08-26 in QGIS 3.44, headless — `docs/live-smoke.md`)

*Layer → Add Layer → Add Raster Layer* on `basis.tif`; *Properties → Symbology → Style → Load
Style* → `styles/basis.qml`. Same for `mdt`, `mds`, `chm`, `n_all`, `n_ground_asprs`. The basis
colours are the viewer's (green measured, orange interpolated, red undetermined) and the styles are
generated from the package's own palette (`scripts/make_styles.py`), so they cannot drift from
the code. NoData (−9999 float, 255 basis, −1 counts) is in the GeoTIFF tags, so holes render
transparent. The continuous styles stretch to the values **in view** (QGIS's *Updated canvas*
origin — the only one a loaded style can re-stretch with; measured in `docs/live-smoke.md`), so
the ramp follows as you pan or zoom. To pin one range, set Min / Max in *Symbology* once.

## Attribution travels

Every GeoTIFF carries the `--attribution` string in its tags, beside the band name, the package
version and the record's hash: `gdalinfo out/mdt.tif | grep -i attribution`, or with rasterio's
CLI, `rio info --tags out/mdt.tif`. If you redistribute derived products, that string is what
your licence obligations point at.

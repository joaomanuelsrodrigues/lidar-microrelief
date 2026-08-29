# What this stands on — and where the gap actually is

A per-cell band saying what an elevation is made of is **not new**. It is an established convention
of agency DEM production, and this page names it, quotes it, and maps `basis` onto it. Read this
before assuming the `basis` band is an invention: it is not, and the project is stronger for saying
so plainly than it would be for leaving the question open.

Every quote below is from the producer's own specification.

## 1. The convention, in three products

### Copernicus DEM — a family of per-cell quality layers, one of which names the donor

*Copernicus Digital Elevation Model — Product Handbook*, v5.0, 29.11.2022, §1.2.5 "Quality
Layers". Table 5 lists **six**: Editing Mask, Filling Mask, Height Error Mask, Water Body Mask,
Source Data Layer and Accuracy Layer. The three that bear on `basis`:

- **EDM (Editing Mask)** — *"indicates all DEM pixels that were modified during the terrain and
  hydro editing process … The EDM represents the last editing process that was applied to a pixel."*
  Values (Table 6, first four of fourteen): `0` Void (no data), `1` Not edited, `2` Infill of
  external elevation data, `3` Interpolated pixels.
- **FLM (Filling Mask)** — *"All edited and filled pixels are flagged in this mask. **For filled
  pixels, the fill source is specified.**"* Table 7 codes the donor per pixel: `3` ASTER, `4` SRTM90,
  `5` SRTM30, `6` GMTED2010, `9` AW3D30, `101` DSM05 Spain, and more.
- **HEM (Height Error Mask)** — *"the corresponding height error for each DEM pixel in the form of
  the standard deviation derived from the interferometric coherence and geometrical considerations."*

FLM is **strictly more** than this project publishes: our band says *interpolated*; theirs says
*interpolated, from AW3D30*.

### ArcticDEM / REMA / EarthDEM — a measured-vs-filled mask, a count, and a spread

Polar Geospatial Center, mosaic component rasters:

- `*_datamask.tif` — *"Raster indicating DEM pixels with heights purely sourced from SETSM output (1)
  versus those that have been filled/merged with another dataset or mask out as NoData in quality
  control steps (0)."*
- `*_count.tif` — *"Number of contributing DEMs"* · `*_mad.tif` — *"Median absolute deviation of
  contributing DEMs"* · `*_mindate.tif` / `*_maxdate.tif` — dates of contributing DEMs.

### NASADEM — per-pixel source of the data

NASA Earthdata, NASADEM_HGT v001: *"The NUM layer indicates the number of scenes that were processed
for each pixel and the source of the data."*

## 2. Reading `basis` against those conventions

This is a **reading aid, not a claim of conformance.** The two taxonomies answer different
questions: EDM records *what was done to a pixel* (fourteen editing operations); `basis` records
*what the published value is made of* (three evidential states). They overlap; they are not the same
scheme, and this project does not implement the Copernicus specification.

| `microrelief` `basis` | our value | Copernicus EDM | ArcticDEM `datamask` |
|---|---|---|---|
| `measured` | `1` | `1` — Not edited | `1` — purely SETSM |
| `interpolated` | `2` | **`3`** — Interpolated pixels | `0` |
| `undetermined` | `0` | `0` — Void (no data) | `0` |

> **⚠️ The one thing to carry away from this table: our `2` is not their `2`.**
> `microrelief` `2` means *interpolated*. Copernicus `2` means *infill of external elevation data* —
> a donor dataset, which is a thing this project never does. Their *interpolated* is `3`. Two of the
> three codes coincide by luck and the third collides in the most misleading way available, so a
> raster from here must never be read with an EDM colour table, or vice versa.

Two further asymmetries, in both directions:

- **Theirs carries more where it is filled.** FLM names the donor; we have no donor to name, because
  an interpolated cell here borrows from a measured cell *in the same tile*, never from another
  dataset.
- **Ours distinguishes more where it is not.** `datamask` is binary, so ArcticDEM's `0` covers both
  of our non-measured states at once. Our `undetermined` is a published value with its own code, not
  an absence — NoData for the `basis` band is `255`, precisely so that `0` can mean something.

## 3. Where the gap actually is: the tool layer

The convention lives at the **product** layer and is absent at the **tool** layer. Checked against
the free tools a practitioner would actually reach for to fill voids in their own raster:

| tool | emits a per-cell "what is this made of" band? | evidence |
|---|---|---|
| GDAL `gdal_fillnodata` | **no** | the only mask option is *"-mask `<filename>` — Use the first band of the specified file as a validity mask"* — an **input** |
| PDAL `writers.gdal` + `window_size` | **no** | *"Cell distance for fallback interpolation"*; measured 2026-08-27 — it fills and forgets |
| GRASS `r.fillnulls` | **no** | one output parameter, *"Name for output raster map"*; the manual's own example tells you to derive the difference with `r.mapcalc` |
| SAGA `Close Gaps` | **no** | parameter table: *"Mask \| grid, input, optional \| `MASK`"* — an input, as in GDAL. One output, the filled grid |
| WhiteboxTools `FillMissingData` | **no** | read from the implementation (`fill_missing_data.rs`): one declared `--output`, one `output.write()`, no auxiliary raster |

So: **an agency that produces a DEM publishes its provenance; a person who derives a DEM from their
own point cloud with the standard free tools gets no such band, and is not prompted to make one.**
That is the gap this closes, and it closes it by default rather than as an option.

**The obvious objection, stated here rather than waited for.** The information is one raster-algebra
step away for anyone who keeps their pre-fill raster: `gdal_calc` over the original nodata mask
reproduces most of `basis`. That is true, and it is not the defence. The defence is that it is easy
and nobody does it — so the raster that leaves the pipeline and reaches a downstream consumer who
never saw the pre-fill state carries none of it. `basis` is a contract, not a by-product.

## 4. The number we decline to publish

Copernicus ships HEM: a per-pixel error in metres, derived from interferometric coherence — a sensor
model they own. **This project has no such model, and therefore publishes no error magnitude.**

The honest quantity available here is a different one: *how far away the nearest evidence is*, never
*how wrong this cell is*. The machinery for it already exists internally — an interpolated cell
records the row and column it borrowed from — but **the distance is not published as a band today.**
It is a ruled next step (2026-08-27), not a shipped feature, and it is listed here so the absence is
visible rather than discovered.

## 5. What this page does not establish

- **No full texts were read.** Every product claim above is from a producer specification; none of
  the five tools was executed. For each, the inference *"no declared output parameter ⇒ no such
  output"* is sound because each declares its outputs as parameters — but it is an inference.
- **GRASS, SAGA and WhiteboxTools were checked on 2026-08-29**; GDAL on 2026-08-27; PDAL was measured
  on 2026-08-27. Tools change. If any of them ships a fill mask, §3 gains a row and the claim
  narrows — and an issue pointing that out is welcome.
- **Whether the free GLO-30 download bundles EDM/FLM/HEM**, or only the DGED package does, was not
  settled. It does not affect the point: the convention is public and documented either way.
- **No patent or standards search.** ISO 19115 lineage and the OGC coverage-quality work were not
  examined; they would most likely add prior art, not remove it.

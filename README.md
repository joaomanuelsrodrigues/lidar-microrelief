# microrelief

[![ci](https://github.com/joaomanuelsrodrigues/lidar-microrelief/actions/workflows/ci.yml/badge.svg)](https://github.com/joaomanuelsrodrigues/lidar-microrelief/actions/workflows/ci.yml)
![licence](https://img.shields.io/badge/licence-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-%E2%89%A5%203.12-blue)

DTM, DSM and CHM from raw airborne LiDAR, plus a **basis** band that says for each cell whether it
was measured, interpolated from a neighbour, or left undetermined, and a provenance record that
names the inputs, the parameters and the known limitations. For anyone who needs a terrain model
that admits where it has nothing to say. Worked example: DGT LiDAR over the terraces of Sistelo,
Portugal.

![Basis layer over Sistelo](docs/viewer/basis.png)
*Basis layer: green = measured, orange = interpolated, red = undetermined. Drag the comparison
yourself: [live viewer](https://joaomanuelsrodrigues.github.io/lidar-microrelief/viewer/).*

## What this stands on

A per-cell band saying what an elevation is made of is **not new.** Copernicus DEM ships six quality
layers — its Editing Mask codes each pixel *Not edited*, *Interpolated* or *Void*, its Filling Mask
names the **donor dataset** for every filled pixel, and a Height Error Mask gives a per-pixel error in
metres; ArcticDEM ships `datamask`, `count` and
`mad`; NASADEM's NUM layer carries per-pixel count and source. The convention is mature, documented,
and belongs to the agencies that produce national and global DEMs.

**Where it is missing is the tool layer.** Fill the voids in your own raster with the free tools a
practitioner actually reaches for — GDAL `gdal_fillnodata`, PDAL `writers.gdal`, GRASS `r.fillnulls`,
SAGA `Close Gaps`, WhiteboxTools `FillMissingData` — and not one of the five hands back a band saying
which cells it just invented. In GDAL and SAGA the mask is an *input*. The fill is done and forgotten,
and the raster that reaches whoever gets it next is indistinguishable, cell by cell, from one that
was measured everywhere.

So this is not an invention. It is the agencies' provenance discipline brought down to the layer
where you derive a DEM from your own point cloud, made the default rather than an option. The
quotes, the mapping onto those conventions — our `interpolated` is `2` and Copernicus's is `3`, so
they are **not** interchangeable — and the objections a domain reader will raise are in
[`docs/prior-art.md`](docs/prior-art.md).

## Install

Python ≥ 3.12. Not on PyPI yet — install from the repository:

```
git clone https://github.com/joaomanuelsrodrigues/lidar-microrelief
cd lidar-microrelief
uv sync --extra dgt          # or plain `uv sync` if you bring your own LAZ and never touch the DGT catalogue
uv run microrelief --help
```

With pip instead of `uv`:

```
pip install "microrelief[dgt] @ git+https://github.com/joaomanuelsrodrigues/lidar-microrelief"
```

The `dgt` extra adds the one network dependency (`requests`) used by `select` and `precheck` to
read the DGT catalogue. `run` needs no network and no extra.

If the `microrelief` console script is not on your `PATH`, `python -m microrelief` takes the same
arguments and does the same thing. Both forms are exercised in the test suite, because until 0.4.1
the module form exited 0 having done nothing — and a silent success is worse than a failure.

## Try it — two minutes, real data

A 150 m × 150 m sample of DGT LiDAR ships in the repository (`examples/sistelo-sample/`, CC BY 4.0):

```
uv run microrelief run --aoi examples/sistelo-sample/aoi.geojson --laz examples/sistelo-sample \
    --out outputs/sample --attribution "$(cat examples/sistelo-sample/attribution.txt)"
```

You get six GeoTIFFs (`mdt`, `mds`, `chm`, `basis`, `n_all`, `n_ground_asprs`) and
`provenance.json`. On the author's machine the record's hash is `2da06987808e` and the basis is
51.6% measured · 42.3% interpolated · 6.1% undetermined; `tests/test_sample.py` reproduces the
record on every CI run. Open the rasters in QGIS with the styles in `styles/` (`docs/recipes.md`).

## Your own data

`run` reads every `.laz` directly inside `--laz` (not `.las`, not subdirectories). The contract,
each line a refusal with its reason when unmet:

- Anything laspy opens as LAS/LAZ; exercised so far: LAS 1.4, point format 8 (the DGT delivery).
  Other versions and point formats are untested rather than unsupported.
- The header declares a CRS that resolves to an EPSG code — **projected, in metres** — and it is
  the AOI's. No reprojection happens here; `docs/recipes.md` shows PDAL or LAStools doing it first.
- Every coordinate is finite: a header scale/offset that decodes to NaN or inf refuses the file.
- The classification dimension is read. **Class 2 is optional** — present, the record reports
  agreement against it; absent, `agreement: null` and the tile is named. Classes 7 and 18 (noise)
  are excluded from every surface and counted.
- The AOI is a GeoJSON Polygon; `properties.bounds` + `properties.bounds_epsg` is what the CLI
  uses. A bare WGS84 ring needs `--crs <epsg>`.
- `--attribution` is required and has no default: the record names the source you declare.

Without `--selection` (the DGT catalogue step) the record says it does not know what the provider
claimed, rather than repeating what it measured. Any provider other than DGT is **untested rather
than unsupported** — see *What has been exercised*.

## The Sistelo case study

Microrelief over the terraces of Sistelo (Arcos de Valdevez, Portugal), derived from raw airborne
LiDAR — a 0.5 m DTM, DSM and CHM in which **every cell declares what it is made of**: measured,
interpolated from the nearest measured cell, or undetermined. Undetermined cells are published as
holes,
deliberately. The inputs are the four raw DGT LAZ tiles of the AOI (845,372,695 bytes, one sortie,
flown 2026-03-30); DGT's own published rasters are **not an input** to anything here — nothing in
this repository reads them at all. The only official product used is the ASPRS classification the
LAZ returns already carry: it names the noise classes excluded from every surface (7 and 18),
travels per cell as the published `n_ground_asprs` band, and anchors the comparison below. A
delivery carrying no class 2 at all is not refused — the record publishes `agreement: null` and
names the tile, because a missing official comparison is a fact about the file, not a failure of
the surface. What the classification never does is decide which cells are ground in these
surfaces — that decision is re-derived from the raw returns by our own filter.

## The picture

Open `docs/viewer/index.html` and drag the wipe between any two of DSM, DTM, CHM and basis. Each of the
three **surface** bands is transparent exactly where it has nothing it can honestly publish, and
the rules differ by band: the **DTM** on undetermined cells — nothing in the cell qualifies as
measured ground, either no return at all or only returns the filter rejects, and no measured cell
lies within 2 m to borrow from; the **CHM** wherever the cell's own ground was not measured,
because a height against borrowed ground is a difference between a measurement and somewhere else;
the **DSM** only where no return landed at all. The holes are on purpose. The viewer's CHM is
drawn at 64 colour levels (about 0.67 m per step over its 0–43 m) so the page stays under its
5 MB image cap; the GeoTIFF is not quantised.

**The basis layer is never transparent**, and that is the point: it is the exact per-cell answer —
green = measured, orange = interpolated, red = undetermined — so `undetermined` reaches you as a
published value, not as a hole. A band whose job is to say "we looked and there was nothing to
measure" would erase its own admission by declaring that cell NoData; its NoData code is 255, one
the band never produces (`test_the_undetermined_code_is_a_value_not_a_hole`).

## How to reproduce

```
microrelief select   --aoi aoi/aoi.geojson --out outputs/selection.json
microrelief precheck --aoi aoi/aoi.geojson --cell 0.5 --ground-fraction 0.4
microrelief run      --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs/ \
                     --cell 0.5 --selection outputs/selection.json \
                     --attribution "Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, licensed CC BY 4.0. Derived products (ground classification, DTM, DSM, CHM) produced by microrelief; not reviewed or endorsed by DGT."
```

`--attribution` is required and has no default: a record that names a source the caller never
declared is a false provenance claim, and this package will not make one on your behalf. The
string above is DGT's, because these are DGT's tiles; on your own data, write your own.

**`--crs` is not in that command, and when you need it is a property of your AOI file, not of
the command line.** `aoi/aoi.geojson` declares its own projected CRS (`bounds` + a sibling
`bounds_epsg`), so the CRS is read from the file. An AOI that is a bare WGS84 ring declaring no
CRS of its own is refused rather than guessed at — the package will not decide which national
grid you are on — and `--crs <epsg>` on `select`, `precheck` and `run` is one of the two ways out
the refusal names. Whichever way it arrives, a CRS that is not projected with metre axes is
refused: every threshold in this package is in metres.

`select` and `precheck` reach the DGT STAC catalogue and need no account; `run` touches no network
at all. Only the LAZ download itself needs an account, and it is manual: the provider's direct
token grant is closed to this client, so acceptance was the artefact — each file's size checked
byte-for-byte against the catalogue's `file:size` — never a status code (`SITE.md` §Acquisition).

## What has been exercised

The offline core — reading classified LAS/LAZ, the ground filter, the common grid, the basis
layer, the record — carries no network dependency and no provider's conventions. **DGT is the one
provider this package has been run against**, behind the optional `dgt` extra
(the `dgt` extra — see Install); `microrelief/providers/dgt/` is where its catalogue's
conventions live, and the import edge points core ← providers only, locked by a test.

Any other provider, and any other delivery, is **untested rather than unsupported** — this
repository's own standard is that a path is unvalidated until it has been exercised end to end
against the real thing, and no second one has been. The core's site-independence is enforced
negatively instead: the tests that bind this package to Sistelo live in `tests/case_study/`, and
with `aoi/aoi.geojson` removed from the tree the rest of the suite still passes.

## The numbers, from the run of 2026-08-31 (0.4.2)

Every figure below is quoted from `docs/live-smoke.md`, which carries the commands and their
verbatim output. The machine-readable record is `docs/viewer/provenance.json` (a tracked copy of the
run's `outputs/provenance.json`). The values have not moved since the 2026-08-08 run: 0.4.0
decoupled the core from its one provider, 0.4.1 declared two limitations and closed a silent
success, and 0.4.2 closed a sibling of that success and three stale records; none changed a
measurement. That is a **measured** claim rather than an argued
one — all six bands are identical to the 0.4.0 run's cell for cell, 94,089,600 cells compared,
with only `package_version`, `created_utc`, `reproducibility_hash` and two added
`known_limitations` differing (`scripts/compare_runs.py`, output in `docs/live-smoke.md`). The
hash moved because the package version is inside it, which is the designed way a code change
reaches the artefacts.

| What | Value |
|---|---|
| Grid | 3960 × 3960 cells of 0.5 m (3.9204 km²), EPSG:3763, one common grid for everything |
| Cell basis | measured 69.7% · interpolated 28.2% · undetermined 2.1% |
| Closed-form void expectation | 0.117% of cells empty, given the measured 27.0 pts/m² and every return reaching the ground — read beside the cells with no measured basis (the 28.2% interpolated plus the 2.1% undetermined); the gap between the two is the combined effect of canopy interception and the ground filter's own rejections — a cell is measured only when the filter calls it ground (`density.py`) |
| Agreement with the official classification | ground recall 0.993 · non-ground recall 0.588 · accuracy 0.792 · **majority-class null 0.503** |
| Reproducibility hash | `09b79da9fff731caeebbb4b37b8c5508eb10ed0399940382212c48ba810518c2` |
| Cost | 34.6 s wall clock, 4.4 GiB peak resident |

ASPRS noise classes 7 and 18 (Low Point / High Noise) are excluded from every surface and counted
per tile as `point_count_noise_excluded` — 0.228% of returns over this AOI (248,809 of
109,312,003; the 150 m sample's own share is 0.104%). This delivery's class 7 spans
both extremes (84.2 m to 1752.5 m, against classified ground topping out at 506.1 m); kept, it
produced a 1524.55 m CHM and pushed the minimum surface below the terrain.

## Ground classification

The Simple Morphological Filter (Pingel et al., 2013) over the per-cell minimum surface — our own
implementation, so that every derived product is re-derived from the raw returns rather than
inheriting the delivery's classification. It is written from PDAL 2.10.2's `filters/SMRFilter.cpp`
read line by line, because that build is what it is validated against cell for cell, and the
places where the source and the paper disagree are named in `smrf.py`'s own header.

**Its parameters are pinned, not settable.** They are PDAL's defaults — `cell = 1.0 m`,
`slope = 0.15`, `scalar = 1.25`, `threshold = 0.5 m`, `window = 18 × cell = 18.0 m` — because that
is the one configuration the validation covers; any other value is a code path no reference run has
exercised, which is the same reason the module refuses `cut > 0` rather than ignoring it. The record
still declares all five, so a reader can see what ran, and `CALIBRATIONS.md` gives each one a
calibration target. One consequence is a real restriction: the publishing grid cell must divide the
1 m analysis cell, so `--cell` takes 1/k metres and refuses anything else, naming what would work.
A second is that the grid grows outward to whole 1 m blocks — up to `(1 m / --cell) - 1` cells per
axis past the AOI you asked for, which is one cell at `--cell 0.5`, four at `0.2` and nine at
`0.1`. Those cells are not free of consequence: membership is decided against the grid, not the
AOI, so one that falls inside a source tile publishes what was measured in it rather than
`undetermined`. Both products shipped here are already whole blocks, so neither moved.

**What it replaced, and what that cost.** Up to 0.4.4 this was a progressive morphological filter
(Zhang et al., 2003) whose `max_elevation_m` capped every tolerance — the parameter that decided
whether a terrace riser survived, set to 3.5 m from the tallest *verified* riser at Sistelo
(**2.98 m**: 16,596 candidates, top-12 checked one by one, everything taller being built walls, a
gully edge, or steps carried by one or two returns; `docs/riser-measurement.md`). SMRF has no such
cap, so terrace survival stopped being a guarantee and became a measurement — which is why it was
gated on one before being wired, and why the limitation list says so. That filter is still in the
tree as the comparison arm, its settings pinned in `GroundParams` at the values 0.4.4 shipped, and
`CALIBRATIONS.md` keeps its rows.

**Is the filter any good? — measured against PDAL's own, 2026-08-27.** On the shipped 150 m sample,
per cell, over cells holding at least one return, against the delivery's own ASPRS class 2. All three
run out of the box; none tuned.

| ground filter | accuracy | recall ground | recall non-ground | false positives |
|---|---|---|---|---|
| **microrelief** (own PMF variant) | 0.837 | **0.999** | 0.723 | 14,327 |
| PDAL `filters.pmf` (defaults) | 0.827 | 0.660 | **0.945** | 2,865 |
| PDAL `filters.smrf` (defaults) | **0.857** | 0.955 | 0.789 | 10,923 |

The table is a **2026-08-27 measurement**, and its first row is the filter this tool used to run.
**SMRF beat that implementation by 2.0 accuracy points**, and 2026-08-31 gave the gap a name: on a
built AOI, SMRF calls **16.4%** of the roof cells that hold no ground return at all ground, where
the old filter published **87.7%** of them as measured terrain — at a cost of 0.6 points on plain
ground and about **one in twenty** of the steepest terrace cells. (The roof figures are ones an
instrument re-derives exactly, 2026-09-02. The terrace cost is measured 2026-09-03 in
`docs/p4-terrace-result.md`: this sentence said *one in eight* until then, on a 2026-08-31 figure
whose script was never in this tree and which does not reproduce. The roof-*interior* pair it quoted
before that is not reproducible from the erosion as it was described, and
`docs/reference-instrument-result.md` says so.)

**So the tool moved to SMRF, in 0.5.0** — re-implemented here from PDAL 2.10.2's source, agreeing
with it on **99.662%** of cells at κ 0.991 over the six-tile Valongo AOI
(`docs/smrf-build-result.md` — that is a different, far larger population than this sample, and
the two accuracy figures below are not comparable to it), and accepted against
terraces before being wired (`docs/p4-terrace-result.md`). On this sample it now scores
**0.866** accuracy, ground recall 0.977, non-ground recall
0.788, 10,934 false positives — today's figures, not the table's row for
PDAL's build. The old filter stays in the tree as the comparison arm and nothing else.

The table also shows the operating point was a *choice* rather than a rounding difference: PDAL's
PMF is the same algorithm as the retired filter and scores 0.660 ground recall against its 0.999 —
that declared tolerance variant was systematically more permissive toward ground, and paid for it
in non-ground recall and false positives. Keeping the row here costs nothing and pretending
otherwise costs everything.

**The filter is deliberately not the product.** It is re-derived from the raw returns so that every
published cell has a traceable origin; the claim is the `basis` band and the record, not the surface.
That is why the filter could be swapped without the product changing shape: what this tool offers is
the cell-by-cell account of what it knows, and any classifier can sit underneath it.

*Read the denominators:* the table above is the **shipped 150 m sample**, cells with ≥ 1 return,
majority-class null 0.587. The paragraph below reports the **full AOI**, which is a different
population and a different set of numbers. Caveats on both: one site, out-of-the-box parameters, and
the "truth" is DGT's own classification — a product, not ground truth.

The comparison against the official ASPRS classification exists to **quantify the difference, not
to beat the DGT** — the official ground class never decides a cell in these surfaces; here it is
the reference being quantified against, **not an input** to the filter. Two other official labels
*are* inputs upstream of it: classes 7 and 18 are removed before the minimum surface the filter
reads is formed, and a tile carrying no class 2 at all is read normally but recorded as carrying
no official ground, which makes `agreement` absent for the whole product (`read.py`,
`cli.py`). Ground recall 0.993,
non-ground recall 0.588, accuracy 0.792, majority-class null 0.503; the number to read beside
those is `fp = 3,174,486` — 0.2045 of compared cells are cells where this filter says ground and
the official classification has no ground return, which is the expected shape of a minimum-surface
filter under canopy, declared rather than tuned away.

## What this does not support

- **The ground filter does not remove every building, and the record calls what it keeps
  measured.** At a built site near Valongo, **16.4%** of the cells holding official building
  returns and no ground return publish as `basis = measured`. The filter this tool ran until
  0.5.0 published **87.7%** of that same population (both re-derived by instrument, 2026-09-02,
  `docs/reference-instrument-result.md`). Where it happens, the DTM says the roof and the ground
  are the same thing, and says it with the strongest word the band has. It was **not fixable by a
  parameter** of the old filter — the best single height threshold separates a roof from the
  terrain it stands on at **0.712** balanced accuracy and the best width threshold at **0.528**,
  and a one-storey roof is the same height as the 2.98 m terrace riser its tolerance cap existed
  to preserve — which is why the repair was to change the filter rather than to tune it
  (`docs/ground-filter-diagnosis.md`). Found by running the pipeline on a second AOI chosen for
  what it *contains* rather than for what it shows (`docs/second-aoi-gate-result.md`) — 272 tests,
  a ten-round review and a security pass had all gone over it, because every one of them asks
  about the code and none asks what the input holds.
- **Terrace preservation is measured, not enforced.** The old filter had a parameter that capped
  how far it could cut, set from the tallest verified riser at the calibration site; SMRF has no
  such cap. That risers survive it is an empirical result at **one** site: it keeps **91.078%** of
  the cells the old filter called measured ground, and **95.082%** of those standing on a step
  above 2.5 m, against bounds pre-registered before the run (`docs/p4-terrace-result.md`). At a
  second site with different terraces, that is unmeasured.
- **Byte-identical replay on real data is not established — now with a measured bound.** A run on
  2026-08-05 saw, in four reads of the 845 MB dataset, one single corrupted coordinate
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
- **The reproducibility hash does not cover `--attribution` either.** Measured: two runs differing
  only in that string share the hash `2da06987808e…`, so a product can be relabelled with a
  different source and keep its anchor. Defensible — the hash covers inputs and parameters, not
  what you wrote about them — but it is a thing to know before you treat the hash as a licence
  check.
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
- **The AOI-vs-tile CRS check lives at the CLI's composition root, so calling `select_tiles` as a
  library function goes around it.** No caller does today; the gap becomes reachable exactly when
  someone uses this as a library, which is what 0.4.0 makes possible. Declared here and in the
  record rather than fixed by duplicating the check into the provider.
- **`scripts/measure_risers.py` takes no `--crs`**, so it can only work an AOI that declares its
  own projected CRS. It is a measurement script, not part of the package's interface.
- **The only resource ceiling is a cell count, not a memory bound.** `grid_for_bounds` refuses
  above 200,000,000 cells; measured, the per-cell arrays alone cost 60 B/cell (40 B in the
  accumulator, 20 B in `CellStats`), so that ceiling is ~12 GB before the ground filter, the two
  distance transforms and the surfaces. `--cell 0.1` over 1 km² is 100M cells, passes the guard,
  and can still be OOM-killed — a failure without a reason, which is the opposite of everything
  else here. The refusal now states the byte cost; it does not bound it.

## Attribution

Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, licensed
**CC BY 4.0**. Derived products (ground classification, DTM, DSM, CHM) produced by `microrelief`;
**not reviewed or endorsed by DGT**. The attribution travels inside every exported GeoTIFF's tags
and in `docs/viewer/provenance.json`, so it reaches whoever holds the file, not only whoever found this
page.

# What `run` accepts, and what it refuses

`run` reads every `.laz` directly inside `--laz`. Not `.las`, and not subdirectories. Each
paragraph below is a refusal with its reason when unmet, because a pipeline that guesses at an
input is a pipeline whose provenance record is a guess.

**File format.** Anything laspy opens as LAS or LAZ. Exercised so far: LAS 1.4, point format 8,
which is the DGT delivery. Other versions and point formats are untested rather than unsupported,
and the difference matters: nothing here has been run against them, so nothing here claims they
work.

**Coordinate reference system.** The header declares a CRS that resolves to an EPSG code, it is
projected with metre axes, and it is the area's. Nothing is reprojected here. `docs/recipes.md`
shows PDAL or LAStools doing it first. Every threshold in this package is in metres, so a
geographic CRS is refused rather than silently treated as one.

**Finite coordinates.** A header scale or offset that decodes to NaN or infinity refuses the file.
Without this, a cell can publish a point count of 1 beside a minimum elevation of NaN, and the
missing value stops meaning "nothing was measured here".

**Classification.** The classification dimension is read. Class 2 is optional: present, the record
reports agreement against it; absent, `agreement` is null and the tile is named, because a missing
official comparison is a fact about the file rather than a failure of the surface. The noise
classes, 7 and 18, are excluded from every surface and counted per tile.

**Area of interest.** A GeoJSON Polygon. The CLI reads `properties.bounds` together with
`properties.bounds_epsg`. A bare WGS84 ring needs `--crs <epsg>` on `select`, `precheck` and `run`;
one declaring no CRS of its own is refused rather than guessed at, since this package will not
decide which national grid you are on.

**Publishing cell.** `--cell` takes 1 over a whole number of metres, because the publishing grid
has to divide the ground filter's 1 m analysis cell. Anything else is refused, naming what would
work.

**Attribution.** `--attribution` is required and has no default. A record naming a source the
caller never declared would be a false provenance claim, and this package will not make one on your
behalf.

## One provider, exercised

DGT is the one provider this package has been run against. Its catalogue conventions live behind
the optional `dgt` extra in `microrelief/providers/dgt/`, and a test locks the import edge so that
core never reaches for a provider.

Any other provider, and any other delivery, is untested rather than unsupported. The standard here
is that a path is unvalidated until it has been exercised end to end against the real thing, and no
second one has been. Site independence is enforced negatively instead: the tests that bind this
package to Sistelo live in `tests/case_study/`, and with `aoi/aoi.geojson` removed from the tree
the rest of the suite still passes.

Without `--selection`, the catalogue step, the record says it does not know what the provider
claimed rather than repeating back what it measured.

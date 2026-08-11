# Attribution

Source data: **Direção-Geral do Território (DGT)**, Centro de Dados, collection `LAZ`
(airborne LiDAR point clouds, 1 km × 1 km tiles, EPSG:3763 / ETRS89 PT-TM06).
Licensed **CC BY 4.0**. The DGT produced the source measurements; it did not produce, review or
endorse the derived products in this repository.

Derived here, by this code: the ground classification, DTM, DSM, CHM, the basis codes, and the
per-cell counts — except `n_ground_asprs`, which counts the provider's class-2 labels per cell:
the labels are DGT's, only the counting is ours. The official ASPRS classification is used exactly
as the README enumerates: it names the noise classes excluded from every surface (7 and 18),
travels per cell as the published `n_ground_asprs` band, and anchors the agreement comparison.
A delivery that carries **no** class 2 is not refused — the record publishes `agreement: null` and
names the tile, because a missing official comparison is a fact about the file, not a failure of
the surface. What the classification never does is decide which cells are ground in these
surfaces — that decision is re-derived from the raw returns by this repository's own filter.

## Who supplies this string (0.4.0)

**The attribution is the caller's to declare.** `--attribution` is a required argument with no
default, and the core has no knowledge of any provider: a record naming a source the caller never
declared would be a false provenance claim published inside the file, which is the one thing this
repository exists not to do. Before 0.4.0 the DGT string was a constant in the core, so *any*
run — over anyone's data — published DGT as its source and CC BY 4.0 as its licence.

The DGT string above now lives with the provider that needs it, in
`src/microrelief/providers/dgt/` as `DGT_ATTRIBUTION`, behind the optional `dgt` extra. It is the
string the published run passes, verbatim.

**A run on other data must declare its own source and licence.** There is no fallback and no
inherited default; the run refuses to start without one.

Each exported GeoTIFF repeats whatever attribution the run was given in its metadata tags, so it
survives being detached from this repository.

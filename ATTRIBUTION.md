# Attribution

Source data: **Direção-Geral do Território (DGT)**, Centro de Dados, collection `LAZ`
(airborne LiDAR point clouds, 1 km × 1 km tiles, EPSG:3763 / ETRS89 PT-TM06).
Licensed **CC BY 4.0**. The DGT produced the source measurements; it did not produce, review or
endorse the derived products in this repository.

Derived here, by this code: the ground classification, DTM, DSM, CHM, the basis codes, and the
per-cell counts — except `n_ground_asprs`, which counts the provider's class-2 labels per cell:
the labels are DGT's, only the counting is ours. The official ASPRS classification is used exactly as the README
enumerates: it gates acceptance (a tile with no official ground class is refused), names the
noise classes excluded from every surface (7 and 18), travels per cell as the published
`n_ground_asprs` band, and anchors the agreement comparison. What it never does is decide which
cells are ground in these surfaces — that decision is re-derived from the raw returns by this
repository's own filter.

Each exported GeoTIFF repeats this attribution in its metadata tags, so it survives being detached
from this repository.

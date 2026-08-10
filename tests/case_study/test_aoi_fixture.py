"""The AOI is a fixture the rest of the piece depends on, so its shape is locked here.

Crossing tile boundaries is a requirement, not an accident of where the box landed: the
seam is where a per-tile pipeline would show its joins, and this piece has to have one.
"""

import json
from pathlib import Path

from pyproj import Transformer

AOI_PATH = Path(__file__).resolve().parents[2] / "aoi" / "aoi.geojson"


def _ring() -> list[list[float]]:
    doc = json.loads(AOI_PATH.read_text(encoding="utf-8"))
    geom = doc["geometry"] if doc["type"] == "Feature" else doc
    assert geom["type"] == "Polygon"
    assert len(geom["coordinates"]) == 1, "one exterior ring, no holes"
    return geom["coordinates"][0]


def _ring_in_metres() -> tuple[list[float], list[float]]:
    tf = Transformer.from_crs(4326, 3763, always_xy=True)
    xs, ys = zip(*(tf.transform(lon, lat) for lon, lat in _ring()), strict=True)
    return list(xs), list(ys)


def test_aoi_is_a_single_closed_polygon_in_wgs84() -> None:
    ring = _ring()
    assert ring[0] == ring[-1], "GeoJSON rings close on themselves"
    assert len(ring) == 5, "four corners plus the repeated first"
    assert all(-9.6 < lon < -6.1 and 36.9 < lat < 42.2 for lon, lat in ring), ring


def test_aoi_is_about_four_square_km() -> None:
    xs, ys = _ring_in_metres()
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    assert 1500 < width < 2500, width
    assert 1500 < height < 2500, height


def test_aoi_crosses_a_tile_boundary_on_both_axes() -> None:
    # Honest note: given a 1 km lattice this is *entailed* by the size test above — a 2 km
    # box cannot avoid a seam. It cannot fail while the AOI is the right size, so what it
    # actually guards is the lattice premise, measured against the catalogue on
    # 2026-08-04: every returned footprint spans exactly (1000, 1000) m.
    xs, ys = _ring_in_metres()
    assert int(max(xs) // 1000) > int(min(xs) // 1000), (min(xs), max(xs))
    assert int(max(ys) // 1000) > int(min(ys) // 1000), (min(ys), max(ys))


def test_aoi_sits_strictly_inside_its_tile_block_by_more_than_the_seam() -> None:
    # This one can fail, and would if the AOI were pushed out to the block edge. DGT's
    # declared footprints stop ~1 mm short of the lattice, so an AOI flush with the block
    # is short of full coverage on all four sides for no gain.
    doc = json.loads(AOI_PATH.read_text(encoding="utf-8"))
    assert doc["properties"]["bounds_epsg"] == 3763
    x0, y0, x1, y1 = doc["properties"]["bounds"]
    block = (
        (x0 // 1000) * 1000,
        (y0 // 1000) * 1000,
        -((-x1) // 1000) * 1000,
        -((-y1) // 1000) * 1000,
    )
    margins = (x0 - block[0], y0 - block[1], block[2] - x1, block[3] - y1)
    assert all(m > 0.001 for m in margins), (margins, block)


def test_aoi_declares_the_tiles_and_the_single_sortie_it_was_chosen_for() -> None:
    doc = json.loads(AOI_PATH.read_text(encoding="utf-8"))
    props = doc["properties"]
    assert len(props["tiles"]) == 4, props["tiles"]
    assert props["flight_date"] == "2026-03-30T00:00:00Z"
    assert "CC BY 4.0" in props["licence"]

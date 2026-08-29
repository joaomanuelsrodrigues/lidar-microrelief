"""The CLI tests that are about *this* delivery's AOI rather than about the CLI.

Cut out of `tests/test_cli.py`, which keeps everything that runs on a `tmp_path` fixture.
"""

from __future__ import annotations

from pathlib import Path

from microrelief.cli import aoi_bounds
from microrelief.grid import grid_for_bounds

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_declared_bounds_win_over_the_wgs84_ring() -> None:
    """A declared bound beats one inferred from the geometry, and it is not a
    hypothetical: measured on the committed AOI.

    The ring in `aoi/aoi.geojson` is the WGS84 *image* of the working box and, transformed back,
    misses it by up to 3.8 mm — the file says so itself. `grid_for_bounds` floors the origin and
    ceils the extent, so those millimetres move the origin half a cell and grow the grid from
    3960x3960 to 3961x3962: 11,882 extra cells, every one of them outside all four tiles and so
    published as `undetermined`, and a different `reproducibility_hash`, because the grid is in it.

    So the declared `bounds` + `bounds_epsg` are not a convenience — they are the only source that
    gives the grid the AOI was chosen with.
    """
    minx, miny, maxx, maxy, epsg = aoi_bounds(REPO_ROOT / "aoi" / "aoi.geojson")
    assert (minx, miny, maxx, maxy) == (-20990.0, 255010.0, -19010.0, 256990.0)
    assert epsg == 3763
    assert grid_for_bounds(minx, miny, maxx, maxy, 0.5, epsg).shape == (3960, 3960)

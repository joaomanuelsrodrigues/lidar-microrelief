"""The command line, and the contract between what it is told and what it publishes.

Three of these tests exist because the plan's version of `cli.py` was written before the modules
it calls were finished, and drifted from them in ways only running it exposes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import rasterio

from microrelief.cli import aoi_bounds, main
from microrelief.grid import grid_for_bounds
from tests.synthetic import ORIGIN_X, ORIGIN_Y, ramp, write_las

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every cloud in this file is synthetic, so it is nobody's data. Naming a real provider here
# would be the same false source-and-licence claim `--attribution` exists to prevent, and it
# would stop these tests telling a string the CLI passed through from one the core supplied
# on its own. The Sistelo string lives in the provenance factory, where real data is described.
ATTRIBUTION = "Source: synthetic test fixture, no provider, no licence."


def _synthetic_run(
    tmp_path: Path, extra: list[str] | None = None, unclassified_tile: bool = False
) -> tuple[int, Path]:
    """One synthetic tile, an AOI given directly in the tiles' CRS, and a run over both.

    `unclassified_tile` adds a second tile carrying no ASPRS class 2, for the mosaic rule.
    """
    laz = tmp_path / "laz"
    laz.mkdir()
    write_las(laz / "SYNTH-1.laz", cloud=ramp(size_m=50.0, spacing=0.5), epsg=3763)
    if unclassified_tile:
        write_las(laz / "SYNTH-2.laz", n=500, epsg=3763, classification=5)  # vegetation only
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "crs_epsg": 3763,
                "coordinates": [
                    [
                        [ORIGIN_X, ORIGIN_Y],
                        [ORIGIN_X + 40, ORIGIN_Y],
                        [ORIGIN_X + 40, ORIGIN_Y + 40],
                        [ORIGIN_X, ORIGIN_Y + 40],
                        [ORIGIN_X, ORIGIN_Y],
                    ]
                ],
            }
        )
    )
    out = tmp_path / "out"
    argv = [
        "run",
        "--aoi",
        str(aoi),
        "--laz",
        str(laz),
        "--out",
        str(out),
        "--cell",
        "0.5",
        "--attribution",
        ATTRIBUTION,
    ]
    return main(argv + (extra or [])), out


def test_run_refuses_when_the_laz_directory_is_empty(tmp_path: Path, capsys: Any) -> None:
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-7.55, 41.18],
                        [-7.54, 41.18],
                        [-7.54, 41.19],
                        [-7.55, 41.19],
                        [-7.55, 41.18],
                    ]
                ],
            }
        )
    )
    code = main(
        [
            "run",
            "--aoi",
            str(aoi),
            "--laz",
            str(tmp_path),
            "--out",
            str(tmp_path / "o"),
            "--attribution",
            ATTRIBUTION,
        ]
    )
    assert code != 0
    assert "no .laz files" in capsys.readouterr().err


def test_run_refuses_an_aoi_that_is_not_a_polygon(tmp_path: Path, capsys: Any) -> None:
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(json.dumps({"type": "Point", "coordinates": [-7.55, 41.18]}))
    code = main(
        [
            "run",
            "--aoi",
            str(aoi),
            "--laz",
            str(tmp_path),
            "--out",
            str(tmp_path / "o"),
            "--attribution",
            ATTRIBUTION,
        ]
    )
    assert code != 0
    assert "Polygon" in capsys.readouterr().err


def test_agreement_is_published_when_every_tile_carries_the_official_class(
    tmp_path: Path,
) -> None:
    """Positive control for the test below. Without it, an `agreement is None` assertion would
    pass just as well if agreement had been broken for every run rather than only this case."""
    code, out = _synthetic_run(tmp_path)
    assert code == 0
    assert json.loads((out / "provenance.json").read_text())["agreement"] is not None


def test_one_unclassified_tile_makes_agreement_absent_for_the_whole_product(
    tmp_path: Path, capsys: Any
) -> None:
    """All-or-nothing on purpose. Agreement over a mosaic where only some tiles carry class 2
    mixes 'measured non-ground' with 'never classified' into one number — a statistic over a
    denominator it was not taken from (§A1/s258). The tile is named, not just counted."""
    code, out = _synthetic_run(tmp_path, unclassified_tile=True)
    assert code == 0
    assert json.loads((out / "provenance.json").read_text())["agreement"] is None
    assert "SYNTH-2" in capsys.readouterr().err


def test_run_over_a_synthetic_tile_produces_every_output(tmp_path: Path) -> None:
    code, out = _synthetic_run(tmp_path)
    assert code == 0
    for name in ("mdt", "mds", "chm", "basis", "n_all", "n_ground_asprs"):
        assert (out / f"{name}.tif").exists()
    doc = json.loads((out / "provenance.json").read_text())
    assert doc["honesty"]["fraction_measured"] > 0.9


def test_the_declared_bounds_win_over_the_wgs84_ring() -> None:
    """§A6, and it is not a hypothetical: measured on the committed AOI.

    The ring in `aoi/aoi.geojson` is the WGS84 *image* of the working box and, transformed back,
    misses it by up to 3.8 mm — the file says so itself. `grid_for_bounds` floors the origin and
    ceils the extent, so those millimetres move the origin half a cell and grow the grid from
    3960x3960 to 3961x3962: 11,882 extra cells, every one of them outside all four tiles and so
    published as `undetermined`, and a different `reproducibility_hash`, because the grid is in it.

    So the declared `bounds_epsg3763` is not a convenience — it is the only source that gives the
    grid the AOI was chosen with.
    """
    minx, miny, maxx, maxy, epsg = aoi_bounds(REPO_ROOT / "aoi" / "aoi.geojson")
    assert (minx, miny, maxx, maxy) == (-20990.0, 255010.0, -19010.0, 256990.0)
    assert epsg == 3763
    assert grid_for_bounds(minx, miny, maxx, maxy, 0.5, epsg).shape == (3960, 3960)


def test_a_ring_only_aoi_still_works_and_is_reprojected(tmp_path: Path) -> None:
    """The sibling of the test above: preferring the declared bounds must not delete the path for
    an AOI that has none, which is what a reader drawing their own polygon will hand over."""
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-8.3864, 41.9643],
                        [-8.3624, 41.9643],
                        [-8.3624, 41.9822],
                        [-8.3864, 41.9822],
                        [-8.3864, 41.9643],
                    ]
                ],
            }
        )
    )
    minx, miny, maxx, maxy, epsg = aoi_bounds(aoi)
    assert epsg == 3763
    assert -21100 < minx < -20900 and 254900 < miny < 255100


def test_declared_bounds_that_are_not_a_box_of_four_numbers_are_refused(tmp_path: Path) -> None:
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"bounds_epsg3763": [-20990.0, 255010.0, -19010.0]},
                "geometry": {"type": "Polygon", "coordinates": [[[-8.38, 41.96]]]},
            }
        )
    )
    with pytest.raises(SystemExit, match="four numbers"):
        aoi_bounds(aoi)


def test_without_a_selection_the_record_says_it_does_not_know_the_catalogue(
    tmp_path: Path,
) -> None:
    """A run with no catalogue beside it publishes `null`, not the measured count copied into the
    catalogue's field. Copying it would make the two numbers agree by construction, and the pair
    exists precisely so a reader can see whether the file we read is the file the provider
    described. A field that cannot disagree is not evidence."""
    _code, out = _synthetic_run(tmp_path)
    doc = json.loads((out / "provenance.json").read_text())
    (one,) = doc["inputs"]
    assert one["point_count_catalogue"] is None
    assert one["point_count_measured"] > 0
    assert doc["flight_dates"] == []


def test_a_selection_supplies_the_catalogue_facts_and_lets_them_disagree(tmp_path: Path) -> None:
    """With `--selection`, the counts and the stamps come from the catalogue, and a provider that
    declared a different count than it delivered is visible in the record rather than smoothed
    over. The declared count here is deliberately wrong."""
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "item_id": "SYNTH-1",
                        "point_count": 999_999,
                        "flight_date": "2025-03-30T11:02:14+00:00",
                    }
                ]
            }
        )
    )
    code, out = _synthetic_run(tmp_path, ["--selection", str(selection)])
    assert code == 0
    doc = json.loads((out / "provenance.json").read_text())
    (one,) = doc["inputs"]
    assert one["point_count_catalogue"] == 999_999
    assert one["point_count_measured"] != 999_999
    assert doc["flight_dates"] == ["2025-03-30T11:02:14+00:00"]


def test_a_laz_file_missing_from_the_selection_is_refused(tmp_path: Path, capsys: Any) -> None:
    """Otherwise `--selection` degrades into decoration: the run would quote catalogue facts for
    the tiles it recognised and invent nothing for the rest, while the record shows one list."""
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"tiles": [{"item_id": "SOMETHING-ELSE", "point_count": 1}]}))
    code, _out = _synthetic_run(tmp_path, ["--selection", str(selection)])
    assert code != 0
    assert "SYNTH-1" in capsys.readouterr().err


def test_the_density_denominator_is_the_grid_not_the_requested_aoi(tmp_path: Path) -> None:
    """`grid_for_bounds` snaps outward to whole cells, so an AOI that is not a multiple of the
    cell yields a grid larger than what was asked for. The honesty report counts cells of that
    grid; dividing by the requested area instead would put a count over the wrong denominator —
    the §A1/s258 lesson, one module along."""
    laz = tmp_path / "laz"
    laz.mkdir()
    write_las(laz / "SYNTH-1.laz", cloud=ramp(size_m=50.0, spacing=0.5), epsg=3763)
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "crs_epsg": 3763,
                "coordinates": [
                    [
                        [ORIGIN_X, ORIGIN_Y],
                        [ORIGIN_X + 40.3, ORIGIN_Y],
                        [ORIGIN_X + 40.3, ORIGIN_Y + 40.3],
                        [ORIGIN_X, ORIGIN_Y + 40.3],
                        [ORIGIN_X, ORIGIN_Y],
                    ]
                ],
            }
        )
    )
    out = tmp_path / "out"
    assert (
        main(
            [
                "run",
                "--aoi",
                str(aoi),
                "--laz",
                str(laz),
                "--out",
                str(out),
                "--cell",
                "0.5",
                "--attribution",
                ATTRIBUTION,
            ]
        )
        == 0
    )
    doc = json.loads((out / "provenance.json").read_text())
    n_cells = doc["grid"]["n_rows"] * doc["grid"]["n_cols"]
    grid_area = n_cells * doc["grid"]["cell"] ** 2
    requested_area = 40.3 * 40.3
    assert grid_area != pytest.approx(requested_area)  # the snap really did change the area

    with rasterio.open(out / "n_all.tif") as src:
        counts = src.read(1)
    in_grid = float(counts[counts > 0].sum())

    assert doc["honesty"]["measured_density_pts_m2"] == pytest.approx(in_grid / grid_area)
    # Control positive: the two denominators must actually give different answers, or this test
    # would pass against either implementation and discriminate nothing.
    assert doc["honesty"]["measured_density_pts_m2"] != pytest.approx(in_grid / requested_area)

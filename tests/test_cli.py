"""The command line, and the contract between what it is told and what it publishes.

Three of these tests exist because an early version of `cli.py` was written before the modules
it calls were finished, and drifted from them in ways only running it exposes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import rasterio

from microrelief.cli import aoi_bounds, main
from microrelief.crs import CRSError
from tests.synthetic import ORIGIN_X, ORIGIN_Y, ramp, write_las

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
            # This AOI is a bare WGS84 ring, so it names no working CRS and
            # `_cmd_run` refuses on its first line — before it ever looks for `.laz` files. The
            # CRS is passed rather than written into the fixture as a `crs_epsg` property: these
            # coordinates are genuinely lon/lat, and declaring them as 3763 would make the
            # fixture a lie to silence a failure.
            "--crs",
            "3763",
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
    denominator it was not taken from (2026-08-04). The tile is named, not just counted."""
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


RING = [
    [-8.3864, 41.9643],
    [-8.3624, 41.9643],
    [-8.3624, 41.9822],
    [-8.3864, 41.9822],
    [-8.3864, 41.9643],
]
"""Copied verbatim from the ring-only test this task supersedes, and so are the bounds asserted
against it below. Those numbers are known to hold for this ring because that test has been
passing on them; inventing a nearby ring and keeping the inherited bounds would be asserting
numbers nobody measured, and a fixture whose expected values are guessed cannot tell you whether
a failure is the code or the fixture (2026-08-03)."""


def test_the_aoi_declares_its_own_crs_rather_than_the_cli_assuming_one(tmp_path: Path) -> None:
    """A different metric CRS must work. The pin was a Portugal fact in a general code path."""
    aoi = tmp_path / "utm.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {
                    "bounds": [500000.0, 4600000.0, 502000.0, 4602000.0],
                    "bounds_epsg": 32629,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
                },
            }
        )
    )
    minx, miny, maxx, maxy, epsg = aoi_bounds(aoi)
    assert (minx, miny, maxx, maxy) == (500000.0, 4600000.0, 502000.0, 4602000.0)
    assert epsg == 32629


def test_an_aoi_declaring_a_geographic_crs_for_its_metric_bounds_is_refused(
    tmp_path: Path,
) -> None:
    """`aoi_bounds`'s own responsibility (R2-M1, R2-M2). It resolves 4326 as the working CRS,
    so it must refuse it here — not return it and leave the refusal to whatever the caller
    happens to build next. `select` and `precheck` build no Grid at all."""
    aoi = tmp_path / "degrees.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"bounds": [-8.5, 41.9, -8.4, 42.0], "bounds_epsg": 4326},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
                },
            }
        )
    )
    with pytest.raises(CRSError, match="degree"):
        aoi_bounds(aoi)


def test_a_ring_declaring_etrs89_geographic_is_not_mistaken_for_a_projected_one(
    tmp_path: Path,
) -> None:
    """R2-M1. EPSG:4258 is ETRS89 *geographic* — degrees, and the likeliest wrong tag on
    Portuguese data. A draft of this task tested `ring_epsg != 4326` and would have taken these
    degrees as metres: plausible output, silently wrong, which is the class this task exists
    to close. It must refuse, and the refusal must still say how to get through."""
    aoi = tmp_path / "etrs89.geojson"
    aoi.write_text(json.dumps({"type": "Polygon", "crs_epsg": 4258, "coordinates": [RING]}))
    with pytest.raises(SystemExit, match="--crs") as caught:
        aoi_bounds(aoi)
    # The guard's own words are carried through the chain, not swallowed and re-worded.
    assert "4258" in str(caught.value) and "degree" in str(caught.value)


def test_a_crs_named_by_the_caller_is_refused_as_itself_when_it_is_not_metric(
    tmp_path: Path,
) -> None:
    """R2-M1. Naming a bad CRS is a different mistake from naming none, and gets a different
    exception. A caller who just typed `--crs 4326` does not need to be told how to supply a
    CRS; they need to be told why theirs will not do. Positive control on the pair: the same
    file with `crs=3763` succeeds, in the test below."""
    aoi = tmp_path / "ring.geojson"
    aoi.write_text(json.dumps({"type": "Polygon", "coordinates": [RING]}))
    with pytest.raises(CRSError, match="degree"):
        aoi_bounds(aoi, crs=4326)


def test_a_ring_only_wgs84_aoi_refuses_rather_than_assuming_a_national_grid(
    tmp_path: Path,
) -> None:
    """Case 5. The package will not guess which country you are in. The refusal has to name both
    ways out, or it trades a wrong answer for a dead end."""
    aoi = tmp_path / "ring.geojson"
    aoi.write_text(json.dumps({"type": "Polygon", "coordinates": [RING]}))
    with pytest.raises(SystemExit, match="--crs"):
        aoi_bounds(aoi)


def test_a_ring_only_aoi_is_projected_into_the_crs_it_was_given(tmp_path: Path) -> None:
    """Case 4, and the positive control for the refusal above: the same file that is refused
    without a CRS must succeed with one, or the refusal is untestable as a discriminator
    (2026-08-03).

    This is the capability operator ruling D-1 preserves. Preferring the declared bounds must not
    delete the path for an AOI that has none, which is what a reader drawing their own polygon
    hands over — what goes is only the guess about *which* CRS to project into.
    """
    aoi = tmp_path / "ring.geojson"
    aoi.write_text(json.dumps({"type": "Polygon", "coordinates": [RING]}))
    minx, miny, _maxx, _maxy, epsg = aoi_bounds(aoi, crs=3763)
    assert epsg == 3763
    assert -21100 < minx < -20900 and 254900 < miny < 255100


def _provider_serving(tiles: list[Any]) -> Any:
    """A stand-in for the DGT module: crafted search results, the REAL select_tiles.

    Stubbing only the network call is deliberate. If `select_tiles` were stubbed too, the
    positive control would prove the guard let something through without proving a selection
    can still be made — and it is the second half that says the guard is not simply blocking
    everything."""
    from microrelief.providers import dgt

    class _Provider:
        select_tiles = staticmethod(dgt.select_tiles)

        @staticmethod
        def search_tiles(_bbox: Any) -> list[Any]:
            return tiles

    return _Provider


def _pt_tm06_tiles() -> list[Any]:
    """A 3x3 km block of EPSG:3763 tiles — positive-x here, as `tests/test_selection.py`
    builds them; what matters is only that no coordinate can coincide with UTM 29N's."""
    from microrelief.providers.dgt import TileRef

    return [
        TileRef(
            item_id=f"LO-{int(x)}-{int(y)}",
            collection="LAZ",
            minx=x,
            miny=y,
            maxx=x + 1000.0,
            maxy=y + 1000.0,
            crs_epsg=3763,
            point_count=19_000_000,
            flight_date="2024-11-22T00:00:00Z",
            file_size=130_000_000,
            href="https://example.invalid/t",
        )
        for x in (48000.0, 49000.0, 50000.0)
        for y in (169000.0, 170000.0, 171000.0)
    ]


def _aoi_file(tmp_path: Path, name: str, bounds: list[float], epsg: int) -> Path:
    aoi = tmp_path / name
    aoi.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"bounds": bounds, "bounds_epsg": epsg},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
                },
            }
        )
    )
    return aoi


def test_an_aoi_and_tiles_in_different_crss_are_refused_before_the_overlap_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """D-3(b). A genuine UTM 29N box against PT-TM06 tiles: the ranges are disjoint in BOTH
    axes, so every `_overlap_area` is zero and `select_tiles` would die on 'no tile intersects'
    — sending the reader to hunt a coverage problem they do not have. The refusal has to name
    the real cause, and it has to happen at the composition root, before the arithmetic."""
    import microrelief.cli as cli

    monkeypatch.setattr(cli, "_dgt", lambda: _provider_serving(_pt_tm06_tiles()))
    aoi = _aoi_file(tmp_path, "utm.geojson", [500000.0, 4600000.0, 502000.0, 4602000.0], 32629)

    assert cli.main(["select", "--aoi", str(aoi), "--out", str(tmp_path / "sel.json")]) == 2
    err = capsys.readouterr().err
    assert "32629" in err and "3763" in err
    assert "no tile intersects" not in err  # the old, misleading message must NOT be what speaks


def test_a_matching_crs_still_selects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the guard. Same tiles, same code path, AOI in the tiles' own CRS:
    the selection must complete and write its record. Without this, the refusal above is
    indistinguishable from a guard that blocks everything, and from a selection that came back
    empty for some unrelated reason (2026-08-03)."""
    import microrelief.cli as cli

    monkeypatch.setattr(cli, "_dgt", lambda: _provider_serving(_pt_tm06_tiles()))
    aoi = _aoi_file(tmp_path, "ptm.geojson", [48200.0, 169200.0, 50200.0, 171200.0], 3763)
    out = tmp_path / "sel.json"

    assert cli.main(["select", "--aoi", str(aoi), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["covered_fraction"] == pytest.approx(1.0)


def test_the_crs_guard_is_not_disabled_by_a_neighbour_in_another_crs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard read `if len(tile_crs) == 1 and only != epsg`, so one tile in a second CRS
    anywhere in the search box switched the whole check off -- and `select_tiles` compares CRSs
    only among the tiles that *touch* the AOI. Measured against the live catalogue on
    2026-08-31: an AOI over six tiles read as EPSG:9001 was accepted, coverage 1.0000, because
    a single neighbouring tile read as 3763 made the set size two.

    `_overlap_area` compares every searched tile's box against the AOI bounds, so the condition
    that has to hold is that every one of them is in the AOI's CRS -- not that they agree
    among themselves.
    """
    import microrelief.cli as cli
    from microrelief.providers.dgt import TileRef

    stranger = TileRef(
        item_id="LO-stranger",
        collection="LAZ",
        minx=500000.0,
        miny=4600000.0,
        maxx=501000.0,
        maxy=4601000.0,
        crs_epsg=32629,
        point_count=1,
        flight_date="2024-11-22T00:00:00Z",
        file_size=1,
        href="https://example.invalid/t",
    )
    monkeypatch.setattr(cli, "_dgt", lambda: _provider_serving([*_pt_tm06_tiles(), stranger]))
    aoi = _aoi_file(tmp_path, "ptm.geojson", [48200.0, 169200.0, 50200.0, 171200.0], 3763)

    assert cli.main(["select", "--aoi", str(aoi), "--out", str(tmp_path / "sel.json")]) == 2
    err = capsys.readouterr().err
    assert "32629" in err and "3763" in err


def test_declared_bounds_that_are_not_a_box_of_four_numbers_are_refused(tmp_path: Path) -> None:
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"bounds": [500000.0, 4600000.0, 502000.0], "bounds_epsg": 32629},
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
    the 2026-08-04 lesson, one module along."""
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


_FIGURE = re.compile(r"\d+\.\d+%?")
_CITATION = re.compile(r"docs/[A-Za-z0-9._/-]+\.md")


def _figures(line: str) -> list[str]:
    return _FIGURE.findall(line)


def _assert_every_figure_has_evidence(line: str) -> None:
    """Every figure a limitation publishes must appear in a document that same line cites.

    The documents come from the line, not from a list kept here: a limitation may be measured in
    one record and re-measured in another, and the check has to follow the citation rather than
    force the prose back to whichever file the test was written against.
    """
    root = Path(__file__).resolve().parents[1]
    cited = _CITATION.findall(line)
    assert cited, f"a limitation quoting figures must cite where they were measured: {line!r}"

    corpus = ""
    for name in cited:
        path = root / name
        assert path.exists(), f"the limitation cites {name}, which is not in the tree"
        corpus += path.read_text(encoding="utf-8")

    missing = [f for f in _figures(line) if f not in corpus]
    assert not missing, (
        f"the record publishes {missing} which {cited} do not contain: a declared limitation "
        "may not carry a number its own evidence cannot show"
    )


def test_every_limitation_that_quotes_a_figure_can_show_where_it_was_measured() -> None:
    """The partition, over the whole list rather than over the one line a test remembered.

    Each limitation either quotes no figure, or cites documents that carry every figure it
    quotes. Nothing is exempt: an exemption here would be a number in every published record
    with nothing behind it.
    """
    from microrelief.cli import LIMITATIONS

    quoting = [line for line in LIMITATIONS if _figures(line)]
    assert quoting, "this check scanned nothing: no limitation quotes a figure"
    for line in quoting:
        _assert_every_figure_has_evidence(line)


def test_the_evidence_check_fires_on_a_figure_no_cited_document_contains() -> None:
    """Both arms. Without this, a check that cannot fail reads exactly like a clean list."""
    real = (
        "16.4% publish as measured ground at a built site near Valongo "
        "(docs/reference-instrument-result.md)."
    )
    _assert_every_figure_has_evidence(real)  # the quiet arm

    with pytest.raises(AssertionError, match="99.9%"):
        _assert_every_figure_has_evidence(
            "99.9% of cells are ground (docs/reference-instrument-result.md)."
        )
    with pytest.raises(AssertionError, match="not in the tree"):
        _assert_every_figure_has_evidence("16.4% of cells (docs/no-such-record.md).")
    with pytest.raises(AssertionError, match="must cite"):
        _assert_every_figure_has_evidence("16.4% of cells, measured somewhere.")


def test_the_record_declares_that_buildings_are_published_as_terrain() -> None:
    """The defect the second-AOI gate found, with every number tied to the run that measured it.

    A limitation is the strongest thing this tool says about its own failures, and it travels into
    every `provenance.json`. A shipped record claiming `basis=measured` over a roof, with ten
    declared limitations and none of them naming it, is the product asserting what it cannot
    support -- which is the one failure the honesty layer exists to prevent.

    So the line is pinned to its evidence rather than to a phrasing: every figure it quotes must
    appear in a document it cites, so the two cannot drift apart the way a number typed into two
    files does.

    The evidence is read from the line's own citations rather than from one filename fixed here.
    Pinned to `ground-filter-diagnosis.md` alone, this test went red the moment the defect was
    measured a second time and the line moved to the newer record -- a lock that fires on a
    correction is a lock that gets edited to whatever the code says.
    """
    from microrelief.cli import LIMITATIONS

    declared = [line for line in LIMITATIONS if "building" in line]
    assert len(declared) == 1, (
        "exactly one limitation must name the building defect; "
        f"found {len(declared)} lines mentioning a building"
    )
    figures = _figures(declared[0])
    assert figures, "a limitation that quotes no measurement is an opinion"
    _assert_every_figure_has_evidence(declared[0])


# --- the filter the pipeline runs, and the parameters the record declares -------------------


def test_the_record_declares_the_smrf_parameters_and_none_of_the_retired_ones(
    tmp_path: Path,
) -> None:
    """The record states what ran. The retired filter's parameters are not merely unused here --
    their presence would say a filter ran that did not."""
    code, out = _synthetic_run(tmp_path)
    assert code == 0
    doc = json.loads((out / "provenance.json").read_text())
    params = doc["parameters"]

    assert params["smrf_cell"] == 1.0
    assert params["smrf_slope"] == 0.15
    assert params["smrf_scalar"] == 1.25
    assert params["smrf_threshold"] == 0.5
    # The resolved width, not the `None` that stands for "18 * cell" in the dataclass: a record
    # that publishes a sentinel has not said what ran.
    assert params["smrf_window_m"] == 18.0

    retired = {"max_window_m", "slope_threshold", "elevation_threshold_m", "max_elevation_m"}
    assert not retired & set(params), f"the record still declares {retired & set(params)}"
    assert not retired & set(doc["uncalibrated_thresholds"])
    for name in ("smrf_cell", "smrf_slope", "smrf_scalar", "smrf_threshold", "smrf_window_m"):
        assert name in doc["uncalibrated_thresholds"], name


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--max-window-m", "4.0"),
        ("--slope-threshold", "0.3"),
        ("--elevation-threshold-m", "0.3"),
        ("--max-elevation-m", "3.5"),
    ],
)
def test_the_retired_parameters_are_rejected_rather_than_silently_ignored(
    tmp_path: Path, flag: str, value: str
) -> None:
    """A removal is asserted, not assumed. An accepted-and-ignored flag is the worse failure:
    the caller believes they set something."""
    with pytest.raises(SystemExit) as exc:  # argparse exits 2 on an unknown option
        _synthetic_run(tmp_path, extra=[flag, value])
    assert exc.value.code == 2


def test_a_cell_that_does_not_divide_the_analysis_cell_refuses_and_says_what_would_work(
    tmp_path: Path, capsys: Any
) -> None:
    """Pinning the SMRF cell at 1 m narrows the admissible `--cell` to 1/k. That is a real
    restriction, so it refuses at the composition root with an actionable message rather than
    somewhere inside the filter."""
    code, _out = _synthetic_run(tmp_path, extra=["--cell", "0.3"])
    assert code != 0
    err = capsys.readouterr().err
    assert "multiple" in err
    assert "0.5" in err, "the refusal must name a cell size that would work"

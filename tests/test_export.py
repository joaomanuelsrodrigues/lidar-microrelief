import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from microrelief.accumulate import Accumulator
from microrelief.density import BASIS_MEASURED, BASIS_UNDETERMINED, compute_basis
from microrelief.export import NODATA_FLOAT, NODATA_INT32, NODATA_UINT8, export
from microrelief.grid import grid_for_bounds
from microrelief.ground import GroundParams, classify_ground
from microrelief.provenance import Provenance
from microrelief.read import PointBatch
from microrelief.surfaces import build_surfaces
from tests.synthetic import ORIGIN_X, ORIGIN_Y, canopy, ramp, with_void
from tests.test_provenance import a_provenance
from tests.test_surfaces import CELL, pipeline


def a_hole() -> Any:
    """A cloud with a void wide enough that its middle is beyond interpolation range."""
    return with_void(ramp(), ORIGIN_X + 10.0, ORIGIN_Y + 10.0, 12.0)


def test_every_band_of_surfaces_reaches_disk(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(ramp())
    written = export(surf, a_provenance(), tmp_path)
    assert set(surf.rasters()) <= set(written)
    assert (tmp_path / "provenance.json").exists()


def test_nan_never_escapes_into_a_band_that_declares_nodata(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(a_hole())
    export(surf, a_provenance(), tmp_path)
    with rasterio.open(tmp_path / "mdt.tif") as src:
        band = src.read(1)
        assert src.nodata == NODATA_FLOAT
        assert not np.isnan(band).any()
        assert (band == NODATA_FLOAT).any()


def test_undetermined_cells_are_nodata_in_the_written_dtm(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(a_hole())
    export(surf, a_provenance(), tmp_path)
    with rasterio.open(tmp_path / "mdt.tif") as src:
        band = src.read(1)
    assert (band[surf.basis == BASIS_UNDETERMINED] == NODATA_FLOAT).all()


def test_measured_values_survive_the_round_trip(tmp_path: Path) -> None:
    """The other half of the NoData claim. Every test above is satisfied by an implementation
    that writes NoData everywhere; this one says the file carries what the array carried."""
    _g, _s, surf = pipeline(a_hole())
    export(surf, a_provenance(), tmp_path)
    with rasterio.open(tmp_path / "mdt.tif") as src:
        band = src.read(1)
    measured = surf.basis == BASIS_MEASURED
    assert measured.sum() > 0
    assert np.array_equal(band[measured], surf.mdt[measured])


def test_counts_and_codes_stay_integers_on_disk(tmp_path: Path) -> None:
    """A count written as a float is a count you can no longer trust to be exact, and a class
    code written as a float stops being a class code. The dtype is part of what each band means."""
    _g, _s, surf = pipeline(ramp())
    export(surf, a_provenance(), tmp_path)
    expected = {
        "mdt": "float32",
        "mds": "float32",
        "chm": "float32",
        "basis": "uint8",
        "n_all": "int32",
        "n_ground_asprs": "int32",
    }
    for name, dtype in expected.items():
        with rasterio.open(tmp_path / f"{name}.tif") as src:
            assert src.dtypes[0] == dtype, name


def test_the_undetermined_code_is_a_value_not_a_hole(tmp_path: Path) -> None:
    """`undetermined` is a published state — we looked, and there was nothing to measure. Declaring
    it as the basis band's NoData would erase exactly the admission the band exists to make."""
    _g, _s, surf = pipeline(a_hole())
    export(surf, a_provenance(), tmp_path)
    with rasterio.open(tmp_path / "basis.tif") as src:
        band = src.read(1)
        assert src.nodata == NODATA_UINT8
    assert (band == BASIS_UNDETERMINED).sum() == int((surf.basis == BASIS_UNDETERMINED).sum())
    assert (band == BASIS_UNDETERMINED).sum() > 0


def test_a_count_band_declares_a_nodata_no_count_can_be(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(a_hole())
    export(surf, a_provenance(), tmp_path)
    with rasterio.open(tmp_path / "n_all.tif") as src:
        assert src.nodata == NODATA_INT32
        assert (src.read(1) >= 0).all()


def test_crs_and_transform_come_from_the_one_grid(tmp_path: Path) -> None:
    g, _s, surf = pipeline(ramp())
    export(surf, a_provenance(), tmp_path)
    for name in surf.rasters():
        with rasterio.open(tmp_path / f"{name}.tif") as src:
            assert src.crs.to_epsg() == 3763
            assert src.transform == g.transform
            assert (src.height, src.width) == g.shape


def test_a_rectangular_aoi_is_written_with_its_own_shape(tmp_path: Path) -> None:
    """Every fixture in this repo is square, so `(height, width) == grid.shape` holds just as well
    for an implementation that swaps the two — measured: swapping them fails no other test here.
    A real AOI need not be square, and a swap would silently transpose the whole product.
    """
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 12.0, ORIGIN_Y + 6.0, CELL, 3763)
    assert g.n_rows != g.n_cols
    acc = Accumulator(g)
    cloud = ramp(size_m=12.0, spacing=0.5)
    acc.add(PointBatch(cloud.x, cloud.y, cloud.z, cloud.classification, 3763, Path("m"), "0" * 64))
    stats = acc.finish()
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))
    surf = build_surfaces(g, stats, compute_basis(is_ground, stats, CELL))

    export(surf, a_provenance(), tmp_path)
    for name in surf.rasters():
        with rasterio.open(tmp_path / f"{name}.tif") as src:
            assert (src.height, src.width) == g.shape == (12, 24), name


def test_attribution_travels_inside_the_file(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(ramp())
    prov = a_provenance()
    export(surf, prov, tmp_path)
    with rasterio.open(tmp_path / "mdt.tif") as src:
        tags = src.tags()
    assert "CC BY 4.0" in tags["attribution"]
    assert tags["reproducibility_hash"] == prov.reproducibility_hash


def test_every_band_carries_the_attribution_not_only_the_first(tmp_path: Path) -> None:
    """Any one of these files can be opened alone by someone who never saw the others."""
    _g, _s, surf = pipeline(ramp())
    export(surf, a_provenance(), tmp_path)
    for name in surf.rasters():
        with rasterio.open(tmp_path / f"{name}.tif") as src:
            assert "CC BY 4.0" in src.tags()["attribution"], name


def test_two_runs_produce_identical_bytes(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(ramp())
    prov = a_provenance()
    a, b = tmp_path / "a", tmp_path / "b"
    export(surf, prov, a)
    export(surf, prov, b)
    for name in surf.rasters():
        assert (
            hashlib.sha256((a / f"{name}.tif").read_bytes()).hexdigest()
            == hashlib.sha256((b / f"{name}.tif").read_bytes()).hexdigest()
        ), name


def test_provenance_json_is_written_and_parses(tmp_path: Path) -> None:
    _g, _s, surf = pipeline(ramp())
    prov = a_provenance()
    export(surf, prov, tmp_path)
    doc = json.loads((tmp_path / "provenance.json").read_text())
    assert doc["reproducibility_hash"] == prov.reproducibility_hash


def test_the_sidecar_carries_every_field_the_record_holds(tmp_path: Path) -> None:
    """The sibling shape (§A3/s246), on the boundary where the record leaves the process: a field
    added to `Provenance` and not serialised would be missed by every test naming its own keys."""
    _g, _s, surf = pipeline(ramp())
    export(surf, a_provenance(), tmp_path)
    doc = json.loads((tmp_path / "provenance.json").read_text())
    assert set(doc) == {f.name for f in fields(Provenance)}


def golden_fixtures() -> dict[str, Any]:
    """Two clouds, because no single one exercises the whole chain.

    `ramp_with_void` is the only one that produces all three basis codes — at one return per cell
    a canopy void gets filled by the filter — and `canopy_dense` is the only one whose CHM is not
    identically zero, because a cell needs both a ground and a canopy return to have a height at
    all. A golden over either alone locks half of what this package claims to do.
    """
    return {
        "ramp_with_void": with_void(
            ramp(size_m=10.0, spacing=0.5), ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 6.0
        ),
        "canopy_dense": canopy(size_m=10.0, spacing=0.25, ground_fraction=0.6),
    }


def test_golden_hashes_are_unchanged(tmp_path: Path) -> None:
    """Locks the whole chain. If this breaks, either a real bug was introduced or the outputs
    legitimately changed — and in the second case the golden file is updated *in the same commit*
    as the change that justifies it, never on its own.

    Machine-local by construction: these bytes depend on the GDAL and libdeflate builds. Replay
    across two machines is not verified, and the README says so rather than implying otherwise.
    """
    golden = json.loads((Path(__file__).parent / "fixtures" / "golden_hashes.json").read_text())
    fixtures = golden_fixtures()
    assert set(golden) == set(fixtures), "the golden file does not cover every fixture"
    for label, cloud in fixtures.items():
        _g, _s, surf = pipeline(cloud, size_m=10.0)
        out = tmp_path / label
        export(surf, a_provenance(), out)
        assert set(golden[label]) == set(surf.rasters()), f"{label}: golden misses a band"
        for name, expected in golden[label].items():
            actual = hashlib.sha256((out / f"{name}.tif").read_bytes()).hexdigest()
            assert actual == expected, f"{label}/{name}"


def test_the_golden_fixtures_still_exercise_what_they_were_chosen_for(tmp_path: Path) -> None:
    """A golden whose fixture quietly stopped covering the interesting cases is a green test over
    nothing. This states what each one is *for*, so a change that flattens them fails here with a
    reason rather than there with a hash."""
    _g, _s, void = pipeline(golden_fixtures()["ramp_with_void"], size_m=10.0)
    assert set(np.unique(void.basis)) == {0, 1, 2}, "ramp_with_void no longer shows all three"

    _g2, _s2, dense = pipeline(golden_fixtures()["canopy_dense"], size_m=10.0)
    heights = dense.chm[np.isfinite(dense.chm)]
    assert heights.size > 0 and heights.max() > 1.0, "canopy_dense no longer has a canopy"

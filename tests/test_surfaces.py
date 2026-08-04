from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from microrelief.accumulate import Accumulator, CellStats
from microrelief.density import (
    BASIS_INTERPOLATED,
    BASIS_MEASURED,
    BASIS_UNDETERMINED,
    compute_basis,
)
from microrelief.grid import Grid, grid_for_bounds
from microrelief.ground import GroundParams, classify_ground
from microrelief.read import PointBatch
from microrelief.surfaces import Surfaces, build_surfaces
from tests.synthetic import ORIGIN_X, ORIGIN_Y, Cloud, canopy, ramp, with_void

CELL = 0.5


def pipeline(cloud: Cloud, size_m: float = 50.0) -> tuple[Grid, CellStats, Surfaces]:
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + size_m, ORIGIN_Y + size_m, CELL, 3763)
    acc = Accumulator(g)
    acc.add(PointBatch(cloud.x, cloud.y, cloud.z, cloud.classification, 3763, Path("m"), "0" * 64))
    stats = acc.finish()
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))
    return g, stats, build_surfaces(g, stats, compute_basis(is_ground, stats, CELL))


def test_chm_recovers_a_known_tree_height() -> None:
    _g, _s, surf = pipeline(canopy(tree_height=8.0, ground_fraction=0.3))
    both = (surf.basis == BASIS_MEASURED) & np.isfinite(surf.chm)
    assert np.nanmedian(surf.chm[both & (surf.chm > 1.0)]) == pytest.approx(8.0, abs=1.5)


def test_chm_is_exactly_mds_minus_mdt_wherever_both_are_measured() -> None:
    _g, _s, surf = pipeline(canopy())
    m = (surf.basis == BASIS_MEASURED) & np.isfinite(surf.mds)
    assert np.allclose(surf.chm[m], surf.mds[m] - surf.mdt[m], equal_nan=True)


def test_chm_stays_nodata_on_a_borrowed_ground_even_where_the_surface_was_seen() -> None:
    """A canopy height is a difference of two measurements or it is nothing.

    An interpolated cell has a real DSM (returns hit the canopy) and a borrowed DTM. Subtracting
    them would publish a tree height computed against ground that was never seen there. This is
    the assertion the `chm == mds - mdt` test cannot make: that one only inspects cells where the
    subtraction is already allowed.
    """
    _g, _s, surf = pipeline(with_void(canopy(), ORIGIN_X + 20.0, ORIGIN_Y + 20.0, 3.0))
    borrowed = surf.basis == BASIS_INTERPOLATED
    assert borrowed.any(), "the fixture must actually produce interpolated cells"
    assert np.isfinite(surf.mds[borrowed]).any(), "and some of them must have a measured surface"
    assert np.isnan(surf.chm[borrowed]).all()


def test_an_interpolated_cell_carries_the_elevation_of_the_cell_it_names() -> None:
    g, stats, surf = pipeline(with_void(ramp(), ORIGIN_X + 20.0, ORIGIN_Y + 20.0, 3.0))
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))
    basis = compute_basis(is_ground, stats, CELL)
    borrowed = basis.basis == BASIS_INTERPOLATED
    assert borrowed.any()
    lender = stats.min_z_all[basis.source_row[borrowed], basis.source_col[borrowed]]
    assert np.allclose(surf.mdt[borrowed], lender)


def test_an_undetermined_cell_is_nodata_in_the_dtm_never_a_number() -> None:
    _g, _s, surf = pipeline(with_void(ramp(), ORIGIN_X + 10.0, ORIGIN_Y + 10.0, 12.0))
    undetermined = surf.basis == BASIS_UNDETERMINED
    assert undetermined.any(), "the fixture must actually produce undetermined cells"
    assert np.isnan(surf.mdt[undetermined]).all()


def test_the_dsm_reports_nothing_where_nothing_was_returned() -> None:
    """`CellStats` is a bare dataclass, so this invariant belongs to its producer, not its type.

    `Accumulator.finish()` already NaNs the extrema of empty cells, which makes the guard in
    `build_surfaces` indistinguishable from its absence on every cloud in this file — a mutation
    deleting it passes all of them. It is kept and driven here instead, because the invariant it
    protects is the load-bearing one of the whole piece: NaN means nothing was measured, and only
    that. A hand-built or future `CellStats` carrying a stale extremum over zero returns must not
    put a surface elevation on the map.
    """
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 5.0, ORIGIN_Y + 5.0, CELL, 3763)
    n_all = np.ones(g.shape, np.int32) * 3
    n_all[4, 4] = 0  # no returns here...
    z = np.ones(g.shape, np.float32)  # ...but a stale extremum says otherwise
    stats = CellStats(z, z, n_all, np.zeros(g.shape, np.int32), z, 0)
    surf = build_surfaces(g, stats, compute_basis(np.ones(g.shape, bool), stats, CELL))

    assert np.isnan(surf.mds[4, 4])
    assert np.isnan(surf.chm[4, 4])
    assert np.isfinite(surf.mds).sum() == surf.mds.size - 1


def test_every_published_raster_shares_the_one_grid() -> None:
    """One test over the whole set. A fourth product added without a basis breaks this."""
    g, _s, surf = pipeline(ramp())
    for name, band in surf.rasters().items():
        assert band.shape == g.shape, name


def test_rasters_publishes_every_band_the_dataclass_holds() -> None:
    """The sibling bug, closed at the source rather than one band at a time.

    Iterating `rasters()` cannot notice a band that was added to `Surfaces` and left out of
    `rasters()` — the loop simply never visits it, and export, which iterates the same dict,
    would ship a product the contract tests never saw. So the contract is stated against the
    dataclass's own fields, which is the thing that grows when a band is added.
    """
    _g, _s, surf = pipeline(ramp())
    array_fields = {f.name for f in fields(surf) if isinstance(getattr(surf, f.name), np.ndarray)}
    assert set(surf.rasters()) == array_fields


def test_no_cell_carries_a_value_without_a_basis_code() -> None:
    _g, _s, surf = pipeline(canopy())
    has_value = np.isfinite(surf.mdt)
    assert (surf.basis[has_value] != BASIS_UNDETERMINED).all()


def test_ramp_is_recovered_within_tolerance() -> None:
    g, _s, surf = pipeline(ramp(slope=0.1))
    rows, cols = np.nonzero(surf.basis == BASIS_MEASURED)
    xs = g.origin_x + (cols + 0.5) * CELL
    truth = 0.1 * (xs - ORIGIN_X)
    assert np.nanmax(np.abs(surf.mdt[rows, cols] - truth)) < 0.2

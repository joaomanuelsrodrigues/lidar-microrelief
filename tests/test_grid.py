import dataclasses

import numpy as np
import pytest

from microrelief.grid import GridError, grid_for_bounds


def test_origin_snaps_to_cell_multiples_so_tile_edges_land_on_cell_edges() -> None:
    # DGT tiles start on a 1000 m lattice in EPSG:3763; at 0.5 m, 1000/0.5 is an integer,
    # so a snapped origin puts every tile boundary exactly on a cell edge.
    g = grid_for_bounds(48000.3, 168000.2, 50000.0, 170000.0, cell=0.5, crs_epsg=3763)
    assert g.origin_x == 48000.0
    assert g.origin_y == 170000.0
    assert ((49000.0 - g.origin_x) / g.cell) % 1 == 0


def test_cell_indices_are_row_major_from_the_top_left() -> None:
    g = grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=1.0, crs_epsg=3763)
    x = np.array([0.5, 9.5])
    y = np.array([9.5, 0.5])
    row, col, inside = g.cell_indices(x, y)
    assert inside.all()
    assert row.tolist() == [0, 9]
    assert col.tolist() == [0, 9]


def test_points_outside_the_grid_are_flagged_not_clipped() -> None:
    g = grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=1.0, crs_epsg=3763)
    x = np.array([-0.1, 5.0, 10.5])
    y = np.array([5.0, 5.0, 5.0])
    _row, _col, inside = g.cell_indices(x, y)
    assert inside.tolist() == [False, True, False]


def test_grid_above_the_memory_ceiling_refuses_with_the_number_in_the_message() -> None:
    with pytest.raises(GridError, match="1600000000 cells"):
        grid_for_bounds(0.0, 0.0, 20000.0, 20000.0, cell=0.5, crs_epsg=3763, max_cells=1_000_000)


def test_degenerate_bounds_refuse() -> None:
    with pytest.raises(GridError, match="empty extent"):
        grid_for_bounds(10.0, 0.0, 10.0, 5.0, cell=0.5, crs_epsg=3763)
    with pytest.raises(GridError, match="positive, finite"):
        grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=0.0, crs_epsg=3763)


def test_grid_is_frozen_so_no_stage_can_redefine_it_midway() -> None:
    g = grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=1.0, crs_epsg=3763)
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.cell = 2.0  # type: ignore[misc]


def test_the_grid_snaps_outward_to_whole_blocks_when_a_block_size_is_given() -> None:
    """An analysis that works in blocks of N cells needs a grid that is whole blocks.

    Without this the ground filter refuses any AOI whose extent happens to be odd, which is
    unconstrained: `n_cols` and `n_rows` are `ceil()` of an arbitrary extent.
    """
    plain = grid_for_bounds(0.0, 0.0, 10.5, 12.5, cell=1.0, crs_epsg=3763)
    assert (plain.n_cols, plain.n_rows) == (11, 13)

    snapped = grid_for_bounds(0.0, 0.0, 10.5, 12.5, cell=1.0, crs_epsg=3763, block=2)
    assert (snapped.n_cols, snapped.n_rows) == (12, 14)
    assert (snapped.origin_x, snapped.origin_y) == (plain.origin_x, plain.origin_y)


def test_a_grid_that_is_already_whole_blocks_is_left_alone() -> None:
    """The two products this package publishes are 300 and 3960 cells square; the snap must be
    a no-op on them, or wiring it would move a published record hash for no reason."""
    for n, cell in ((300, 0.5), (3960, 0.5)):
        extent = n * cell
        plain = grid_for_bounds(0.0, 0.0, extent, extent, cell=cell, crs_epsg=3763)
        snapped = grid_for_bounds(0.0, 0.0, extent, extent, cell=cell, crs_epsg=3763, block=2)
        assert (plain.n_cols, plain.n_rows) == (n, n)
        assert snapped == plain


def test_the_default_block_of_one_changes_nothing() -> None:
    for bounds in ((0.0, 0.0, 10.5, 12.5), (48000.3, 168000.2, 50000.0, 170000.0)):
        assert grid_for_bounds(*bounds, cell=0.5, crs_epsg=3763) == grid_for_bounds(
            *bounds, cell=0.5, crs_epsg=3763, block=1
        )


def test_a_block_size_below_one_is_refused_rather_than_dividing_by_it() -> None:
    """`round(smrf_cell / grid_cell)` is 0 for a grid coarser than the analysis cell, and 0 is
    the one value that turns a snap into a crash rather than a wrong answer."""
    with pytest.raises(GridError, match="block"):
        grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=1.0, crs_epsg=3763, block=0)


def test_the_memory_ceiling_is_checked_after_the_snap_not_before() -> None:
    """The snap can only grow the grid, so a ceiling checked before it is a ceiling the run can
    cross. 9 x 9 cells fit under 100; snapped to blocks of 4 they are 12 x 12 = 144, which does
    not."""
    assert grid_for_bounds(0.0, 0.0, 9.0, 9.0, cell=1.0, crs_epsg=3763, max_cells=100).n_cells == 81
    with pytest.raises(GridError, match="144 cells"):
        grid_for_bounds(0.0, 0.0, 9.0, 9.0, cell=1.0, crs_epsg=3763, max_cells=100, block=4)

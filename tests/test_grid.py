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
    with pytest.raises(GridError, match="cell must be positive"):
        grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=0.0, crs_epsg=3763)


def test_grid_is_frozen_so_no_stage_can_redefine_it_midway() -> None:
    g = grid_for_bounds(0.0, 0.0, 10.0, 10.0, cell=1.0, crs_epsg=3763)
    with pytest.raises(Exception):  # noqa: B017
        g.cell = 2.0  # type: ignore[misc]

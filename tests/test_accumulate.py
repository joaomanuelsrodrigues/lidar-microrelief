import numpy as np
import pytest

from microrelief.accumulate import Accumulator
from microrelief.grid import grid_for_bounds
from microrelief.read import PointBatch
from tests.synthetic import GROUND, ORIGIN_X, ORIGIN_Y, VEGETATION, ramp


def batch_from(cloud, path="mem") -> PointBatch:
    from pathlib import Path

    return PointBatch(cloud.x, cloud.y, cloud.z, cloud.classification, 3763, Path(path), "0" * 64)


def test_min_and_max_per_cell_are_the_real_min_and_max() -> None:
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 1.0, 3763)
    x = np.array([ORIGIN_X + 0.5] * 3)
    y = np.array([ORIGIN_Y + 0.5] * 3)
    z = np.array([10.0, 5.0, 7.0])
    cls = np.full(3, GROUND, np.uint8)
    acc = Accumulator(g)
    acc.add(PointBatch(x, y, z, cls, 3763, __import__("pathlib").Path("m"), "0" * 64))
    stats = acc.finish()
    row, col = 1, 0  # y = origin_y + 0.5 is one row below the top edge
    assert stats.min_z_all[row, col] == pytest.approx(5.0)
    assert stats.max_z_all[row, col] == pytest.approx(10.0)
    assert stats.n_all[row, col] == 3


def test_two_tiles_land_in_one_grid_with_no_seam() -> None:
    """The property that makes a mosaic step unnecessary: order of tiles cannot matter."""
    c = ramp(size_m=20.0, spacing=0.5)
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 20.0, ORIGIN_Y + 20.0, 1.0, 3763)
    left = c.x < ORIGIN_X + 10.0

    def stats_for(order):
        acc = Accumulator(g)
        for mask in order:
            acc.add(
                batch_from(
                    type(c)(
                        c.x[mask], c.y[mask], c.z[mask], c.classification[mask], c.truth_surface
                    )
                )
            )
        return acc.finish()

    a = stats_for([left, ~left])
    b = stats_for([~left, left])
    assert np.array_equal(a.n_all, b.n_all)
    assert np.allclose(a.min_z_all, b.min_z_all, equal_nan=True)


def test_empty_cells_are_nan_not_zero() -> None:
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 5.0, ORIGIN_Y + 5.0, 1.0, 3763)
    acc = Accumulator(g)
    acc.add(batch_from(ramp(size_m=1.0, spacing=0.5)))
    stats = acc.finish()
    assert np.isnan(stats.min_z_all).any()
    assert (stats.n_all == 0).any()
    # zero would be a plausible elevation; NaN cannot be mistaken for a measurement
    assert not (stats.min_z_all[np.isnan(stats.min_z_all)] == 0).any()


def test_points_outside_the_grid_are_counted_not_folded_onto_the_border() -> None:
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 1.0, 3763)
    x = np.array([ORIGIN_X - 50.0, ORIGIN_X + 0.5])
    y = np.array([ORIGIN_Y + 0.5, ORIGIN_Y + 0.5])
    acc = Accumulator(g)
    acc.add(
        PointBatch(
            x,
            y,
            np.array([1.0, 2.0]),
            np.full(2, GROUND, np.uint8),
            3763,
            __import__("pathlib").Path("m"),
            "0" * 64,
        )
    )
    stats = acc.finish()
    assert stats.n_outside == 1
    assert stats.n_all.sum() == 1


def test_official_ground_counts_are_tracked_separately_from_all_returns() -> None:
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 1.0, 3763)
    x = np.array([ORIGIN_X + 0.5] * 2)
    y = np.array([ORIGIN_Y + 0.5] * 2)
    cls = np.array([GROUND, VEGETATION], np.uint8)
    acc = Accumulator(g)
    acc.add(
        PointBatch(x, y, np.array([3.0, 9.0]), cls, 3763, __import__("pathlib").Path("m"), "0" * 64)
    )
    stats = acc.finish()
    assert stats.n_all[1, 0] == 2
    assert stats.n_ground_asprs[1, 0] == 1
    assert stats.min_z_ground_asprs[1, 0] == pytest.approx(3.0)


def test_add_refuses_a_batch_whose_crs_does_not_match_the_grid() -> None:
    """The CRS check is relational (batch vs. the grid it is poured into), not a hardcoded

    national assumption -- there is no `TILE_CRS_EPSG` constant to check against instead. A
    grid built for EPSG:3763 must refuse a batch declaring EPSG:4326, loudly, before any point
    of that batch is touched.
    """
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 1.0, 3763)
    x = np.array([ORIGIN_X + 0.5])
    y = np.array([ORIGIN_Y + 0.5])
    mismatched = PointBatch(
        x,
        y,
        np.array([1.0]),
        np.full(1, GROUND, np.uint8),
        4326,
        __import__("pathlib").Path("m"),
        "0" * 64,
    )
    acc = Accumulator(g)
    with pytest.raises(ValueError, match="4326"):
        acc.add(mismatched)
    stats = acc.finish()
    assert stats.n_all.sum() == 0
    assert stats.n_outside == 0

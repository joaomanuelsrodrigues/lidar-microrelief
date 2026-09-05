import inspect

import numpy as np
import pytest

from microrelief.accumulate import Accumulator
from microrelief.cli import LIMITATIONS
from microrelief.grid import BYTES_PER_CELL, grid_for_bounds
from microrelief.read import PointBatch
from tests.synthetic import GROUND, ORIGIN_X, ORIGIN_Y, VEGETATION, ramp, with_void


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
    """Zero and "nothing measured" must stay distinguishable in both directions: a cell whose

    only return is a genuine z == 0.0 publishes 0.0, and a cell with no returns at all
    publishes NaN -- neither may be mistaken for the other.
    """
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 5.0, ORIGIN_Y + 5.0, 1.0, 3763)
    acc = Accumulator(g)
    acc.add(batch_from(ramp(size_m=1.0, spacing=0.5)))  # lands in row 4, cols 0-1 only
    # A genuine z == 0.0 measurement, landing in row 0, col 4 -- a cell the ramp never touches.
    acc.add(
        PointBatch(
            np.array([ORIGIN_X + 4.5]),
            np.array([ORIGIN_Y + 4.5]),
            np.array([0.0]),
            np.full(1, GROUND, np.uint8),
            3763,
            __import__("pathlib").Path("m"),
            "0" * 64,
        )
    )
    stats = acc.finish()

    zero_row, zero_col = 0, 4
    empty_row, empty_col = 2, 2  # untouched by either batch

    assert stats.n_all[empty_row, empty_col] == 0
    assert np.isnan(stats.min_z_all[empty_row, empty_col])

    assert stats.n_all[zero_row, zero_col] == 1
    assert not np.isnan(stats.min_z_all[zero_row, zero_col])
    assert stats.min_z_all[zero_row, zero_col] == pytest.approx(0.0)


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


def test_a_cell_with_only_vegetation_publishes_no_ground_minimum() -> None:
    """A cell that has returns but none classified ground must not leak the accumulator's

    +inf initialiser into a published field. `min_z_all` (masked by `n_all == 0`) stays a real
    number; `min_z_ground_asprs` (masked by `n_ground == 0`, a *different* counter) must be NaN,
    not +inf -- +inf would pass `np.isnan() == False` and silently poison anything downstream
    that expects "not NaN" to mean "a real measurement."
    """
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 2.0, ORIGIN_Y + 2.0, 1.0, 3763)
    x = np.array([ORIGIN_X + 0.5] * 2)
    y = np.array([ORIGIN_Y + 0.5] * 2)
    cls = np.full(2, VEGETATION, np.uint8)
    acc = Accumulator(g)
    acc.add(
        PointBatch(x, y, np.array([4.0, 6.0]), cls, 3763, __import__("pathlib").Path("m"), "0" * 64)
    )
    stats = acc.finish()
    assert stats.n_all[1, 0] == 2
    assert stats.n_ground_asprs[1, 0] == 0
    assert np.isfinite(stats.min_z_all[1, 0])
    assert np.isnan(stats.min_z_ground_asprs[1, 0])


def test_with_void_empties_exactly_size_over_cell_grid_rows() -> None:
    """`with_void`'s y-selection must align with the grid's own (top-closed, bottom-open) row

    convention, not the "intuitive" bottom-closed reading that agrees with it in x but points
    the opposite way in y -- otherwise a void of `size` empties one row short, with a lattice
    line surviving at the boundary as a sparsely-measured cell instead of an empty one.
    """
    cell = 0.5
    c = with_void(ramp(size_m=50.0, spacing=0.2), ORIGIN_X + 10.0, ORIGIN_Y + 10.0, 5.0)
    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 50.0, ORIGIN_Y + 50.0, cell, 3763)
    acc = Accumulator(g)
    acc.add(batch_from(c))
    stats = acc.finish()

    col_lo, col_hi = int(10.0 / cell), int(15.0 / cell)
    fully_empty_rows = int((stats.n_all[:, col_lo:col_hi] == 0).all(axis=1).sum())
    assert fully_empty_rows == int(5.0 / cell)


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


def test_the_published_byte_cost_per_cell_is_the_measured_one() -> None:
    """`BYTES_PER_CELL` ships in three unlocked copies and one of them is in every record.

    The number reaches the refusal message (`grid.py`), the declared limitation
    (`cli.LIMITATIONS`, hence every `provenance.json` the tool writes) and the README. Its
    docstring says "measured rather than estimated" and until this test nothing measured it: add a
    sixth accumulator array or widen a `CellStats` dtype and all three copies silently
    understate, while the published record keeps asserting a ceiling that is not the one the
    memory actually implies.

    So this measures it, from the objects themselves, and ties the two halves to the constant.
    """
    grid = grid_for_bounds(0.0, 0.0, 100.0, 100.0, cell=0.5, crs_epsg=3763)
    n = grid.n_cells
    acc = Accumulator(grid)

    live = [v for v in vars(acc).values() if isinstance(v, np.ndarray)]
    assert len(live) == 5, f"the accumulator holds {len(live)} arrays, not the five declared"
    acc_bytes = sum(a.nbytes for a in live) / n

    stats = acc.finish()
    published = [v for v in vars(stats).values() if isinstance(v, np.ndarray)]
    assert len(published) == 5, f"CellStats holds {len(published)} arrays, not the five declared"
    stats_bytes = sum(a.nbytes for a in published) / n

    assert acc_bytes == 40.0, f"accumulator is {acc_bytes} B/cell, CALIBRATIONS.md says 40"
    assert stats_bytes == 20.0, f"CellStats is {stats_bytes} B/cell, CALIBRATIONS.md says 20"
    assert acc_bytes + stats_bytes == BYTES_PER_CELL


def test_the_ceiling_the_record_publishes_is_the_ceiling_the_code_enforces() -> None:
    """The literal in `LIMITATIONS` travels into every published record; the default in
    `grid_for_bounds` is what actually refuses. Nothing tied them together, so changing the
    default would leave every `provenance.json` asserting a ceiling that is not enforced."""
    enforced = inspect.signature(grid_for_bounds).parameters["max_cells"].default
    declared = [line for line in LIMITATIONS if "resource ceiling" in line]
    assert len(declared) == 1, "the ceiling limitation is not where this test expects it"
    assert f"{enforced:,} cells" in declared[0], (
        f"the record declares a ceiling that is not {enforced:,}"
    )
    implied_gb = enforced * BYTES_PER_CELL / 1e9
    assert f"~{implied_gb:.0f} GB" in declared[0], (
        f"the record's byte figure is not {implied_gb:.0f} GB"
    )

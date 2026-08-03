import numpy as np
import pytest

from microrelief.accumulate import Accumulator
from microrelief.grid import grid_for_bounds
from microrelief.ground import GroundError, GroundParams, classify_ground, windows_for
from microrelief.read import PointBatch
from tests.synthetic import ORIGIN_X, ORIGIN_Y, canopy, hillside, ramp, terraced

CELL = 0.5
SIZE_M = 50.0
RISER = 1.5
# hillside() puts its crest at the middle of the extent; this is that column in the grid.
CREST_COL = int((SIZE_M / 2) / CELL)


def stats_for(cloud, size_m=SIZE_M):
    from pathlib import Path

    g = grid_for_bounds(ORIGIN_X, ORIGIN_Y, ORIGIN_X + size_m, ORIGIN_Y + size_m, CELL, 3763)
    acc = Accumulator(g)
    acc.add(PointBatch(cloud.x, cloud.y, cloud.z, cloud.classification, 3763, Path("m"), "0" * 64))
    return g, acc.finish()


def test_a_gentle_ramp_is_entirely_ground() -> None:
    g, stats = stats_for(ramp(slope=0.1))
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))
    measured = stats.n_all > 0
    assert is_ground[measured].mean() > 0.98


def test_terrace_risers_survive_while_the_tolerance_stays_under_the_riser() -> None:
    """The acid test. A terrace riser is an abrupt vertical discontinuity, and the filter's job is
    to leave it alone while removing objects. It is run on `hillside` rather than `terraced`
    because `terraced` is monotone and a morphological opening removes only local maxima -- so it
    survives every window by construction, and passing on it would prove nothing.
    """
    g, stats = stats_for(hillside(tread=6.0, riser=RISER))
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(24.0, 0.3, 0.3, 3.0))
    measured = stats.n_all > 0
    assert is_ground[measured].mean() > 0.95

    # The claim is about structure, and it is asserted on what the filter produces: a mask.
    # Comparing `min_z_all` against the true surface would test the accumulator instead --
    # `classify_ground` never touches a value -- and would fail on the cells a riser falls
    # inside, where the min over the cell is legitimately the lower terrace while the cell
    # centre is on the upper one.
    kept = stats.min_z_all[measured & is_ground]
    levels = np.unique(np.round(kept / RISER).astype(int))
    assert levels.size == 5, f"a whole terrace level was removed: {levels}"
    assert kept.min() == pytest.approx(-6.0)  # crest-to-edge relief, undiminished
    assert kept.max() == pytest.approx(0.0)


def test_terraces_are_destroyed_once_the_tolerance_falls_below_one_riser() -> None:
    """The failure is asserted, not assumed -- and it is asserted against the parameter that
    actually causes it. Same fixture and same window as the test above: only `max_elevation_m`
    moves, from above one riser to below it. That is what makes the cap a calibrated choice
    rather than a default someone copied.
    """
    g, stats = stats_for(hillside(tread=6.0, riser=RISER))
    measured = stats.n_all > 0
    tolerance_below_a_riser = RISER - 0.5
    is_ground = classify_ground(
        stats.min_z_all, CELL, GroundParams(24.0, 0.3, 0.3, tolerance_below_a_riser)
    )
    assert is_ground[measured].mean() < 0.90

    # The damage must be at the crest, not at the array edge: `mode="nearest"` clamps the border,
    # and a boundary artefact would satisfy the fraction above while proving nothing about terraces.
    _rows, cols = np.nonzero(measured & ~is_ground)
    assert cols.min() < CREST_COL < cols.max()
    assert cols.min() > 0
    assert cols.max() < g.n_cols - 1


def test_a_monotone_staircase_cannot_be_damaged_by_any_window() -> None:
    """Pins the finding that retired the previous version of this test file (s256).

    An opening removes local maxima; a staircase that only ever climbs has none. So `terraced`
    reads as entirely ground at a window four times its tread, and any test using it to
    demonstrate window-driven destruction passes for a reason unrelated to its name.
    """
    g, stats = stats_for(terraced(tread=6.0, riser=RISER))
    measured = stats.n_all > 0
    for max_window_m in (1.0, 4.0, 24.0):
        is_ground = classify_ground(
            stats.min_z_all, CELL, GroundParams(max_window_m, 0.3, 0.3, 3.0)
        )
        assert is_ground[measured].all(), f"{max_window_m} m window damaged a monotone staircase"


def test_max_window_m_is_a_ceiling_on_the_radius_search_not_a_window() -> None:
    """The radius doubles, so the parameter names a bound the filter never reaches."""
    assert windows_for(24.0, 0.5) == (1.5, 2.5, 4.5, 8.5, 16.5)
    assert windows_for(4.0, 0.5) == windows_for(6.0, 0.5) == (1.5, 2.5, 4.5)
    assert windows_for(0.1, 0.5) == (1.5,)  # never empty: one window is always run


def test_canopy_returns_are_rejected_as_objects() -> None:
    g, stats = stats_for(canopy(tree_height=8.0, ground_fraction=0.3))
    is_ground = classify_ground(stats.min_z_all, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))
    measured = stats.n_all > 0
    # Cells whose lowest return is high above the local surface must not be called ground.
    high = measured & (stats.min_z_all > np.nanpercentile(stats.min_z_all, 50) + 4.0)
    assert is_ground[high].mean() < 0.2


def test_an_all_empty_grid_refuses() -> None:
    empty = np.full((10, 10), np.nan, dtype=np.float32)
    with pytest.raises(GroundError, match="no measured cells"):
        classify_ground(empty, CELL, GroundParams(4.0, 0.3, 0.3, 3.0))


def test_the_filter_is_deterministic() -> None:
    g, stats = stats_for(terraced())
    p = GroundParams(4.0, 0.3, 0.3, 3.0)
    assert np.array_equal(
        classify_ground(stats.min_z_all, CELL, p), classify_ground(stats.min_z_all, CELL, p)
    )

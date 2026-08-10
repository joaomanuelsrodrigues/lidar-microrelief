"""Metre arithmetic on a CRS measured in degrees is the silent-wrong-answer class."""

import pytest

from microrelief.crs import CRSError, require_metric_crs
from microrelief.grid import Grid, grid_for_bounds


def test_a_projected_metric_crs_is_accepted() -> None:
    require_metric_crs(3763)  # PT-TM06/ETRS89, the calibration site's CRS
    require_metric_crs(32629)  # UTM 29N, a different metric CRS entirely


def test_a_geographic_crs_is_refused_by_name() -> None:
    with pytest.raises(CRSError, match="degree"):
        require_metric_crs(4326)


def test_an_unresolvable_epsg_is_refused_rather_than_assumed() -> None:
    with pytest.raises(CRSError, match="not a known EPSG code"):
        require_metric_crs(999999)


def test_the_grid_itself_refuses_a_geographic_crs() -> None:
    """The guard sits on Grid, not only on grid_for_bounds: a library caller that builds a
    Grid directly must not get past it either."""
    with pytest.raises(CRSError):
        Grid(origin_x=0.0, origin_y=10.0, cell=1.0, n_cols=10, n_rows=10, crs_epsg=4326)


def test_grid_for_bounds_refuses_a_geographic_crs() -> None:
    with pytest.raises(CRSError):
        grid_for_bounds(-8.5, 41.9, -8.4, 42.0, cell=0.5, crs_epsg=4326)


def test_the_guard_is_what_refuses_and_not_some_other_precondition() -> None:
    """Positive control. The geographic bounds above are also tiny in metres; if the refusal
    came from an extent or cell-count check instead, this identical call with a metric CRS
    would fail too. It must succeed."""
    grid = grid_for_bounds(-8.5, 41.9, -8.4, 42.0, cell=0.5, crs_epsg=3763)
    assert grid.n_cols > 0 and grid.n_rows > 0

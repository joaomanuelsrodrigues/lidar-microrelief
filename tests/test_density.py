import numpy as np
import pytest

from microrelief.accumulate import CellStats
from microrelief.density import (
    BASIS_INTERPOLATED,
    BASIS_MEASURED,
    BASIS_UNDETERMINED,
    compute_basis,
    honesty_report,
)


def stats_with(n_all: np.ndarray) -> CellStats:
    z = np.where(n_all > 0, 1.0, np.nan).astype(np.float32)
    zeros = np.zeros_like(n_all, dtype=np.int32)
    return CellStats(z, z, n_all.astype(np.int32), zeros, z, 0)


def test_a_ground_cell_with_enough_returns_is_measured() -> None:
    n_all = np.ones((5, 5), int) * 3
    r = compute_basis(np.ones((5, 5), bool), stats_with(n_all), cell=0.5, k_min_returns=2)
    assert (r.basis == BASIS_MEASURED).all()


def test_a_cell_below_k_is_not_measured_even_though_it_has_returns() -> None:
    n_all = np.ones((5, 5), int) * 3
    n_all[2, 2] = 1
    r = compute_basis(np.ones((5, 5), bool), stats_with(n_all), cell=0.5, k_min_returns=2)
    assert r.basis[2, 2] != BASIS_MEASURED


def test_a_hole_near_measured_cells_is_interpolated_and_names_its_source() -> None:
    n_all = np.ones((9, 9), int) * 3
    is_ground = np.ones((9, 9), bool)
    is_ground[4, 4] = False
    r = compute_basis(is_ground, stats_with(n_all), cell=0.5, d_max_interp_m=2.0)
    assert r.basis[4, 4] == BASIS_INTERPOLATED
    assert (r.source_row[4, 4], r.source_col[4, 4]) != (4, 4)
    assert r.basis[r.source_row[4, 4], r.source_col[4, 4]] == BASIS_MEASURED


def test_a_hole_beyond_d_is_undetermined_never_a_guessed_number() -> None:
    n_all = np.ones((21, 21), int) * 3
    is_ground = np.ones((21, 21), bool)
    is_ground[4:17, 4:17] = False  # 13 cells wide; its centre is 7 cells = 3.5 m from any edge
    r = compute_basis(is_ground, stats_with(n_all), cell=0.5, d_max_interp_m=2.0)
    assert r.basis[10, 10] == BASIS_UNDETERMINED
    assert r.basis[5, 10] == BASIS_INTERPOLATED  # one cell in from the rim


def mixed_fixture() -> tuple[np.ndarray, CellStats]:
    """A grid that exhibits all three states at once, so a contract over them is not vacuous."""
    n_all = np.ones((21, 21), int) * 3
    n_all[0, 0] = 0  # ground, but no returns: fails the k bar rather than the ground test
    is_ground = np.ones((21, 21), bool)
    is_ground[4:17, 4:17] = False
    return is_ground, stats_with(n_all)


def test_the_three_codes_are_a_closed_set_and_this_fixture_shows_all_of_them() -> None:
    is_ground, stats = mixed_fixture()
    r = compute_basis(is_ground, stats, cell=0.5, d_max_interp_m=2.0)
    codes = {BASIS_UNDETERMINED, BASIS_MEASURED, BASIS_INTERPOLATED}
    assert set(np.unique(r.basis)) == codes, "a fourth state would leak into the published band"


def test_each_code_agrees_with_an_independent_measure_of_what_it_claims() -> None:
    """One contract over the whole grid, not one test per state.

    `compute_basis` gets its distances from a distance transform; this re-derives them by brute
    force and asserts the three masks against that. A per-state test would pass while the
    cell-to-metre conversion was wrong; this fails on it.
    """
    cell, d_max, k = 0.5, 2.0, 1
    is_ground, stats = mixed_fixture()
    r = compute_basis(is_ground, stats, cell=cell, k_min_returns=k, d_max_interp_m=d_max)

    measured = is_ground & (stats.n_all >= k)
    rows, cols = np.nonzero(measured)
    all_r, all_c = np.indices(measured.shape)
    dist = (
        np.hypot(
            all_r[..., None] - rows[None, None, :], all_c[..., None] - cols[None, None, :]
        ).min(axis=2)
        * cell
    )

    assert ((r.basis == BASIS_MEASURED) == measured).all()
    assert ((r.basis == BASIS_INTERPOLATED) == (~measured & (dist <= d_max))).all()
    assert ((r.basis == BASIS_UNDETERMINED) == (~measured & (dist > d_max))).all()


def test_every_interpolated_cell_borrows_from_a_measured_cell_within_the_distance() -> None:
    cell, d_max = 0.5, 2.0
    is_ground, stats = mixed_fixture()
    r = compute_basis(is_ground, stats, cell=cell, d_max_interp_m=d_max)

    borrowed = r.basis == BASIS_INTERPOLATED
    assert borrowed.any()
    sr, sc = r.source_row[borrowed], r.source_col[borrowed]
    assert (r.basis[sr, sc] == BASIS_MEASURED).all()
    rows, cols = np.nonzero(borrowed)
    assert (np.hypot(rows - sr, cols - sc) * cell <= d_max).all()


def test_the_honesty_report_puts_the_closed_form_expectation_beside_the_measurement() -> None:
    n_all = np.ones((100, 100), int) * 3
    r = compute_basis(np.ones((100, 100), bool), stats_with(n_all), cell=0.5)
    rep = honesty_report(r.basis, stats_with(n_all), cell=0.5, area_m2=2500.0)
    assert rep.fraction_measured == pytest.approx(1.0)
    assert rep.fraction_undetermined == pytest.approx(0.0)
    assert 0.0 <= rep.expected_void_fraction <= 1.0


def test_the_three_reported_fractions_account_for_every_cell() -> None:
    is_ground, stats = mixed_fixture()
    r = compute_basis(is_ground, stats, cell=0.5, d_max_interp_m=2.0)
    rep = honesty_report(r.basis, stats, cell=0.5, area_m2=2500.0)
    total = rep.fraction_measured + rep.fraction_interpolated + rep.fraction_undetermined
    assert total == pytest.approx(1.0)
    assert rep.fraction_undetermined > 0.0, "the fixture must exercise the undetermined share"
    assert set(rep.as_dict()) == {
        "fraction_measured",
        "fraction_interpolated",
        "fraction_undetermined",
        "measured_density_pts_m2",
        "expected_void_fraction",
    }


def test_a_grid_with_no_measured_cell_at_all_refuses() -> None:
    n_all = np.zeros((5, 5), int)
    with pytest.raises(ValueError, match="no measured cells"):
        compute_basis(np.zeros((5, 5), bool), stats_with(n_all), cell=0.5)

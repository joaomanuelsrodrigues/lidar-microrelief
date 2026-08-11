import math

import pytest

from microrelief.precheck import PrecheckRefusal, check_tiles, expected_void_fraction
from microrelief.providers.dgt import TileRef, select_tiles
from tests.test_selection import AOI, full_cover, tile


def test_void_fraction_is_the_poisson_zero_term() -> None:
    # lambda = density * cell_area * ground_fraction; P(no return) = exp(-lambda).
    assert expected_void_fraction(10.0, 0.5, 1.0) == pytest.approx(math.exp(-2.5))
    assert expected_void_fraction(10.0, 0.5, 1.0) == pytest.approx(0.0821, abs=1e-4)


def test_the_real_dgt_density_makes_open_ground_nearly_solid_but_canopy_still_hollow() -> None:
    # Measured 2026-08-01 from the catalogue: 15.9-21.2 pts/m2, not the ~10 of the specification.
    assert expected_void_fraction(19.4, 0.5, 1.0) < 0.01
    assert expected_void_fraction(19.4, 0.5, 0.10) > 0.60  # closed canopy stays majority-empty


def _nominal_spec_density_tiles() -> list[TileRef]:
    """A 3x3 lattice at 10 pts/m2 -- the density the DGT specification nominally promises.

    At cell 0.5 m and a 40% ground return it yields 36.8% empty cells, 1.8 points above the
    0.35 ceiling. The margin is deliberately narrow: a fixture far past the ceiling is refused
    by a broken comparison just as readily as by a correct one, so it distinguishes nothing.
    """
    return [
        tile(x, y, count=10_000_000)
        for x in (48000.0, 49000.0, 50000.0)
        for y in (169000.0, 170000.0, 171000.0)
    ]


def test_a_sparse_selection_refuses_with_the_number_in_the_message() -> None:
    sel = select_tiles(_nominal_spec_density_tiles(), AOI)
    with pytest.raises(PrecheckRefusal, match="36.8%"):
        check_tiles(sel.tiles, cell=0.5, ground_fraction=0.4, max_void_fraction=0.35)


def test_allow_sparse_is_a_named_exit_not_a_silent_one() -> None:
    sel = select_tiles(_nominal_spec_density_tiles(), AOI)
    estimates = check_tiles(
        sel.tiles, cell=0.5, ground_fraction=0.4, max_void_fraction=0.35, allow_sparse=True
    )
    assert len(estimates) == 9


def test_a_healthy_selection_passes_and_reports_per_tile() -> None:
    sel = select_tiles(full_cover(), AOI)
    estimates = check_tiles(sel.tiles, cell=0.5, ground_fraction=0.4)
    assert len(estimates) == 9
    assert all(e.void_open_ground < 0.01 for e in estimates)

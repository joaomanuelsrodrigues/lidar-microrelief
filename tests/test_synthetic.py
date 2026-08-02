import numpy as np

from tests.synthetic import GROUND, canopy, ramp, sparse, terraced, with_void


def test_ramp_matches_its_own_truth_surface() -> None:
    c = ramp()
    assert np.allclose(c.z, c.truth_surface(c.x, c.y))


def test_terraced_has_flat_treads_and_abrupt_risers() -> None:
    c = terraced(tread=6.0, riser=1.5)
    steps = np.unique(np.round(c.z, 6))
    assert len(steps) > 5
    assert np.allclose(np.diff(steps), 1.5)


def test_canopy_thins_ground_returns_to_about_the_requested_fraction() -> None:
    c = canopy(ground_fraction=0.3)
    assert 0.27 < (c.classification == GROUND).mean() < 0.33


def test_with_void_removes_every_ground_return_inside_the_square() -> None:
    c = with_void(ramp(), 48010.0, 169010.0, 5.0)
    inside = (c.x >= 48010) & (c.x < 48015) & (c.y >= 169010) & (c.y < 169015)
    assert not (inside & (c.classification == GROUND)).any()


def test_sparse_is_below_one_return_per_half_metre_cell() -> None:
    c = sparse(density=0.5)
    assert c.x.size / (50.0 * 50.0) < 1.0

import numpy as np
import pytest

from microrelief.accumulate import CellStats
from microrelief.ground import agreement


def stats(n_all, n_ground):
    z = np.zeros_like(n_all, dtype=np.float32)
    return CellStats(z, z, n_all.astype(np.int32), n_ground.astype(np.int32), z, 0)


def test_perfect_agreement_still_reports_the_null_beside_it() -> None:
    n_all = np.ones((10, 10), int) * 5
    n_ground = np.zeros((10, 10), int)
    n_ground[:9] = 3  # 90% of cells are officially ground
    a = agreement(n_ground > 0, stats(n_all, n_ground))
    assert a.accuracy == pytest.approx(1.0)
    assert a.majority_class_null == pytest.approx(0.9)
    assert a.recall_ground == pytest.approx(1.0)
    assert a.recall_nonground == pytest.approx(1.0)


def test_a_classifier_that_says_ground_everywhere_is_exposed_by_the_null() -> None:
    n_all = np.ones((10, 10), int) * 5
    n_ground = np.zeros((10, 10), int)
    n_ground[:9] = 3
    a = agreement(np.ones((10, 10), bool), stats(n_all, n_ground))
    assert a.accuracy == pytest.approx(0.9)
    assert a.accuracy == pytest.approx(a.majority_class_null)  # it beat nothing
    assert a.recall_nonground == pytest.approx(0.0)


def test_empty_cells_are_excluded_because_neither_classifier_saw_anything() -> None:
    n_all = np.zeros((10, 10), int)
    n_all[:5] = 4
    n_ground = np.zeros((10, 10), int)
    n_ground[:5] = 2
    a = agreement(n_ground > 0, stats(n_all, n_ground))
    assert a.n_cells == 50


def test_no_measured_cells_refuses_rather_than_dividing_by_zero() -> None:
    z = np.zeros((4, 4), int)
    with pytest.raises(ValueError, match="no measured cells"):
        agreement(np.zeros((4, 4), bool), stats(z, z))

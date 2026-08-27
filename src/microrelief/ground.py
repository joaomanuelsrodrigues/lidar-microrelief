"""Deriving ground from the minimum surface.

A progressive morphological filter (Zhang et al. 2003, IEEE TGRS 41(4)): open the minimum surface
with windows of growing size and mark as object any cell that the opening pushes down further than
a slope-dependent tolerance allows.

This is deliberately *not* the published DGT classification. Inheriting it would leave the hard
step to someone else; deriving it makes the comparison in `agreement()` a result rather than a
tautology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt, grey_opening

from microrelief.accumulate import CellStats


class GroundError(RuntimeError):
    """There is nothing here to classify."""


@dataclass(frozen=True)
class GroundParams:
    max_window_m: float
    slope_threshold: float
    elevation_threshold_m: float
    max_elevation_m: float


def _fill_nearest(z: NDArray[np.float32], invalid: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Fill empty cells with their nearest measured neighbour, so the opening has no holes.

    This fill exists only so the morphology is well defined. It never reaches an output: the
    basis codes in `density.py` decide what a cell is allowed to publish.
    """
    indices = distance_transform_edt(invalid, return_distances=False, return_indices=True)
    filled: NDArray[np.float64] = np.asarray(z, dtype=np.float64)[tuple(indices)]
    return filled


def _radii(max_window_m: float, cell: float) -> list[int]:
    max_radius = max(1, int(round(max_window_m / cell / 2)))
    radii, radius = [], 1
    while radius <= max_radius:
        radii.append(radius)
        radius *= 2
    return radii


def windows_for(max_window_m: float, cell: float) -> tuple[float, ...]:
    """The window widths the filter will actually use, in metres.

    The radius doubles, so `max_window_m` is a ceiling on the radius search and not a width that
    is ever used. At 0.5 m cells `max_window_m=24` yields (1.5, 2.5, 4.5, 8.5, 16.5) -- never 24 --
    and `max_window_m=4` and `max_window_m=6` yield exactly the same schedule.

    Exposed rather than left implicit in the loop because comparing "the window" to a terrace
    tread means comparing these numbers to it, not the parameter. Reasoning about the parameter
    instead produced a test that claimed a 24 m window against a 6 m tread and was in fact
    running a 16.5 m one (2026-08-03).
    """
    return tuple((2 * radius + 1) * cell for radius in _radii(max_window_m, cell))


def classify_ground(
    min_z: NDArray[np.float32], cell: float, params: GroundParams
) -> NDArray[np.bool_]:
    """Mark as object every cell the opening pushes down further than the tolerance allows.

    What decides whether a terrace riser survives is `max_elevation_m` against the riser height,
    not `max_window_m` against the tread: the cap is the ceiling on every tolerance, so a riser
    is excused exactly when the cap exceeds it, at any window (measured 2026-08-03 -- see
    `CALIBRATIONS.md` and `tests/test_ground.py`).
    """
    invalid = np.isnan(min_z)
    if invalid.all():
        raise GroundError("no measured cells: every cell of the minimum surface is empty")

    surface = _fill_nearest(min_z, invalid)
    is_object = np.zeros(min_z.shape, dtype=bool)

    for radius in _radii(params.max_window_m, cell):
        size = 2 * radius + 1
        opened = grey_opening(surface, size=(size, size), mode="nearest")
        window_m = size * cell
        tolerance = min(
            params.slope_threshold * window_m + params.elevation_threshold_m,
            params.max_elevation_m,
        )
        is_object |= (surface - opened) > tolerance
        surface = opened

    return ~is_object & ~invalid


@dataclass(frozen=True)
class Agreement:
    n_cells: int
    tp: int
    fp: int
    fn: int
    tn: int
    recall_ground: float
    recall_nonground: float
    accuracy: float
    majority_class_null: float
    ground_prevalence: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "n_cells": self.n_cells,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "recall_ground": self.recall_ground,
            "recall_nonground": self.recall_nonground,
            "accuracy": self.accuracy,
            "majority_class_null": self.majority_class_null,
            "ground_prevalence": self.ground_prevalence,
        }


def agreement(is_ground: NDArray[np.bool_], stats: CellStats) -> Agreement:
    """Compare our per-cell ground decision with the official ASPRS classification.

    The aim is not to beat the DGT: it is to quantify and explain the difference. Large
    disagreement under canopy is a result as long as it is declared. Catastrophic disagreement on
    open ground (recall below ~0.70) is a defect in our filter — that is the internal falsification
    criterion for this pipeline.
    """
    measured = stats.n_all > 0
    if not measured.any():
        raise ValueError("no measured cells to compare")

    ours = is_ground[measured]
    official = (stats.n_ground_asprs > 0)[measured]

    tp = int((ours & official).sum())
    fp = int((ours & ~official).sum())
    fn = int((~ours & official).sum())
    tn = int((~ours & ~official).sum())
    n = tp + fp + fn + tn

    prevalence = (tp + fn) / n
    return Agreement(
        n_cells=n,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        recall_ground=tp / (tp + fn) if (tp + fn) else float("nan"),
        recall_nonground=tn / (tn + fp) if (tn + fp) else float("nan"),
        accuracy=(tp + tn) / n,
        majority_class_null=max(prevalence, 1.0 - prevalence),
        ground_prevalence=prevalence,
    )

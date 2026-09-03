"""What each cell of the terrain model is made of.

Three states, not two. A cell that has no ground evidence and no measured neighbour close enough
to borrow from is not given a plausible number: it is left as NoData and counted. The most
shareable image this piece produces is the one showing what it refuses to claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

from microrelief.accumulate import CellStats
from microrelief.precheck import expected_void_fraction

BASIS_UNDETERMINED = 0
BASIS_MEASURED = 1
BASIS_INTERPOLATED = 2


@dataclass(frozen=True, eq=False)
class BasisResult:
    """Per cell: what its value is made of, and which cell it came from.

    `source_row`/`source_col` are meaningful for every cell, but only binding where the basis is
    `BASIS_INTERPOLATED`: for a measured cell they point at itself, and for an undetermined one
    they point at a cell too far away to borrow from, which is precisely why nothing is borrowed.
    """

    basis: NDArray[np.uint8]
    source_row: NDArray[np.int64]
    source_col: NDArray[np.int64]


@dataclass(frozen=True)
class HonestyReport:
    fraction_measured: float
    fraction_interpolated: float
    fraction_undetermined: float
    measured_density: float
    expected_void_fraction: float

    def as_dict(self) -> dict[str, float]:
        return {
            "fraction_measured": self.fraction_measured,
            "fraction_interpolated": self.fraction_interpolated,
            "fraction_undetermined": self.fraction_undetermined,
            "measured_density_pts_m2": self.measured_density,
            "expected_void_fraction": self.expected_void_fraction,
        }


def compute_basis(
    is_ground: NDArray[np.bool_],
    stats: CellStats,
    cell: float,
    k_min_returns: int = 1,
    d_max_interp_m: float = 2.0,
) -> BasisResult:
    """Assign one of three basis codes to every cell.

    A cell is measured when our filter called it ground *and* it holds at least `k_min_returns`
    returns; the two conditions are separate and a cell can fail either one. Everything else is
    a hole, and a hole is interpolated only while a measured cell lies within `d_max_interp_m`.
    Beyond that the cell stays undetermined: NoData, counted, never a plausible-looking number.
    """
    # Both are lengths in metres and both reach arithmetic that does not refuse them.
    # Measured on the shipped sample: `--d-max-interp-m nan` published
    # `measured 51.6% | interpolated 0.0% | undetermined 48.4%` at exit 0 against the true
    # 51.6/42.3/6.1, because `distances * cell <= nan` is False everywhere; `inf` inverted it,
    # turning every hole into `interpolated` and erasing `undetermined`, which is the one class
    # this band exists to publish. The record then carried a bare `NaN` token -- accepted by
    # Python's lenient reader, rejected by any RFC 8259 parser.
    if not math.isfinite(cell) or cell <= 0:
        raise ValueError(f"cell must be a positive, finite length in metres, got {cell}")
    # Zero is ADMISSIBLE here and the guard's first version wrongly bundled it with nonsense.
    # `d_max_interp_m = 0` means "borrow from nothing": `distances * cell <= 0` holds only where
    # the distance is zero, i.e. at cells already measured, so the band comes out measured plus
    # undetermined with no interpolated cell at all. That is the most conservative honest setting
    # this flag can express, not an error.
    if not math.isfinite(d_max_interp_m) or d_max_interp_m < 0:
        raise ValueError(
            f"d_max_interp_m must be a non-negative, finite length in metres, got {d_max_interp_m}"
        )

    measured = is_ground & (stats.n_all >= k_min_returns)
    if not measured.any():
        raise ValueError("no measured cells: nothing to interpolate from")

    distances, indices = distance_transform_edt(
        ~measured, return_distances=True, return_indices=True
    )
    within = (np.asarray(distances, dtype=np.float64) * cell) <= d_max_interp_m

    basis = np.full(measured.shape, BASIS_UNDETERMINED, dtype=np.uint8)
    basis[~measured & within] = BASIS_INTERPOLATED
    basis[measured] = BASIS_MEASURED

    idx = np.asarray(indices, dtype=np.int64)
    return BasisResult(basis=basis, source_row=idx[0], source_col=idx[1])


def honesty_report(
    basis: NDArray[np.uint8], stats: CellStats, cell: float, area_m2: float
) -> HonestyReport:
    n = basis.size
    density = float(stats.n_all.sum()) / area_m2
    # Compared against the closed form at f = 1: the share of cells a Poisson process of this
    # density would leave empty. Divergence between the two is itself the finding.
    return HonestyReport(
        fraction_measured=float((basis == BASIS_MEASURED).sum()) / n,
        fraction_interpolated=float((basis == BASIS_INTERPOLATED).sum()) / n,
        fraction_undetermined=float((basis == BASIS_UNDETERMINED).sum()) / n,
        measured_density=density,
        expected_void_fraction=expected_void_fraction(density, cell, 1.0) if density > 0 else 1.0,
    )

"""What each cell of the terrain model is made of.

Three states, not two. A cell that has no ground evidence and no measured neighbour close enough
to borrow from is not given a plausible number: it is left as NoData and counted. The most
shareable image this piece produces is the one showing what it refuses to claim.
"""

from __future__ import annotations

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

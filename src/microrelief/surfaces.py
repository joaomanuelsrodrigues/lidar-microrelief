"""The three surfaces, built from the basis rather than beside it."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from microrelief.accumulate import CellStats
from microrelief.density import BASIS_INTERPOLATED, BASIS_MEASURED, BasisResult
from microrelief.grid import Grid


@dataclass(frozen=True, eq=False)
class Surfaces:
    grid: Grid
    mdt: NDArray[np.float32]
    mds: NDArray[np.float32]
    chm: NDArray[np.float32]
    basis: NDArray[np.uint8]
    n_all: NDArray[np.int32]
    n_ground_asprs: NDArray[np.int32]

    def rasters(self) -> dict[str, NDArray[np.generic]]:
        """Every band that leaves this package. Export iterates this, so nothing ships unlisted."""
        return {
            "mdt": self.mdt,
            "mds": self.mds,
            "chm": self.chm,
            "basis": self.basis,
            "n_all": self.n_all,
            "n_ground_asprs": self.n_ground_asprs,
        }


def build_surfaces(grid: Grid, stats: CellStats, basis_result: BasisResult) -> Surfaces:
    """Assemble the published bands, each one keyed off the basis it is entitled to.

    The DTM takes a measured minimum where there is one and borrows its nearest measured
    neighbour's where the basis says it may; nowhere else does it carry a number. The CHM is
    stricter still: it exists only where the ground under that exact cell was seen, because a
    canopy height computed against borrowed ground is a difference between a measurement and
    somewhere else.
    """
    basis = basis_result.basis

    mdt = np.full(grid.shape, np.nan, dtype=np.float32)
    measured = basis == BASIS_MEASURED
    mdt[measured] = stats.min_z_all[measured]

    borrowed = basis == BASIS_INTERPOLATED
    if borrowed.any():
        # Nearest measured cell, deterministically. No smoothing: an interpolated value is a
        # borrowed measurement, and the band says so.
        mdt[borrowed] = stats.min_z_all[
            basis_result.source_row[borrowed], basis_result.source_col[borrowed]
        ]

    mds = np.where(stats.n_all > 0, stats.max_z_all, np.nan).astype(np.float32)

    chm = np.full(grid.shape, np.nan, dtype=np.float32)
    both = measured & np.isfinite(mds)
    chm[both] = mds[both] - mdt[both]

    return Surfaces(
        grid=grid,
        mdt=mdt,
        mds=mds,
        chm=chm,
        basis=basis,
        n_all=stats.n_all,
        n_ground_asprs=stats.n_ground_asprs,
    )

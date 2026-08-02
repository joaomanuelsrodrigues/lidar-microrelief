"""Stream points into the one grid, then discard them.

The grid is what accumulates: allocated once, sized to the AOI (not to how many tiles get
poured into it). Measured via `.nbytes`, not estimated: at 0.5 m, 4 km2 is 16M cells, so the
accumulator's five internal float64/int64 arrays (8 bytes/cell) total 0.64 GB, and the five
published float32/int32 arrays in `CellStats` (4 bytes/cell) total 0.32 GB -- that 0.32 GB is
the sum across all five arrays, not the size of any one of them.

That grid figure is fixed for the whole run, but it is not the peak. Peak memory happens once
per `add()` call and is dominated by that tile's points, not by the grid. Measured with
`resource.getrusage` around `read_laz()` + `add()` for one synthetic ~21M-point tile poured
into this same 4 km2 grid: peak RSS reached ~2.8 GB, most of it `read_laz()` materialising the
tile's x/y/z/classification arrays and `add()`'s own per-point temporaries (row/col/inside, the
sorted copies behind `_grouped_extrema`) -- the grid's 0.64 GB was a minority of that peak. A
large enough single tile can push point memory past the grid's footprint well before AOI size
does, so sizing for the largest tile matters as much as sizing for the AOI.

What genuinely never happens is two tiles' points coexisting: `add()` returns having copied
nothing of the batch into `self`, so only the grid's aggregates survive from one tile to the
next.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from microrelief.grid import Grid
from microrelief.read import ASPRS_GROUND, PointBatch


class AccumulateError(ValueError):
    """A batch was refused before any point of it was touched.

    Subclasses ValueError so existing `except ValueError` callers keep working unchanged, but
    lets a caller narrow its catch to accumulator-declared refusals -- distinguishing them from
    a genuine array bug (mismatched-length arrays, wrong dtype) that also raises a bare
    ValueError from inside the same `add()` call and should not be silently swallowed.
    """


@dataclass(frozen=True, eq=False)
class CellStats:
    min_z_all: NDArray[np.float32]
    max_z_all: NDArray[np.float32]
    n_all: NDArray[np.int32]
    n_ground_asprs: NDArray[np.int32]
    min_z_ground_asprs: NDArray[np.float32]
    n_outside: int


def _grouped_extrema(
    flat_idx: NDArray[np.int64], z: NDArray[np.float64]
) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
    """Per-cell min, max and count in one sort.

    `np.minimum.at` is correct but far too slow here.
    """
    order = np.argsort(flat_idx, kind="stable")
    idx_sorted = flat_idx[order]
    z_sorted = z[order]
    starts = np.flatnonzero(np.concatenate(([True], idx_sorted[1:] != idx_sorted[:-1])))
    cells = idx_sorted[starts]
    mins = np.minimum.reduceat(z_sorted, starts)
    maxs = np.maximum.reduceat(z_sorted, starts)
    counts = np.diff(np.concatenate((starts, [idx_sorted.size])))
    return cells, mins, maxs, counts


class Accumulator:
    """Folds tiles into one grid's worth of per-cell statistics; never holds a tile's points.

    `add()` is called once per tile and returns having copied nothing of the batch's arrays
    into `self` -- only per-cell aggregates (indexed by grid cell, not by point) survive. That
    is what makes tile order irrelevant and a mosaic step unnecessary: there is no per-tile
    window left anywhere to disagree with another one.
    """

    def __init__(self, grid: Grid) -> None:
        self.grid = grid
        n = grid.n_cells
        self._min_all = np.full(n, np.inf, dtype=np.float64)
        self._max_all = np.full(n, -np.inf, dtype=np.float64)
        self._n_all = np.zeros(n, dtype=np.int64)
        self._min_ground = np.full(n, np.inf, dtype=np.float64)
        self._n_ground = np.zeros(n, dtype=np.int64)
        self._n_outside = 0

    def add(self, batch: PointBatch) -> None:
        if batch.crs_epsg != self.grid.crs_epsg:
            raise AccumulateError(
                f"batch is EPSG:{batch.crs_epsg}, grid is EPSG:{self.grid.crs_epsg}"
            )
        row, col, inside = self.grid.cell_indices(batch.x, batch.y)
        self._n_outside += int((~inside).sum())
        if not inside.any():
            return
        flat = row[inside] * self.grid.n_cols + col[inside]
        z = batch.z[inside]

        cells, mins, maxs, counts = _grouped_extrema(flat, z)
        self._min_all[cells] = np.minimum(self._min_all[cells], mins)
        self._max_all[cells] = np.maximum(self._max_all[cells], maxs)
        self._n_all[cells] += counts

        g = batch.classification[inside] == ASPRS_GROUND
        if g.any():
            gcells, gmins, _gmax, gcounts = _grouped_extrema(flat[g], z[g])
            self._min_ground[gcells] = np.minimum(self._min_ground[gcells], gmins)
            self._n_ground[gcells] += gcounts

    def finish(self) -> CellStats:
        shape = self.grid.shape

        def to_grid(values: NDArray[np.float64], empty: NDArray[np.bool_]) -> NDArray[np.float32]:
            out = values.astype(np.float32)
            out[empty] = np.nan  # zero is a plausible elevation; NaN is not a measurement
            return out.reshape(shape)

        return CellStats(
            min_z_all=to_grid(self._min_all, self._n_all == 0),
            max_z_all=to_grid(self._max_all, self._n_all == 0),
            n_all=self._n_all.astype(np.int32).reshape(shape),
            n_ground_asprs=self._n_ground.astype(np.int32).reshape(shape),
            min_z_ground_asprs=to_grid(self._min_ground, self._n_ground == 0),
            n_outside=self._n_outside,
        )

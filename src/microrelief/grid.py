"""The single common grid for one AOI.

Every raster this package produces shares one instance of `Grid`. That is the structural
reason no elementwise arithmetic can ever happen between per-tile windows: there are no
per-tile windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from affine import Affine
from numpy.typing import NDArray


class GridError(ValueError):
    """The requested grid is not one we are willing to build."""


@dataclass(frozen=True)
class Grid:
    origin_x: float  # left edge (min easting)
    origin_y: float  # top edge (max northing)
    cell: float
    n_cols: int
    n_rows: int
    crs_epsg: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.n_rows, self.n_cols)

    @property
    def n_cells(self) -> int:
        return self.n_rows * self.n_cols

    @property
    def transform(self) -> Affine:
        return Affine(self.cell, 0.0, self.origin_x, 0.0, -self.cell, self.origin_y)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.origin_x,
            self.origin_y - self.n_rows * self.cell,
            self.origin_x + self.n_cols * self.cell,
            self.origin_y,
        )

    def cell_indices(
        self, x: NDArray[np.float64], y: NDArray[np.float64]
    ) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.bool_]]:
        """Map coordinates to (row, col), flagging what falls outside instead of clipping it.

        Clipping would silently pile every out-of-AOI point onto the border cells.
        """
        col = np.floor((x - self.origin_x) / self.cell).astype(np.int64)
        row = np.floor((self.origin_y - y) / self.cell).astype(np.int64)
        inside = (col >= 0) & (col < self.n_cols) & (row >= 0) & (row < self.n_rows)
        return row, col, inside


def grid_for_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    cell: float,
    crs_epsg: int,
    max_cells: int = 200_000_000,
) -> Grid:
    if cell <= 0:
        raise GridError(f"cell must be positive, got {cell}")
    if maxx <= minx or maxy <= miny:
        raise GridError(f"empty extent: ({minx}, {miny}) to ({maxx}, {maxy})")

    origin_x = math.floor(minx / cell) * cell
    origin_y = math.ceil(maxy / cell) * cell
    n_cols = int(math.ceil((maxx - origin_x) / cell))
    n_rows = int(math.ceil((origin_y - miny) / cell))
    n_cells = n_cols * n_rows
    if n_cells > max_cells:
        raise GridError(
            f"grid would hold {n_cells} cells, ceiling is {max_cells}; "
            f"raise --cell or shrink the AOI"
        )
    return Grid(origin_x, origin_y, cell, n_cols, n_rows, crs_epsg)

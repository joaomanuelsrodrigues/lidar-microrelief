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

from microrelief.crs import require_metric_crs


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

    def __post_init__(self) -> None:
        # On Grid rather than only on `grid_for_bounds`: this is the single object every
        # metric path in the package shares, and a caller that constructs one directly
        # must not get a different answer from one that goes through the helper.
        require_metric_crs(self.crs_epsg)

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


BYTES_PER_CELL = 60
"""What one cell of the grid costs, measured rather than estimated.

The accumulator holds five float64/int64 arrays (40 B/cell) and `CellStats` five float32/int32
ones (20 B/cell). The ceiling below counts *cells*, because that is what `grid_for_bounds`
knows; this constant is what those cells cost, so the refusal can say it in the unit the caller
runs out of. It is a **floor** on the run's memory, not a bound: the ground filter, the two
distance transforms and the surfaces are all on top, and a single large tile's points can
exceed the grid entirely (`accumulate.py`). A grid under the ceiling can still be OOM-killed --
declared in `LIMITATIONS`, not defended against.
"""


def grid_for_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    cell: float,
    crs_epsg: int,
    max_cells: int = 200_000_000,
    block: int = 1,
) -> Grid:
    """The grid one AOI is worked on, snapped outward to whole cells and to whole blocks.

    `block` is the analysis block size in cells, for a stage that works on a coarser grid built
    by reducing blocks of these cells (the ground filter does). Left at 1 it changes nothing.
    Above 1 the grid grows by at most `block - 1` cells per axis, because a stage that tiles the
    grid in blocks cannot be handed a grid that is not whole blocks -- and the alternative,
    refusing, would refuse a large share of real AOIs, since `n_cols` and `n_rows` are `ceil()`
    of an arbitrary extent and their parity is unconstrained.

    What the added cells publish is **not** a general guarantee. Membership is decided by
    `cell_indices` against the *grid*, not against the requested AOI, so a fringe cell that
    falls inside a source tile accumulates real returns and publishes what was measured there;
    only a fringe cell outside every tile publishes as `undetermined`. The grid already extends
    past the AOI by up to one cell for the same reason -- the snap widens an existing edge, it
    does not create one.
    """
    # `math.isfinite` leads: `float("nan") <= 0` is False, so a NaN cell walked through a bare
    # positivity test and died in `math.floor(minx / nan)` with "cannot convert float NaN to
    # integer". Same hole, same shape, in all three places this package takes a length.
    if not math.isfinite(cell) or cell <= 0:
        raise GridError(f"cell must be a positive, finite length in metres, got {cell}")
    if block < 1:
        raise GridError(f"block must be at least one cell, got {block}")
    if maxx <= minx or maxy <= miny:
        raise GridError(f"empty extent: ({minx}, {miny}) to ({maxx}, {maxy})")

    origin_x = math.floor(minx / cell) * cell
    origin_y = math.ceil(maxy / cell) * cell
    n_cols = int(math.ceil((maxx - origin_x) / cell))
    n_rows = int(math.ceil((origin_y - miny) / cell))
    # After the snap, never before: the snap can only grow the grid, so a ceiling checked
    # first is a ceiling the run can cross.
    n_cols = int(math.ceil(n_cols / block)) * block
    n_rows = int(math.ceil(n_rows / block)) * block
    n_cells = n_cols * n_rows
    if n_cells > max_cells:
        raise GridError(
            f"grid would hold {n_cells} cells, ceiling is {max_cells} "
            f"(~{n_cells * BYTES_PER_CELL / 1e9:.1f} GB of per-cell arrays alone); "
            f"raise --cell or shrink the AOI"
        )
    return Grid(origin_x, origin_y, cell, n_cols, n_rows, crs_epsg)

"""Whether a DTM at this cell size can be measured rather than invented.

Treats returns landing in a cell as a Poisson process of rate density x cell_area x
ground_fraction, so the share of cells with no return at all is exp(-lambda) in closed form.
Predicted 8.209% against 8.203% measured over 4M cells (s250), so the form is trustworthy;
`ground_fraction` under a specific canopy is not -- see the disclosure in `estimate_tiles`.

Because `pc:count` is published without authentication, this runs on any tile in the country
before a single byte is downloaded.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from microrelief.tiles import Selection, TileRef


class PrecheckRefusal(RuntimeError):
    """The data cannot support the product asked for, and we say so with the number."""


@dataclass(frozen=True)
class TileEstimate:
    item_id: str
    density: float
    flight_date: str
    void_open_ground: float
    void_at_f: float


def expected_void_fraction(density_pts_m2: float, cell: float, ground_fraction: float) -> float:
    """Share of cells expected to hold zero ground returns."""
    if density_pts_m2 <= 0 or cell <= 0:
        raise ValueError("density and cell must be positive")
    if not 0.0 < ground_fraction <= 1.0:
        raise ValueError("ground_fraction must be in (0, 1]")
    lam = density_pts_m2 * cell * cell * ground_fraction
    return math.exp(-lam)


def estimate_tiles(
    tiles: Sequence[TileRef], cell: float, ground_fraction: float
) -> list[TileEstimate]:
    """Per-tile expectation.

    `ground_fraction` is illustrative of the shape of the dependence, not measured: the share of
    returns reaching the ground under a particular canopy is an empirical property of that stand
    and that sensor. Treat the ordering across tiles as informative and the absolute value as a
    reference model.
    """
    return [
        TileEstimate(
            item_id=t.item_id,
            density=t.density,
            flight_date=t.flight_date,
            void_open_ground=expected_void_fraction(t.density, cell, 1.0),
            void_at_f=expected_void_fraction(t.density, cell, ground_fraction),
        )
        for t in tiles
    ]


def check_selection(
    selection: Selection,
    cell: float,
    ground_fraction: float,
    max_void_fraction: float = 0.35,
    allow_sparse: bool = False,
) -> list[TileEstimate]:
    estimates = estimate_tiles(selection.tiles, cell, ground_fraction)
    worst = max(estimates, key=lambda e: e.void_at_f)
    if worst.void_at_f > max_void_fraction and not allow_sparse:
        raise PrecheckRefusal(
            f"tile {worst.item_id} has {worst.density:.1f} pts/m2; at cell {cell} m and "
            f"ground fraction {ground_fraction}, {worst.void_at_f:.1%} of cells are expected to "
            f"hold no ground return (ceiling {max_void_fraction:.0%}). The DTM would be mostly "
            f"interpolated by construction. Use a coarser --cell, or pass --allow-sparse to "
            f"accept and declare it."
        )
    return estimates

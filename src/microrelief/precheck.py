"""Whether a DTM at this cell size can be measured rather than invented.

Treats returns landing in a cell as a Poisson process of rate density x cell_area x
ground_fraction, so the share of cells with no return at all is exp(-lambda) in closed form.
Predicted 8.209% against 8.203% measured over 4M cells (2026-07-30), so the form is trustworthy;
`ground_fraction` under a specific canopy is not -- see the disclosure in `estimate_tiles`.

Because `pc:count` is published without authentication, this runs on any tile in the country
before a single byte is downloaded.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class TileLike(Protocol):
    """What the void expectation needs to know about a tile, and nothing else.

    Structural, not nominal: the DGT `TileRef` satisfies it without core naming that type, so
    the honesty layer stops depending on one catalogue's data class to do arithmetic that has
    nothing to do with catalogues.
    """

    @property
    def item_id(self) -> str: ...

    @property
    def density(self) -> float: ...

    @property
    def flight_date(self) -> str: ...


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
    # Finiteness first, and not only for tidiness: `--cell` is a user flag on `precheck`, which
    # never calls `block_factor`, so this is the one length check on that path. `nan` slipped
    # through (`nan <= 0` is False), made `lam` NaN, and `nan > max_void_fraction` is False --
    # so `check_tiles` skipped its refusal and the command printed `void(f=0.4)=nan%` at exit 0.
    # `inf` was worse: `exp(-inf)` is 0.0, a confident "no voids expected" for an infinite cell.
    if (
        not math.isfinite(density_pts_m2)
        or not math.isfinite(cell)
        or density_pts_m2 <= 0
        or cell <= 0
    ):
        raise ValueError(
            f"density and cell must be positive, finite numbers, got {density_pts_m2} and {cell}"
        )
    if not 0.0 < ground_fraction <= 1.0:
        raise ValueError("ground_fraction must be in (0, 1]")
    lam = density_pts_m2 * cell * cell * ground_fraction
    return math.exp(-lam)


def estimate_tiles(
    tiles: Sequence[TileLike], cell: float, ground_fraction: float
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


def check_tiles(
    tiles: Sequence[TileLike],
    cell: float,
    ground_fraction: float,
    max_void_fraction: float = 0.35,
    allow_sparse: bool = False,
) -> list[TileEstimate]:
    estimates = estimate_tiles(tiles, cell, ground_fraction)
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

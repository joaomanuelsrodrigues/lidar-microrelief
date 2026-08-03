"""Point clouds whose ground surface is known by construction.

Real tiles have no ground truth: the official classification is another estimate. These fixtures
are where "the filter recovered the surface" can mean something exact.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
from numpy.typing import NDArray
from pyproj import CRS

GROUND = 2
VEGETATION = 5
ORIGIN_X, ORIGIN_Y = 48000.0, 169000.0  # inside the DGT lattice, so fixtures look like real data


@dataclass(frozen=True, eq=False)
class Cloud:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    z: NDArray[np.float64]
    classification: NDArray[np.uint8]
    truth_surface: Callable[[NDArray[np.float64], NDArray[np.float64]], NDArray[np.float64]]


def _lattice(size_m: float, spacing: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    n = int(size_m / spacing)
    gx, gy = np.meshgrid(
        ORIGIN_X + np.arange(n) * spacing,
        ORIGIN_Y + np.arange(n) * spacing,
        indexing="xy",
    )
    return gx.ravel(), gy.ravel()


def ramp(size_m: float = 50.0, spacing: float = 0.2, slope: float = 0.1) -> Cloud:
    x, y = _lattice(size_m, spacing)

    def surface(px: NDArray[np.float64], py: NDArray[np.float64]) -> NDArray[np.float64]:
        return slope * (px - ORIGIN_X)

    return Cloud(x, y, surface(x, y), np.full(x.size, GROUND, np.uint8), surface)


def terraced(
    size_m: float = 50.0, spacing: float = 0.2, tread: float = 6.0, riser: float = 1.5
) -> Cloud:
    """A staircase: flat treads separated by abrupt vertical risers.

    This is the worst case for a morphological filter and the exact feature the piece exists to
    show, which is why it is the acid test rather than one fixture among five.
    """
    x, y = _lattice(size_m, spacing)

    def surface(px: NDArray[np.float64], py: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.floor((px - ORIGIN_X) / tread) * riser

    return Cloud(x, y, surface(x, y), np.full(x.size, GROUND, np.uint8), surface)


def hillside(
    size_m: float = 50.0, spacing: float = 0.2, tread: float = 6.0, riser: float = 1.5
) -> Cloud:
    """Terraces climbing to a crest and back down: a hill, not an endless staircase.

    `terraced` is monotone, and a morphological opening removes only local maxima -- so no window
    of any size can damage it (measured s256: ground fraction is exactly 1.0000 at 1 m, 4 m and
    24 m windows against a 6 m tread). It therefore cannot demonstrate the failure it was written
    to demonstrate. A crest gives the opening something to bite on, which is what makes the pair
    "terraces survive" / "terraces are destroyed" discriminate rather than both pass by default.
    """
    x, y = _lattice(size_m, spacing)
    crest = ORIGIN_X + size_m / 2

    def surface(px: NDArray[np.float64], py: NDArray[np.float64]) -> NDArray[np.float64]:
        return -np.floor(np.abs(px - crest) / tread) * riser

    return Cloud(x, y, surface(x, y), np.full(x.size, GROUND, np.uint8), surface)


def canopy(
    size_m: float = 50.0,
    spacing: float = 0.2,
    tree_height: float = 8.0,
    ground_fraction: float = 0.3,
    seed: int = 0,
) -> Cloud:
    """Ground returns thinned to `ground_fraction`, the rest lifted into a canopy layer."""
    base = ramp(size_m, spacing, slope=0.02)
    rng = np.random.default_rng(seed)
    reaches_ground = rng.random(base.x.size) < ground_fraction
    z = np.where(reaches_ground, base.z, base.z + tree_height + rng.normal(0, 0.5, base.x.size))
    cls = np.where(reaches_ground, GROUND, VEGETATION).astype(np.uint8)
    return Cloud(base.x, base.y, z, cls, base.truth_surface)


def with_void(cloud: Cloud, x0: float, y0: float, size: float) -> Cloud:
    """Delete every ground return inside a square, leaving a hole with no ground evidence.

    The y bound is closed on the top and open on the bottom (`y0 < y <= y0 + size`), the
    opposite of x's `x0 <= x < x0 + size` -- not the "intuitive" symmetric reading. This is
    `grid.py`'s own convention (row = `(top - cell, top]`, top-closed, y-down), and matching it
    is what makes a void of `size` empty exactly `size / cell` grid rows: getting it backwards
    leaves one boundary lattice line alive, so the void reads as one row short and the surviving
    row looks sparsely measured instead of empty.
    """
    inside = (cloud.x >= x0) & (cloud.x < x0 + size) & (cloud.y > y0) & (cloud.y <= y0 + size)
    keep = ~(inside & (cloud.classification == GROUND))
    return Cloud(
        cloud.x[keep], cloud.y[keep], cloud.z[keep], cloud.classification[keep], cloud.truth_surface
    )


def sparse(size_m: float = 50.0, density: float = 0.5, seed: int = 0) -> Cloud:
    """Density far below one return per cell, so most cells cannot be measured at all."""
    rng = np.random.default_rng(seed)
    n = int(size_m * size_m * density)
    x = ORIGIN_X + rng.random(n) * size_m
    y = ORIGIN_Y + rng.random(n) * size_m

    def surface(px: NDArray[np.float64], py: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.zeros_like(px)

    return Cloud(x, y, surface(x, y), np.full(n, GROUND, np.uint8), surface)


def write_las(
    path: Path,
    n: int = 1000,
    epsg: int | None = 3763,
    classification: int = GROUND,
    cloud: Cloud | None = None,
) -> None:
    if cloud is None:
        rng = np.random.default_rng(0)
        x = ORIGIN_X + rng.random(n) * 100.0
        y = ORIGIN_Y + rng.random(n) * 100.0
        z = rng.random(n) * 10.0
        cls = np.full(n, classification, np.uint8)
    else:
        x, y, z, cls = cloud.x, cloud.y, cloud.z, cloud.classification

    header = laspy.LasHeader(version="1.4", point_format=6)
    header.scales = np.array([0.01, 0.01, 0.01])
    header.offsets = np.array([np.floor(x.min()), np.floor(y.min()), np.floor(z.min())])
    if epsg is not None:
        header.add_crs(CRS.from_epsg(epsg))
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = cls
    las.write(path)

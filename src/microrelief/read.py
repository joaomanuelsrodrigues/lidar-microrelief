"""Reading a LAZ tile, and refusing the ones we cannot honestly use."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
from numpy.typing import NDArray

ASPRS_GROUND = 2

ASPRS_NOISE = (7, 18)
"""Low Point (noise) and High Noise.

Not a precaution: measured on the four Sistelo tiles, class 7 spans 84.2 m to 1752.5 m while
classified ground tops out at 506.1 m, and every return above 1000 m in the delivery is class 7.
The provider uses 7 for noise at both extremes and publishes no 18. Keeping those returns lifts
`max_z_all` — the first real run produced a CHM of 1524.55 m — and, worse, drops `min_z_all`
below the terrain, which is the surface the ground filter reads and the DTM publishes.
"""


class ReadError(RuntimeError):
    """This file is not something we are willing to build a surface from."""


@dataclass(frozen=True, eq=False)
class PointBatch:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    z: NDArray[np.float64]
    classification: NDArray[np.uint8]
    crs_epsg: int
    source_path: Path
    source_sha256: str
    n_noise_excluded: int = 0

    @property
    def n_points(self) -> int:
        """Returns that reach the grid — noise already removed."""
        return int(self.x.size)

    @property
    def n_points_in_file(self) -> int:
        """What the file held, so the record stays comparable with what the provider declared.
        Dropped returns are subtracted from the surfaces, never from the count of what we read."""
        return self.n_points + self.n_noise_excluded

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (float(self.x.min()), float(self.y.min()), float(self.x.max()), float(self.y.max()))

    def density(self, area_m2: float) -> float:
        """Measured, not quoted. The provider's figure is a specification, not a delivery."""
        return self.n_points / area_m2


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def _epsg_of(header: laspy.LasHeader, path: Path) -> int:
    crs = header.parse_crs()
    if crs is None:
        raise ReadError(f"{path.name} declares no CRS; refusing to assume one")
    code = crs.to_epsg()
    if code is None:
        raise ReadError(
            f"{path.name}'s CRS could not be resolved to an EPSG code; refusing to assume one"
        )
    return int(code)


FOOTPRINT_TOLERANCE_M = 0.01
"""Slack around a tile's declared `proj:bbox` before a return counts as impossible.

The catalogue's box is the box of the returns themselves, so a real tile's extremes lie *on* it and
zero slack would refuse every tile. A centimetre absorbs the scale/offset round trip and sits far
below the one real excursion seen — whose magnitude was not measured directly, but inferred from
that tile's density collapsing below 1e-6 pts/m2, which puts its bounding box above 1e15 m2.
"""


def read_laz(
    path: Path,
    expect_epsg: int = 3763,
    footprint: tuple[float, float, float, float] | None = None,
) -> PointBatch:
    try:
        las = laspy.read(path)
    except Exception as exc:  # laspy raises a family of errors; all mean the same thing here
        raise ReadError(f"{path.name} is not readable as LAS/LAZ: {exc}") from exc

    epsg = _epsg_of(las.header, path)
    if epsg != expect_epsg:
        raise ReadError(f"{path.name} declares EPSG:{epsg}, AOI is EPSG:{expect_epsg}")

    x = np.asarray(las.x, dtype=np.float64)
    y = np.asarray(las.y, dtype=np.float64)
    z = np.asarray(las.z, dtype=np.float64)
    for name, coord in (("x", x), ("y", y), ("z", z)):
        n_bad = int((~np.isfinite(coord)).sum())
        if n_bad:
            raise ReadError(
                f"{path.name}: {n_bad} point(s) have non-finite {name} (a header scale/offset "
                f"that decodes to NaN or inf); refusing to build a surface on it"
            )

    classification = np.asarray(las.classification, dtype=np.uint8)
    if not (classification == ASPRS_GROUND).any():
        raise ReadError(
            f"{path.name}: no points carry ASPRS class 2; without an official ground class "
            f"there is nothing to compare our own filter against"
        )

    # Dropped after the finite check, not before: a non-finite coordinate is a refusal about the
    # whole file's header, and finding it on a noise return would not make the header trustworthy.
    keep = ~np.isin(classification, ASPRS_NOISE)
    n_noise = int((~keep).sum())

    if footprint is not None:
        # Checked on the kept returns: noise is discarded anyway, and refusing a whole tile over a
        # return we already refuse to use would turn the guard into an obstacle. What it exists to
        # catch is a coordinate that cannot be real — a corrupted read, not a mislabelled point.
        fminx, fminy, fmaxx, fmaxy = footprint
        t = FOOTPRINT_TOLERANCE_M
        kx, ky = x[keep], y[keep]
        stray = (kx < fminx - t) | (kx > fmaxx + t) | (ky < fminy - t) | (ky > fmaxy + t)
        n_stray = int(stray.sum())
        if n_stray:
            i = int(np.argmax(stray))
            raise ReadError(
                f"{path.name}: {n_stray} return(s) fall outside its declared footprint "
                f"({fminx}, {fminy})-({fmaxx}, {fmaxy}); first at ({kx[i]}, {ky[i]}). A return "
                f"cannot be outside the box the catalogue derived from the returns, so this is a "
                f"corrupted read, not a property of the terrain — refusing rather than publishing "
                f"a density divided by an exploded bounding box"
            )

    return PointBatch(
        x=x[keep],
        y=y[keep],
        z=z[keep],
        classification=classification[keep],
        crs_epsg=epsg,
        source_path=path,
        source_sha256=sha256_file(path),
        n_noise_excluded=n_noise,
    )

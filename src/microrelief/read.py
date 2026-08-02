"""Reading a LAZ tile, and refusing the ones we cannot honestly use."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
from numpy.typing import NDArray

ASPRS_GROUND = 2
_EPSG_IN_WKT = re.compile(r'AUTHORITY\["EPSG","(\d+)"\]')


class ReadError(RuntimeError):
    """This file is not something we are willing to build a surface from."""


@dataclass(frozen=True)
class PointBatch:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    z: NDArray[np.float64]
    classification: NDArray[np.uint8]
    crs_epsg: int
    source_path: Path
    source_sha256: str

    @property
    def n_points(self) -> int:
        return int(self.x.size)

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
        wkt = crs.to_wkt()
        codes = _EPSG_IN_WKT.findall(wkt)
        if not codes:
            raise ReadError(f"{path.name} has a CRS with no EPSG authority; refusing to assume one")
        code = int(codes[-1])
    return int(code)


def read_laz(path: Path, expect_epsg: int = 3763) -> PointBatch:
    try:
        las = laspy.read(path)
    except Exception as exc:  # laspy raises a family of errors; all mean the same thing here
        raise ReadError(f"{path.name} is not readable as LAS/LAZ: {exc}") from exc

    epsg = _epsg_of(las.header, path)
    if epsg != expect_epsg:
        raise ReadError(f"{path.name} declares EPSG:{epsg}, AOI is EPSG:{expect_epsg}")

    classification = np.asarray(las.classification, dtype=np.uint8)
    if not (classification == ASPRS_GROUND).any():
        raise ReadError(
            f"{path.name}: no points carry ASPRS class 2; without an official ground class "
            f"there is nothing to compare our own filter against"
        )

    return PointBatch(
        x=np.asarray(las.x, dtype=np.float64),
        y=np.asarray(las.y, dtype=np.float64),
        z=np.asarray(las.z, dtype=np.float64),
        classification=classification,
        crs_epsg=epsg,
        source_path=path,
        source_sha256=sha256_file(path),
    )

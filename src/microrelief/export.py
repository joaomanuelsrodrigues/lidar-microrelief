"""Writing the product out, with its record attached to it rather than beside it."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray

from microrelief.provenance import Provenance
from microrelief.surfaces import Surfaces

NODATA_FLOAT = -9999.0
NODATA_UINT8 = 255  # not 0: 0 is `undetermined`, which is a published state, not an absence
NODATA_INT32 = -1  # no count can be negative, so this can never collide with a real value


def _prepare(band: NDArray[np.generic]) -> tuple[NDArray[np.generic], float | int]:
    """Replace NaN with an explicit NoData value. A NaN in a band that declares NoData is a
    value that reads as missing in some tools and as a number in others.

    The dtype is preserved rather than widened: a count that arrives as an integer leaves as one,
    and a class code that arrives as a code leaves as a code.
    """
    if band.dtype == np.float32:
        out = np.where(np.isfinite(band), band, NODATA_FLOAT).astype(np.float32)
        return out, NODATA_FLOAT
    if band.dtype == np.uint8:
        return band, NODATA_UINT8
    return band.astype(np.int32), NODATA_INT32


def export(
    surfaces: Surfaces,
    provenance: Provenance,
    out_dir: Path,
    *,
    official_ground_available: bool = True,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    grid = surfaces.grid
    written: dict[str, Path] = {}

    tags = {
        "attribution": provenance.attribution,
        "reproducibility_hash": provenance.reproducibility_hash,
        "package_version": provenance.package_version,
        "flight_dates": ", ".join(provenance.flight_dates),
        "mixed_epochs": str(provenance.mixed_epochs),
    }

    for name, band in surfaces.rasters().items():
        if name == "n_ground_asprs" and not official_ground_available:
            # A count of something that was never counted. NoData is the only value that
            # does not assert a measurement.
            band = np.full(band.shape, NODATA_INT32, dtype=np.int32)
        data, nodata = _prepare(band)
        path = out_dir / f"{name}.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=grid.n_rows,
            width=grid.n_cols,
            count=1,
            dtype=data.dtype,
            crs=f"EPSG:{grid.crs_epsg}",
            transform=grid.transform,
            nodata=nodata,
            compress="deflate",
            tiled=True,
        ) as dst:
            dst.write(data, 1)
            dst.update_tags(**tags, band=name)
        written[name] = path

    prov_path = out_dir / "provenance.json"
    prov_path.write_text(provenance.to_json(), encoding="utf-8")
    written["provenance"] = prov_path
    return written

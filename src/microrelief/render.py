"""Rasters to PNG for the viewer. NoData renders as a hole, deliberately.

Requires the ``site`` extra (matplotlib brings pillow); the core pipeline does
not import this module.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from matplotlib import colormaps
from numpy.typing import NDArray
from PIL import Image

from microrelief.density import BASIS_INTERPOLATED, BASIS_MEASURED, BASIS_UNDETERMINED

LAYERS: tuple[tuple[str, str], ...] = (
    ("mdt", "terrain"),
    ("mds", "terrain"),
    ("chm", "viridis"),
)

# The basis band is categorical, so its colours are fixed per code — min-max scaling
# would recolour `measured` in any run whose set of present codes differs.
BASIS_PALETTE: dict[int, tuple[int, int, int]] = {
    BASIS_MEASURED: (77, 175, 74),  # green
    BASIS_INTERPOLATED: (255, 127, 0),  # orange
    BASIS_UNDETERMINED: (228, 26, 28),  # red
}


def to_rgba(band: NDArray[np.float32], nodata: float, cmap: str = "terrain") -> NDArray[np.uint8]:
    valid = band != nodata
    if not valid.any():
        raise ValueError("no valid cells to render")
    lo, hi = float(band[valid].min()), float(band[valid].max())
    scaled = np.zeros(band.shape, dtype=np.float64)
    scaled[valid] = (band[valid] - lo) / (hi - lo) if hi > lo else 0.5
    rgba: NDArray[np.uint8] = (colormaps[cmap](scaled) * 255).astype(np.uint8)
    rgba[..., 3] = np.where(valid, 255, 0)
    return rgba


def basis_rgba(band: NDArray[np.uint8], nodata: int) -> NDArray[np.uint8]:
    valid = band != nodata
    if not valid.any():
        raise ValueError("no valid cells to render")
    unknown = set(np.unique(band[valid]).tolist()) - set(BASIS_PALETTE)
    if unknown:
        raise ValueError(
            f"unknown basis code(s) {sorted(unknown)}; the palette covers {sorted(BASIS_PALETTE)}"
        )
    rgba = np.zeros((*band.shape, 4), dtype=np.uint8)
    for code, colour in BASIS_PALETTE.items():
        rgba[band == code] = (*colour, 255)
    return rgba


def render(out_dir: Path, viewer_dir: Path) -> None:
    viewer_dir.mkdir(parents=True, exist_ok=True)
    for name, cmap in LAYERS:
        with rasterio.open(out_dir / f"{name}.tif") as src:
            if src.nodata is None:
                raise ValueError(f"{name}.tif declares no nodata; refusing to guess the holes")
            band = src.read(1).astype(np.float32)
            nodata = float(src.nodata)
        Image.fromarray(to_rgba(band, nodata, cmap)).save(viewer_dir / f"{name}.png")
    with rasterio.open(out_dir / "basis.tif") as src:
        if src.nodata is None:
            raise ValueError("basis.tif declares no nodata; refusing to guess the holes")
        Image.fromarray(basis_rgba(src.read(1).astype(np.uint8), int(src.nodata))).save(
            viewer_dir / "basis.png"
        )


if __name__ == "__main__":
    render(Path("outputs"), Path("viewer"))

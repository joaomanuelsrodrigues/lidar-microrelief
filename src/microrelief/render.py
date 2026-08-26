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

# One short of a 256-entry PNG palette, so a band's opaque colours plus one transparent index
# always fit and `_save_palette` never has to merge two colours. Viewer-only: nothing in the
# record or the rasters passes through this table.
PALETTE_LEVELS = 255

# (band, colormap, ramp levels). The CHM runs at 64 levels — 0.67 m per colour step over the
# 0–43 m at Sistelo — because at 255 its cell-to-cell canopy variation compressed to 7.9 MB,
# over the 5 MB the viewer test caps a page image at; 64 measured 4.96 MB, 128 measured 6.4 MB
# (2026-08-26). Fewer levels, not fewer colours after the fact: the palette stays exact.
LAYERS: tuple[tuple[str, str, int], ...] = (
    ("mdt", "terrain", PALETTE_LEVELS),
    ("mds", "terrain", PALETTE_LEVELS),
    ("chm", "viridis", 64),
)

# The basis band is categorical, so its colours are fixed per code — min-max scaling
# would recolour `measured` in any run whose set of present codes differs.
BASIS_PALETTE: dict[int, tuple[int, int, int]] = {
    BASIS_MEASURED: (77, 175, 74),  # green
    BASIS_INTERPOLATED: (255, 127, 0),  # orange
    BASIS_UNDETERMINED: (228, 26, 28),  # red
}


def to_rgba(
    band: NDArray[np.float32], nodata: float, cmap: str = "terrain", levels: int = PALETTE_LEVELS
) -> NDArray[np.uint8]:
    valid = band != nodata
    if not valid.any():
        raise ValueError("no valid cells to render")
    lo, hi = float(band[valid].min()), float(band[valid].max())
    scaled = np.zeros(band.shape, dtype=np.float64)
    scaled[valid] = (band[valid] - lo) / (hi - lo) if hi > lo else 0.5
    lut = colormaps[cmap].resampled(levels)
    rgba: NDArray[np.uint8] = (lut(scaled) * 255).astype(np.uint8)
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


def _save_palette(rgba: NDArray[np.uint8], path: Path) -> None:
    """A palette PNG whose palette is the image's own colour set — every cell at full resolution,
    every hole transparent, nothing quantised, at less than half the truecolour bytes.

    Not a quantiser on purpose: Pillow's FASTOCTREE, tried first (2026-08-26), collapsed the 256
    colours of the terrain ramp to 50 and moved the basis layer's alpha from 255 to 254 — a viewer
    that reports "measured / interpolated / undetermined" cannot publish approximated colours. The
    colormaps are sampled at PALETTE_LEVELS so the opaque colours plus one transparent index fit;
    an image that does not fit is refused, never merged.
    """
    alpha = rgba[..., 3]
    if not np.isin(alpha, (0, 255)).all():
        raise ValueError("alpha must be 0 or 255: a palette PNG carries no partial transparency")
    opaque = alpha == 255
    rgb = rgba[..., :3].astype(np.uint32)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    colours, inverse = np.unique(key[opaque], return_inverse=True)
    holes = bool((~opaque).any())
    if colours.size + int(holes) > 256:
        raise ValueError(
            f"{colours.size} opaque colours plus {'a transparent index' if holes else 'no holes'} "
            f"exceed a 256-entry palette; refusing to merge colours to make them fit"
        )
    index = np.zeros(alpha.shape, dtype=np.uint8)
    index[opaque] = inverse.astype(np.uint8)
    if holes:
        index[~opaque] = colours.size  # the transparent slot; <= 255 by the check above
    palette = np.stack([(colours >> 16) & 255, (colours >> 8) & 255, colours & 255], axis=1)
    if holes:
        palette = np.vstack([palette, np.zeros((1, 3), dtype=np.uint32)])
    img = Image.fromarray(index)  # mode L; putpalette turns it into P
    img.putpalette(palette.astype(np.uint8).tobytes())
    if holes:
        img.save(path, optimize=True, transparency=int(colours.size))
    else:
        img.save(path, optimize=True)


def render(out_dir: Path, viewer_dir: Path) -> None:
    viewer_dir.mkdir(parents=True, exist_ok=True)
    for name, cmap, levels in LAYERS:
        with rasterio.open(out_dir / f"{name}.tif") as src:
            if src.nodata is None:
                raise ValueError(f"{name}.tif declares no nodata; refusing to guess the holes")
            band = src.read(1).astype(np.float32)
            nodata = float(src.nodata)
        _save_palette(to_rgba(band, nodata, cmap, levels), viewer_dir / f"{name}.png")
    with rasterio.open(out_dir / "basis.tif") as src:
        if src.nodata is None:
            raise ValueError("basis.tif declares no nodata; refusing to guess the holes")
        _save_palette(
            basis_rgba(src.read(1).astype(np.uint8), int(src.nodata)), viewer_dir / "basis.png"
        )


if __name__ == "__main__":
    render(Path("outputs"), Path("docs/viewer"))

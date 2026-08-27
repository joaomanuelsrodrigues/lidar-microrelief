"""to_rgba turns one raster band into RGBA; NoData renders as a hole, deliberately."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from microrelief.render import LAYERS, _save_palette, basis_rgba, to_rgba


def test_nodata_becomes_transparent_not_a_colour() -> None:
    band = np.array([[1.0, -9999.0], [2.0, 3.0]], dtype=np.float32)
    rgba = to_rgba(band, nodata=-9999.0)
    assert rgba.shape == (2, 2, 4)
    assert rgba[0, 1, 3] == 0  # the hole is transparent
    assert (rgba[0, 0, 3], rgba[1, 1, 3]) == (255, 255)


def test_scaling_ignores_nodata_so_one_sentinel_cannot_flatten_the_image() -> None:
    band = np.array([[10.0, -9999.0], [11.0, 12.0]], dtype=np.float32)
    rgba = to_rgba(band, nodata=-9999.0)
    assert np.ptp(rgba[..., 0][band != -9999.0]) > 100


def test_an_all_nodata_band_refuses_rather_than_dividing_by_zero() -> None:
    band = np.full((4, 4), -9999.0, dtype=np.float32)
    with pytest.raises(ValueError, match="no valid cells"):
        to_rgba(band, nodata=-9999.0)


def test_a_rectangular_band_keeps_its_own_shape() -> None:
    # Every raster fixture in this repo is square (2026-08-05); this one is not, on purpose.
    band = np.arange(6, dtype=np.float32).reshape(2, 3)
    rgba = to_rgba(band, nodata=-9999.0)
    assert rgba.shape == (2, 3, 4)


def test_basis_colours_are_fixed_per_code_not_scaled_to_the_codes_present() -> None:
    # Min-max scaling would recolour `measured` in a run with no undetermined cells.
    full = np.array([[0, 1], [2, 255]], dtype=np.uint8)
    without_undetermined = np.array([[1, 1], [2, 255]], dtype=np.uint8)
    a = basis_rgba(full, nodata=255)
    b = basis_rgba(without_undetermined, nodata=255)
    assert tuple(a[0, 1]) == tuple(b[0, 0])  # measured keeps its colour
    assert tuple(a[1, 0]) == tuple(b[1, 0])  # interpolated keeps its colour
    assert a[1, 1, 3] == 0 and b[1, 1, 3] == 0  # nodata is transparent
    # and the three codes are three distinct colours
    assert len({tuple(a[0, 0]), tuple(a[0, 1]), tuple(a[1, 0])}) == 3


def test_basis_refuses_an_unknown_code() -> None:
    band = np.array([[0, 7]], dtype=np.uint8)
    with pytest.raises(ValueError, match="unknown basis code"):
        basis_rgba(band, nodata=255)


def test_an_all_nodata_basis_refuses_too() -> None:
    band = np.full((2, 2), 255, dtype=np.uint8)
    with pytest.raises(ValueError, match="no valid cells"):
        basis_rgba(band, nodata=255)


def _rgba_with(n_colours: int, n_holes: int) -> np.ndarray:
    """n_colours distinct opaque colours followed by n_holes transparent pixels, one row."""
    px = np.zeros((1, n_colours + n_holes, 4), dtype=np.uint8)
    i = np.arange(n_colours)
    px[0, :n_colours, 0] = i % 256
    px[0, :n_colours, 1] = (255 - i) % 256
    px[0, :n_colours, 2] = (i * 7) % 256
    px[0, :n_colours, 3] = 255
    return px


def test_save_palette_keeps_every_colour_and_every_hole(tmp_path: Path) -> None:
    rgba = _rgba_with(255, 1)
    _save_palette(rgba, tmp_path / "p.png")
    with Image.open(tmp_path / "p.png") as im:
        assert im.mode == "P"
        back = np.asarray(im.convert("RGBA"))
    assert np.array_equal(back[..., 3] == 0, rgba[..., 3] == 0)
    opaque = rgba[..., 3] == 255
    assert np.array_equal(back[opaque], rgba[opaque])


def test_save_palette_refuses_more_colours_than_a_palette_holds(tmp_path: Path) -> None:
    # 256 opaque colours fit; 256 plus a transparent index do not, and nothing is merged to fit.
    _save_palette(_rgba_with(256, 0), tmp_path / "fits.png")
    with pytest.raises(ValueError, match="refusing"):
        _save_palette(_rgba_with(256, 1), tmp_path / "overflow.png")


def test_save_palette_refuses_partial_transparency(tmp_path: Path) -> None:
    rgba = _rgba_with(2, 0)
    rgba[0, 0, 3] = 128
    with pytest.raises(ValueError, match="0 or 255"):
        _save_palette(rgba, tmp_path / "half.png")


def test_to_rgba_never_needs_more_than_255_opaque_colours() -> None:
    # The colormaps are sampled at 255 levels, one short of a palette, so a band with holes always
    # fits 255 colours plus the transparent index. At 256 levels this band uses every entry.
    band = np.linspace(0.0, 1.0, 4096, dtype=np.float32).reshape(64, 64)
    rgba = to_rgba(band, nodata=-9999.0)
    colours = {tuple(c) for c in rgba.reshape(-1, 4).tolist()}
    assert len(colours) <= 255


def test_to_rgba_levels_is_the_number_of_colours_it_can_use() -> None:
    band = np.linspace(0.0, 1.0, 4096, dtype=np.float32).reshape(64, 64)
    rgba = to_rgba(band, nodata=-9999.0, levels=64)
    assert len({tuple(c) for c in rgba.reshape(-1, 4).tolist()}) <= 64


def test_every_viewer_layer_declares_levels_a_palette_can_hold() -> None:
    assert all(1 <= levels <= 255 for _name, _cmap, levels in LAYERS)

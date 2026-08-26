"""to_rgba turns one raster band into RGBA; NoData renders as a hole, deliberately."""

import numpy as np
import pytest

from microrelief.render import basis_rgba, to_rgba


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

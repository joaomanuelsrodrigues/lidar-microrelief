import warnings
from pathlib import Path

import laspy
import numpy as np
import pytest
from pyproj import CRS

from microrelief.read import ASPRS_GROUND, ReadError, read_laz
from tests.synthetic import write_las


def test_reads_points_and_classification(tmp_path) -> None:
    path = tmp_path / "tiny.laz"
    write_las(path, n=1000, epsg=3763)
    batch = read_laz(path, expect_epsg=3763)
    assert batch.n_points == 1000
    assert batch.classification.dtype == np.uint8
    assert (batch.classification == ASPRS_GROUND).any()
    assert batch.crs_epsg == 3763


def test_a_different_crs_refuses_instead_of_reprojecting(tmp_path) -> None:
    path = tmp_path / "wrong_crs.laz"
    write_las(path, n=100, epsg=4326)
    with pytest.raises(ReadError, match="declares EPSG:4326, AOI is EPSG:3763"):
        read_laz(path, expect_epsg=3763)


def test_a_file_without_a_crs_refuses_rather_than_assuming_the_national_one(tmp_path) -> None:
    path = tmp_path / "no_crs.laz"
    write_las(path, n=100, epsg=None)
    with pytest.raises(ReadError, match="no CRS"):
        read_laz(path, expect_epsg=3763)


def test_a_cloud_with_no_official_ground_class_is_read_and_declares_the_absence(
    tmp_path: Path,
) -> None:
    """Unclassified, self-classified and drone clouds are readable products. What is absent is
    the official comparison, and absence is a field — the same pattern as
    `point_count_catalogue=None`. Crashing here refused the data over a missing comparison."""
    path = tmp_path / "unclassified.laz"
    write_las(path, n=100, epsg=3763, classification=5)  # vegetation only, no class 2 anywhere
    batch = read_laz(path, expect_epsg=3763)
    assert batch.has_official_ground is False
    assert batch.n_points > 0


def test_a_cloud_with_official_ground_says_so(tmp_path: Path) -> None:
    path = tmp_path / "classified.laz"
    write_las(path, n=100, epsg=3763, classification=ASPRS_GROUND)
    assert read_laz(path, expect_epsg=3763).has_official_ground is True


def test_source_hash_is_recorded_for_provenance(tmp_path) -> None:
    path = tmp_path / "tiny.laz"
    write_las(path, n=100, epsg=3763)
    assert len(read_laz(path, expect_epsg=3763).source_sha256) == 64


def test_a_crs_with_no_epsg_equivalent_refuses_rather_than_assuming(tmp_path) -> None:
    # A custom projection built from raw PROJ parameters, not from an EPSG code: pyproj's
    # confidence search has nothing to match it against, so to_epsg() is genuinely None —
    # not merely stripped of the AUTHORITY tag a naive fixture might try to remove.
    crs = CRS.from_proj4(
        "+proj=tmerc +lat_0=0 +lon_0=-8.13 +k=0.9998 +x_0=250000 +y_0=0 "
        "+ellps=GRS80 +units=m +no_defs"
    )
    assert crs.to_epsg() is None  # the premise this test depends on

    path = tmp_path / "no_epsg_equivalent.laz"
    x = np.array([48000.0, 48001.0])
    y = np.array([169000.0, 169001.0])
    z = np.array([1.0, 2.0])
    header = laspy.LasHeader(version="1.4", point_format=6)
    header.scales = np.array([0.01, 0.01, 0.01])
    header.offsets = np.array([np.floor(x.min()), np.floor(y.min()), np.floor(z.min())])
    header.add_crs(crs)
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = np.full(x.size, ASPRS_GROUND, dtype=np.uint8)
    las.write(path)

    # Confirm the round trip preserves the premise before trusting the refusal below.
    assert laspy.read(path).header.parse_crs().to_epsg() is None

    with pytest.raises(ReadError, match="could not be resolved to an EPSG code"):
        read_laz(path, expect_epsg=3763)


@pytest.mark.parametrize("axis,name", [(0, "x"), (1, "y"), (2, "z")])
def test_a_non_finite_coordinate_refuses_rather_than_polluting_the_nan_sentinel(
    tmp_path, axis, name
) -> None:
    """A NaN header offset decodes every point on that axis to NaN, whatever the raw stored

    integer is -- this is what a malformed or corrupted header produces in practice. If this
    slipped through, a cell built from such a point would carry n_all > 0 next to a NaN
    elevation: the one state the contract forbids, because NaN would stop uniquely meaning
    "nothing was measured here."
    """
    x = np.array([48000.0, 48001.0])
    y = np.array([169000.0, 169001.0])
    z = np.array([1.0, 2.0])
    offsets = [np.floor(x.min()), np.floor(y.min()), np.floor(z.min())]
    offsets[axis] = np.nan

    header = laspy.LasHeader(version="1.4", point_format=6)
    header.scales = np.array([0.01, 0.01, 0.01])
    header.offsets = np.array(offsets)
    header.add_crs(CRS.from_epsg(3763))
    las = laspy.LasData(header)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # the NaN-offset cast itself warns
        las.x, las.y, las.z = x, y, z
    las.classification = np.full(x.size, ASPRS_GROUND, dtype=np.uint8)
    path = tmp_path / f"nan_offset_{name}.laz"
    las.write(path)

    # Confirm the round trip actually produces the NaN premise before trusting the refusal.
    reread = laspy.read(path)
    coord = np.asarray(getattr(reread, name), dtype=np.float64)
    assert np.isnan(coord).all()

    with pytest.raises(ReadError, match=f"non-finite {name}"):
        read_laz(path, expect_epsg=3763)


def _cloud_with_noise(tmp_path: Path) -> Path:
    """A tile shaped like the delivered ones: flat ground, canopy, and class-7 returns at BOTH
    extremes — one far above the canopy, one far below the terrain."""
    x = np.array([48000.2, 48000.4, 48000.6, 48000.3, 48000.5], dtype=np.float64)
    y = np.array([169000.2, 169000.4, 169000.6, 169000.3, 169000.5], dtype=np.float64)
    z = np.array([100.0, 100.0, 100.0, 1700.0, 5.0], dtype=np.float64)
    cls = np.array([ASPRS_GROUND, ASPRS_GROUND, 5, 7, 7], dtype=np.uint8)

    header = laspy.LasHeader(version="1.4", point_format=6)
    header.scales = np.array([0.01, 0.01, 0.01])
    header.offsets = np.array([np.floor(x.min()), np.floor(y.min()), np.floor(z.min())])
    header.add_crs(CRS.from_epsg(3763))
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = cls
    path = tmp_path / "noisy.laz"
    las.write(path)
    return path


def test_noise_returns_are_excluded_from_the_surfaces_and_counted(tmp_path: Path) -> None:
    """Measured on the real delivery, and no synthetic fixture could have found it: ASPRS class 7
    spans BOTH extremes. Across the four Sistelo tiles class 7 runs from 84.2 m to 1752.5 m while
    classified ground tops out at 506.1 m, and every return above 1000 m is class 7.

    Kept, it poisons both surfaces. Above, it lifts `max_z_all` and the CHM reached 1524.55 m.
    Below, it drops `min_z_all` beneath the terrain — and that is the worse half, because
    `min_z_all` is the minimum surface the ground filter reads and the DTM publishes.

    The file's own total is still reported, so the record can still be checked against what the
    provider declared; the excluded count sits beside it rather than vanishing.
    """
    batch = read_laz(_cloud_with_noise(tmp_path), expect_epsg=3763)

    assert batch.n_points == 3, "the two class-7 returns must not reach the grid"
    assert batch.n_noise_excluded == 2
    assert batch.n_points_in_file == 5, "the file's own total stays reportable"

    # The discriminating part: it is the extremes that had to go, not merely two rows.
    assert batch.z.min() == 100.0
    assert batch.z.max() == 100.0
    assert 7 not in set(batch.classification.tolist())


def _tile_at(
    tmp_path: Path, extra_xy: tuple[float, float] | None = None, extra_cls: int = ASPRS_GROUND
) -> Path:
    """A tile whose returns sit inside a 1 m box, optionally with one return placed elsewhere."""
    x = [48000.0, 48000.5, 48001.0]
    y = [169000.0, 169000.5, 169001.0]
    if extra_xy is not None:
        x.append(extra_xy[0])
        y.append(extra_xy[1])
    xa = np.array(x, dtype=np.float64)
    ya = np.array(y, dtype=np.float64)
    za = np.full(xa.size, 100.0)

    header = laspy.LasHeader(version="1.4", point_format=6)
    header.scales = np.array([0.001, 0.001, 0.001])
    header.offsets = np.array([0.0, 0.0, 0.0])
    header.add_crs(CRS.from_epsg(3763))
    las = laspy.LasData(header)
    las.x, las.y, las.z = xa, ya, za
    cls = np.full(xa.size, ASPRS_GROUND, dtype=np.uint8)
    if extra_xy is not None:
        cls[-1] = extra_cls
    las.classification = cls
    path = tmp_path / f"fp_{'wild' if extra_xy else 'clean'}.laz"
    las.write(path)
    return path


FOOTPRINT = (48000.0, 169000.0, 48001.0, 169001.0)


def test_a_return_outside_the_declared_footprint_is_a_refusal(tmp_path: Path) -> None:
    """Found by the first real run, not by any test: across three replay pairs over the Sistelo
    AOI one pair disagreed, and the disagreement was a single return of 109,312,003 carrying a
    coordinate far outside its tile. It blew that tile's measured density to ~0 (the bbox it is
    divided by exploded), moved one return from inside the AOI to outside, and left one grid cell
    holding 32 instead of 33 — while the other five bands stayed byte-identical, which is what
    rules out any larger corruption.

    The catalogue already declares each tile's `proj:bbox`, and it is the box of the returns
    themselves. Nothing checked the points against it, so a corrupted coordinate became a
    published number instead of a refusal. This does not make replay stable; it makes an unstable
    run fail loudly.
    """
    with pytest.raises(ReadError, match="outside its declared footprint"):
        read_laz(_tile_at(tmp_path, (1_000_000.0, 169000.0)), expect_epsg=3763, footprint=FOOTPRINT)


def test_a_noise_return_outside_the_footprint_is_also_a_refusal(tmp_path: Path) -> None:
    """E-006's frozen-tree rounds caught the guard checking retained returns only: a corrupted
    coordinate on a class-7/18 return was silently dropped with the noise, not detected. But a
    coordinate that cannot be real is a property of the READ, not of the return's class — if one
    record decoded to garbage, nothing vouches for the records beside it. Verified on the four
    tiles before extending (2026-08-08): zero noise returns fall outside any declared box, so the
    guard's wider scope refuses nothing that the provider actually ships."""
    with pytest.raises(ReadError, match="outside its declared footprint"):
        read_laz(
            _tile_at(tmp_path, (1_000_000.0, 169000.0), extra_cls=7),
            expect_epsg=3763,
            footprint=FOOTPRINT,
        )


def test_the_footprint_check_does_not_fire_on_the_boundary_or_when_absent(tmp_path: Path) -> None:
    """The sibling that keeps the guard from being a nuisance. The declared box is the box of the
    returns, so its own extremes lie exactly on it — a check that refused those would refuse every
    real tile. And with no footprint declared there is nothing to check against, which is the
    offline path."""
    clean = _tile_at(tmp_path)
    assert read_laz(clean, expect_epsg=3763, footprint=FOOTPRINT).n_points == 3
    assert read_laz(clean, expect_epsg=3763).n_points == 3

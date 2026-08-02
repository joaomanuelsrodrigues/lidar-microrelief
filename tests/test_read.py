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


def test_a_file_with_no_ground_class_at_all_refuses(tmp_path) -> None:
    path = tmp_path / "unclassified.laz"
    write_las(path, n=100, epsg=3763, classification=1)
    with pytest.raises(ReadError, match="no points carry ASPRS class 2"):
        read_laz(path, expect_epsg=3763)


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

import numpy as np
import pytest

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

"""The shipped sample: a stranger's first run, and this repository's first cross-machine probe.

The sample is real DGT data (CC BY 4.0), 150 m × 150 m around the tallest verified terrace riser.
Its contract is locked here so the file cannot drift from what the README says about it; the run
test below is the suite's only test on real returns, and on CI it is the first time a machine that
is not the author's reproduces the record.
"""

import hashlib
import json
import warnings
from pathlib import Path

import laspy
import numpy as np
import rasterio

from microrelief.cli import main

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sistelo-sample"
LAZ = SAMPLE / "sistelo-terraces-150m.laz"
WINDOW = (-20210.0, 256245.0, -20060.0, 256395.0)
SIZE_CAP_BYTES = 6_000_000  # declared in examples/sistelo-sample/README.md, not a pipeline number
# The string the README command reads; the record must carry it verbatim (it is outside the
# reproducibility hash, so only this comparison notices a reworded file).
DGT = (SAMPLE / "attribution.txt").read_text(encoding="utf-8").strip()


def test_the_sample_is_small_enough_to_be_a_first_run() -> None:
    assert LAZ.stat().st_size <= SIZE_CAP_BYTES


def test_the_sample_keeps_its_crs_and_lies_inside_its_declared_window() -> None:
    with laspy.open(LAZ) as f:
        h = f.header
        assert h.parse_crs().to_epsg() == 3763
        assert h.point_count > 100_000
        minx, miny, maxx, maxy = WINDOW
        assert h.mins[0] >= minx - 0.01 and h.maxs[0] <= maxx + 0.01
        assert h.mins[1] >= miny - 0.01 and h.maxs[1] <= maxy + 0.01


def test_the_sample_carries_the_official_ground_class() -> None:
    las = laspy.read(LAZ)
    assert (np.asarray(las.classification) == 2).any()


def test_the_sample_aoi_declares_its_crs() -> None:
    doc = json.loads((SAMPLE / "aoi.geojson").read_text(encoding="utf-8"))
    assert doc["properties"]["bounds"] == list(WINDOW)
    assert doc["properties"]["bounds_epsg"] == 3763


def test_running_the_sample_reproduces_the_expected_record(tmp_path: Path) -> None:
    out = tmp_path / "out"
    rc = main(
        [
            "run",
            "--aoi",
            str(SAMPLE / "aoi.geojson"),
            "--laz",
            str(SAMPLE),
            "--out",
            str(out),
            "--attribution",
            DGT,
        ]
    )
    assert rc in (0, None)
    got = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    expected = json.loads((SAMPLE / "expected" / "provenance.json").read_text(encoding="utf-8"))
    for key in (
        "grid",
        "honesty",
        "agreement",
        "parameters",
        "reproducibility_hash",
        "attribution",
    ):
        assert got[key] == expected[key], key
    assert got["inputs"][0]["sha256"] == expected["inputs"][0]["sha256"]

    # Band identity across machines is UNVERIFIED for this package (README §What this does not
    # support). Warn-class until CI has shown it green once; then promote to assert.
    want = json.loads((SAMPLE / "expected" / "bands.sha256.json").read_text(encoding="utf-8"))
    for name, digest in want.items():
        with rasterio.open(out / f"{name}.tif") as src:
            here = hashlib.sha256(src.read(1).tobytes()).hexdigest()
        if here != digest:
            warnings.warn(
                f"band {name} differs from the author's machine: {here[:12]} vs {digest[:12]} "
                f"(cross-machine replay probe, warn-class)",
                stacklevel=1,
            )

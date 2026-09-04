"""What `scripts/measure_risers.py build` has to leave in the cache.

The script had no tests. This file covers the one property a second consumer now depends on: the
accumulator computes the all-returns surface in the same pass that produces the official-ground
one, and `build` was writing only the latter. Recovering the rest would have meant reading the
delivery again -- 845 MB -- for arrays that had already been computed and thrown away.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

from tests.synthetic import ORIGIN_X, ORIGIN_Y, ramp, write_las

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measure_risers.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_risers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def _aoi(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "crs_epsg": 3763,
                "coordinates": [
                    [
                        [ORIGIN_X, ORIGIN_Y],
                        [ORIGIN_X + 40, ORIGIN_Y],
                        [ORIGIN_X + 40, ORIGIN_Y + 40],
                        [ORIGIN_X, ORIGIN_Y + 40],
                        [ORIGIN_X, ORIGIN_Y],
                    ]
                ],
            }
        )
    )
    return path


def test_the_build_cache_carries_the_all_returns_surface_too(tmp_path: Path) -> None:
    """`min_z_all` is what a ground filter reads; it is computed in the same pass and was being
    dropped, which would have cost a second read of the delivery to recover."""
    laz = tmp_path / "laz"
    laz.mkdir()
    write_las(laz / "SYNTH-1.laz", cloud=ramp(size_m=40.0, spacing=0.5), epsg=3763)
    cache = tmp_path / "surface.npz"

    assert mod.build(_aoi(tmp_path / "aoi.geojson"), laz, cache) == 0

    with np.load(cache, allow_pickle=False) as data:
        assert {"min_z_ground", "n_ground", "min_z_all", "max_z_all", "n_all"} <= set(data.files)
        assert data["min_z_all"].shape == data["min_z_ground"].shape
        assert data["max_z_all"].shape == data["min_z_ground"].shape
        assert data["n_all"].shape == data["min_z_ground"].shape


def test_the_cached_all_returns_surface_is_not_a_copy_of_the_ground_one(tmp_path: Path) -> None:
    """A test that only checks the keys exist would pass if `min_z_all=stats.min_z_ground_asprs`
    were written by mistake, which is the plausible slip. The two differ where a cell holds a
    non-ground return below no ground return at all."""
    laz = tmp_path / "laz"
    laz.mkdir()
    # The ramp covers a quarter of the AOI; the vegetation is scattered over all of it, so the
    # cells beyond the ramp hold returns the official-ground surface cannot see.
    write_las(laz / "SYNTH-1.laz", cloud=ramp(size_m=20.0, spacing=0.5), epsg=3763)
    write_las(laz / "SYNTH-2.laz", n=2000, epsg=3763, classification=5)
    cache = tmp_path / "surface.npz"

    assert mod.build(_aoi(tmp_path / "aoi.geojson"), laz, cache) == 0

    with np.load(cache, allow_pickle=False) as data:
        vegetation_only = (data["n_all"] > 0) & (data["n_ground"] == 0)
        assert vegetation_only.any(), "the fixture must hold cells the ground surface cannot see"
        assert np.isnan(data["min_z_ground"][vegetation_only]).all()
        assert np.isfinite(data["min_z_all"][vegetation_only]).any()

"""The acceptance instrument's own argv contract.

`scripts/compare_runs.py` is what says a release changed identity and nothing else. Its
`--expect-new-limitations` flag is written in `docs/live-smoke.md` BEFORE the two positionals,
and that sentence ("the recorded acceptance command replays unchanged") was published once
without ever being run: an optional-value flag in that position makes argparse swallow the
`old` positional, so both recorded commands died at exit 2 while the module comment, the help
text and the live-smoke record all asserted they worked (s293).

So this file exercises the flag IN THE RECORDED POSITION, end to end, on real files.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_runs.py"

LIMS_0_4_0 = ("a", "b")
NEW_IN_0_4_1 = (
    "The reproducibility hash does not cover the attribution string: two runs differing "
    "only in --attribution share a hash, so a product can be relabelled and keep its anchor.",
    "The only resource ceiling is a cell count (200,000,000 cells, ~12 GB of per-cell "
    "arrays), not a memory bound: a grid inside it can still exhaust memory, and that "
    "failure is an OOM kill rather than a refusal with a reason.",
)


def _a_run(d: Path, version: str, limitations: tuple[str, ...]) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    band = np.arange(4, dtype=np.float32).reshape(2, 2)
    with rasterio.open(
        d / "mdt.tif",
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:3763",
        transform=Affine(0.5, 0, 0, 0, -0.5, 0),
        nodata=-9999.0,
    ) as dst:
        dst.write(band, 1)
    (d / "provenance.json").write_text(
        json.dumps(
            {
                "package_version": version,
                "created_utc": f"2026-08-{'10' if version == '0.4.0' else '30'}T00:00:00+00:00",
                "reproducibility_hash": "deadbeef" if version == "0.4.0" else "cafef00d",
                "known_limitations": list(limitations),
                "grid": {"cell": 0.5},
            }
        ),
        encoding="utf-8",
    )
    return d


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )


def test_the_flag_in_its_recorded_position_is_parsed_not_swallowed(tmp_path: Path) -> None:
    """The exact argv shape `docs/live-smoke.md` records: flag FIRST, then old, then new.

    Exit 2 here means argparse rejected the command line -- the defect this file exists for.
    """
    old = _a_run(tmp_path / "old", "0.4.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.4.1", LIMS_0_4_0 + NEW_IN_0_4_1)
    got = _run("--expect-new-limitations", str(old), str(new))
    assert got.returncode != 2, f"argparse rejected the recorded form: {got.stderr}"
    assert got.returncode == 0, f"acceptance failed: {got.stderr}"
    assert "gained exactly the two declared gaps" in got.stdout


def test_the_bare_command_still_requires_the_list_to_be_unchanged(tmp_path: Path) -> None:
    """The control: without the flag, the added limitations must be reported as a difference.

    A pass here with the flag and a pass here without it would mean the flag does nothing.
    """
    old = _a_run(tmp_path / "old", "0.4.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.4.1", LIMS_0_4_0 + NEW_IN_0_4_1)
    got = _run(str(old), str(new))
    assert got.returncode == 1
    assert "known_limitations is not unchanged" in got.stderr


def test_a_release_with_no_recorded_additions_is_named_not_crashed(tmp_path: Path) -> None:
    """The release is read from the NEW run's record, so an unknown one must say so.

    Before s293 this key came from the command line and reached a dict unguarded: a library
    caller passing an unknown release got a KeyError instead of a verdict.
    """
    old = _a_run(tmp_path / "old", "0.4.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "9.9.9", LIMS_0_4_0 + NEW_IN_0_4_1)
    got = _run("--expect-new-limitations", str(old), str(new))
    assert got.returncode == 1
    assert "no expected limitations" in got.stderr
    assert "Traceback" not in got.stderr


@pytest.mark.parametrize("release", sorted({"0.4.0", "0.4.1"}))
def test_every_release_the_instrument_knows_is_reachable_from_a_record(
    tmp_path: Path, release: str
) -> None:
    """A release whose entry exists but that no record can select is a dead branch."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("compare_runs", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["compare_runs"] = mod
    spec.loader.exec_module(mod)
    assert release in mod.EXPECTED_NEW_LIMITATIONS
    old = _a_run(tmp_path / "old", "0.0.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", release, LIMS_0_4_0 + mod.EXPECTED_NEW_LIMITATIONS[release])
    got = _run("--expect-new-limitations", str(old), str(new))
    assert got.returncode == 0, got.stderr

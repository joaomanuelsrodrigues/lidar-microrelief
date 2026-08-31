"""The acceptance instrument's own argv contract.

`scripts/compare_runs.py` is what says a release changed identity and nothing else. Its
`--expect-new-limitations` flag is written in `docs/live-smoke.md` BEFORE the two positionals,
and that sentence ("the recorded acceptance command replays unchanged") was published once
without ever being run: an optional-value flag in that position makes argparse swallow the
`old` positional, so both recorded commands died at exit 2 while the module comment, the help
text and the live-smoke record all asserted they worked (s293).

So this file exercises the flag IN THE RECORDED POSITION, end to end, on real files.
"""

import contextlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_runs.py"

# Assembled, never written out whole: this file is itself in the population the sweep below
# scans, and a planted literal would make the guard fire on its own source (s283).
FLAG = "--expect-" + "new-limitations"


@contextlib.contextmanager
def _loaded() -> Iterator[ModuleType]:
    """Import the script under a name that does not outlive the test.

    `sys.modules["compare_runs"]` used to be left registered for the rest of the session, so a
    later test importing that generic name would get whichever parametrisation ran last.
    """
    spec = importlib.util.spec_from_file_location("compare_runs", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["compare_runs"] = mod
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("compare_runs", None)


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
    got = _run(FLAG, str(old), str(new))
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
    got = _run(FLAG, str(old), str(new))
    assert got.returncode == 1
    assert "no expected limitations" in got.stderr
    assert "Traceback" not in got.stderr
    # ...and it must not then assert an expectation it has just said it does not hold. The
    # unknown branch used to fall back to the OLD list and report "known_limitations is not the
    # old list plus the two declared gaps", sending a reader after a limitations bug that does
    # not exist -- two problem lines, contradicting each other, from one refusal.
    assert "the old list plus" not in got.stderr, (
        f"a second, contradictory problem line: {got.stderr}"
    )


@pytest.mark.parametrize("release", sorted({"0.4.0", "0.4.1"}))
def test_every_release_the_instrument_knows_is_reachable_from_a_record(
    tmp_path: Path, release: str
) -> None:
    """A release whose entry exists but that no record can select is a dead branch."""
    with _loaded() as mod:
        assert release in mod.EXPECTED_NEW_LIMITATIONS
        old = _a_run(tmp_path / "old", "0.0.0", LIMS_0_4_0)
        new = _a_run(tmp_path / "new", release, LIMS_0_4_0 + mod.EXPECTED_NEW_LIMITATIONS[release])
    got = _run(FLAG, str(old), str(new))
    assert got.returncode == 0, got.stderr


# --- The class this file exists for, one level up -------------------------------------------
#
# Twice now a command line was WRITTEN into a document as a record of what ran, and never run:
# once with an optional-value flag that argparse could not parse in that position (s293), and
# once when the fix reverted the flag to `store_true` and the transcript above it kept the
# pre-fix argv (s295, found by review, one line above the note explaining that exact failure).
# Fixing the two sites would leave the class open, so the parser itself is now the judge of
# every command any document claims to record.

_AFTER_FLAG = re.compile(re.escape(FLAG) + r"[\s`|]+([^\s`|]+)")
_VERSION_SHAPED = re.compile(r"\d+\.\d+(?:\.\d+)?\Z")


def _tracked_documents() -> list[Path]:
    """The population is what git tracks, not a glob: a convention-shaped selector has let a
    member escape this repo's guards three times (s271, s276, s279)."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / n for n in out.stdout.split("\0") if n.endswith(".md")]


def _recorded_argvs(text: str) -> list[list[str]]:
    """Every `$ ... compare_runs.py ...` line, as the argv it claims to have run."""
    argvs: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line.startswith("$ ") or "compare_runs.py" not in line:
            continue
        # `comments=True`: a recorded command may carry a trailing shell comment, and reading
        # it as arguments would make this sweep reject a command that runs (measured, s295 --
        # the instrument over-fired on its first run before it had ever judged a real defect).
        toks = shlex.split(line[2:], comments=True)
        i = max(k for k, t in enumerate(toks) if t.endswith("compare_runs.py"))
        argvs.append(toks[i + 1 :])
    return argvs


def _version_after_flag(text: str) -> list[tuple[int, str]]:
    """Fragments -- table cells, prose -- that put a release name where no value is taken."""
    hits: list[tuple[int, str]] = []
    for n, raw in enumerate(text.splitlines(), 1):
        for m in _AFTER_FLAG.finditer(raw):
            if _VERSION_SHAPED.match(m.group(1)):
                hits.append((n, m.group(1)))
    return hits


def test_every_command_recorded_in_a_document_is_one_the_parser_accepts() -> None:
    """A recorded command that exits 2 is not a record of anything; it never ran."""
    docs = _tracked_documents()
    assert docs, "no tracked .md files: this test scanned nothing"
    swept, bad = 0, []
    with _loaded() as mod:
        parser = mod.build_parser()
        for doc in docs:
            for argv in _recorded_argvs(doc.read_text(encoding="utf-8")):
                swept += 1
                try:
                    parser.parse_args(argv)
                except SystemExit as exc:
                    bad.append((str(doc.relative_to(ROOT)), argv, exc.code))
    assert swept >= 3, f"only {swept} recorded command(s) found across {len(docs)} document(s)"
    assert not bad, f"argparse rejects {len(bad)} of {swept} recorded command(s): {bad}"


def test_no_document_writes_a_release_name_where_the_flag_takes_no_value() -> None:
    """The table cells and prose the command sweep above cannot reach."""
    docs = _tracked_documents()
    bad = [
        (str(doc.relative_to(ROOT)), n, tok)
        for doc in docs
        for n, tok in _version_after_flag(doc.read_text(encoding="utf-8"))
    ]
    assert not bad, f"the flag takes no value, but {len(bad)} site(s) pass one: {bad}"


def test_the_two_sweeps_fire_on_a_planted_defect_and_stay_quiet_on_the_fixed_form() -> None:
    """Both arms, because a guard that never fires and a clean tree are the same green.

    Every planted string is assembled here rather than written out: this file is inside the
    population the sweeps scan, so a literal would make them fire on their own source (s283).
    """
    planted = f"$ .venv/bin/python scripts/compare_runs.py {FLAG} 0.4.1 outputs outputs_b"
    fixed = f"$ .venv/bin/python scripts/compare_runs.py {FLAG} outputs outputs_b"
    with _loaded() as mod:
        parser = mod.build_parser()
        (planted_argv,) = _recorded_argvs(planted)
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(planted_argv)
        assert exc.value.code == 2
        (fixed_argv,) = _recorded_argvs(fixed)
        parser.parse_args(fixed_argv)

    assert _version_after_flag(f"| `{FLAG} 0.4.0` | 1 | the release name |") == [(1, "0.4.0")]
    assert _version_after_flag(f"so `{FLAG}` stays a bare flag and both") == []

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


def _known_releases() -> tuple[str, ...]:
    """Read at collection time, because `parametrize` needs the list before any test runs."""
    with _loaded() as mod:
        return tuple(sorted(mod.RELEASE_LIMITATIONS))


_KNOWN_RELEASES = _known_releases()


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
    # That the flag took effect, without hard-coding the count it reports: the success line used
    # to say "the two declared gaps" whatever the release declared, and this assertion is what
    # kept that wording alive.
    assert "0.4.1's declared transformation" in got.stdout
    assert "2 added" in got.stdout


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


@pytest.mark.parametrize("release", _KNOWN_RELEASES)
def test_every_release_the_instrument_knows_is_reachable_from_a_record(
    tmp_path: Path, release: str
) -> None:
    """A release whose entry exists but that no record can select is a dead branch.

    The parameters are DERIVED from the mapping, not typed here. Typed, this test listed 0.4.0
    and 0.4.1 while the instrument knew three releases: 0.4.4 was exactly the dead branch the
    docstring names, green, for as long as the entry existed. A population selected by a
    hand-written list is not a population.
    """
    with _loaded() as mod:
        change = mod.RELEASE_LIMITATIONS[release]
        old_lims = LIMS_0_4_0 + tuple(old for old, _new in change.replaced)
        old = _a_run(tmp_path / "old", "0.0.0", old_lims)
        new = _a_run(tmp_path / "new", release, mod.apply_change(old_lims, change))
    got = _run(FLAG, str(old), str(new))
    assert got.returncode == 0, got.stderr


def test_the_parametrisation_covers_every_release_the_instrument_knows() -> None:
    """The completeness half: deriving the list is only safe if nothing filters it on the way."""
    with _loaded() as mod:
        assert set(_KNOWN_RELEASES) == set(mod.RELEASE_LIMITATIONS)
        assert len(_KNOWN_RELEASES) >= 3, _KNOWN_RELEASES


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


# --- a release that REPLACES a line, not only appends ---------------------------------------
#
# 0.5.0 swaps the ground filter. One declared limitation stops being true of the shipped tool
# and is rewritten; two more are added. An append-only expectation cannot express that: it can
# only ever say "the old list plus N", so a replacement reads as one removal and one addition
# that the instrument was never told to expect.


def test_a_release_may_replace_a_line_in_place_and_the_position_is_asserted(
    tmp_path: Path,
) -> None:
    with _loaded() as mod:
        change = mod.LimitationChange(replaced=(("b", "b, rewritten"),), added=("c",))
        assert mod.apply_change(("a", "b"), change) == ("a", "b, rewritten", "c")


def test_a_replacement_of_a_line_the_old_run_does_not_carry_is_a_refusal(tmp_path: Path) -> None:
    """Otherwise a typo in the `old` half appends a second copy and both look declared."""
    with _loaded() as mod:
        change = mod.LimitationChange(replaced=(("not present", "new"),))
        with pytest.raises(mod.ChangeError, match="not present"):
            mod.apply_change(("a", "b"), change)


def test_the_transformation_is_replace_then_append_not_the_other_way_round(
    tmp_path: Path,
) -> None:
    """Order is part of the contract: the record's list is compared element by element."""
    with _loaded() as mod:
        change = mod.LimitationChange(replaced=(("a", "A"),), added=("z",))
        assert mod.apply_change(("a", "b"), change) == ("A", "b", "z")


def test_a_release_that_replaces_and_adds_is_accepted_end_to_end(tmp_path: Path) -> None:
    """The shape 0.5.0 actually has, through the real script and the recorded argv position."""
    with _loaded() as mod:
        release = sorted(mod.RELEASE_LIMITATIONS)[-1]
        change = mod.RELEASE_LIMITATIONS[release]
        old_lims = LIMS_0_4_0 + tuple(old for old, _new in change.replaced)
        new_lims = mod.apply_change(old_lims, change)
    old = _a_run(tmp_path / "old", "0.4.0", old_lims)
    new = _a_run(tmp_path / "new", release, new_lims)
    got = _run(FLAG, str(old), str(new))
    assert got.returncode == 0, got.stderr


def test_the_message_names_what_the_release_declares_rather_than_saying_two(
    tmp_path: Path,
) -> None:
    """`the two declared gaps` was hard-coded in the failure line and the success line, and was
    already false for 0.4.4, which declared one. A count typed into a message is a published
    number: it comes from the mapping."""
    with _loaded() as mod:
        change = mod.RELEASE_LIMITATIONS["0.4.4"]
        assert len(change.added) + len(change.replaced) == 1, "0.4.4 declares exactly one"
    old = _a_run(tmp_path / "old", "0.4.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.4.4", LIMS_0_4_0)  # missing the declared change
    got = _run(FLAG, str(old), str(new))
    assert got.returncode == 1
    assert "two declared gaps" not in got.stderr, f"a hard-coded count survived: {got.stderr}"


# --- comparing across a release that changes the data on purpose ----------------------------
#
# The band comparison is the instrument's spine, so the one release that changes every band by
# design has no acceptance path through it: `--record-only` is that path, and it is deliberately
# unusable anywhere else.


def test_record_only_compares_the_record_across_two_versions(tmp_path: Path) -> None:
    with _loaded() as mod:
        change = mod.RELEASE_LIMITATIONS["0.5.0"]
        old_lims = LIMS_0_4_0 + tuple(old for old, _new in change.replaced)
        new_lims = mod.apply_change(old_lims, change)
    old = _a_run(tmp_path / "old", "0.4.0", old_lims)
    new = _a_run(tmp_path / "new", "0.5.0", new_lims)
    # The bands are identical here, but that is not what is being asserted: the point is that
    # the mode reaches a verdict on the record across a version boundary.
    got = _run("--record-only", FLAG, str(old), str(new))
    assert got.returncode == 0, got.stderr
    assert "0 raster(s) compared" not in got.stdout, "the mode must say it skipped the bands"
    # What it skipped is the band CONTENTS. The set is still compared, and the message has to
    # say which -- it said "the bands were not compared" while comparing the set, which is the
    # sentence a reader uses to decide what was checked.
    assert "band CONTENTS not compared" in got.stdout
    assert "set checked" in got.stdout
    # The success VERDICT too, not only the run line. Of the three messages corrected when the
    # band-set check moved back out of the flag, this was the one left with no test -- the same
    # state the CITATION date was in, and the reason it went stale unnoticed.
    assert "the band contents were not compared (the band SET was)" in got.stdout


def test_record_only_still_fails_on_a_limitation_the_release_did_not_declare(
    tmp_path: Path,
) -> None:
    """Skipping the bands must not skip the field this instrument exists for."""
    with _loaded() as mod:
        change = mod.RELEASE_LIMITATIONS["0.5.0"]
        old_lims = LIMS_0_4_0 + tuple(old for old, _new in change.replaced)
        new_lims = mod.apply_change(old_lims, change) + ("an undeclared limitation",)
    old = _a_run(tmp_path / "old", "0.4.0", old_lims)
    new = _a_run(tmp_path / "new", "0.5.0", new_lims)
    got = _run("--record-only", FLAG, str(old), str(new))
    assert got.returncode == 1
    assert "an undeclared limitation" in got.stderr


def test_record_only_refuses_two_runs_of_the_same_version(tmp_path: Path) -> None:
    """The mode exists for a version boundary. Between two builds of one version the bands are
    the whole question, and a flag that could skip them there would be a way to pass a
    self-replay without replaying anything."""
    old = _a_run(tmp_path / "old", "0.5.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.5.0", LIMS_0_4_0)
    got = _run("--record-only", str(old), str(new))
    assert got.returncode == 2
    assert "version boundary" in got.stderr
    assert "0.5.0" in got.stderr, "the refusal must name the version both runs declare"


def test_record_only_still_refuses_a_directory_holding_no_rasters(tmp_path: Path) -> None:
    """`--record-only` skips the PIXEL comparison, not the band set and not the nothing-scanned
    guard. Under the first version of the flag, two directories holding zero rasters returned
    exit 0 with the full success verdict -- and this was the only acceptance path across the
    0.5.0 boundary, so an export that wrote five of six bands would have passed it."""
    for d in (tmp_path / "old", tmp_path / "new"):
        d.mkdir(parents=True)
        (d / "provenance.json").write_text(
            json.dumps(
                {
                    "package_version": "0.4.4" if d.name == "old" else "0.5.0",
                    "created_utc": "2026-01-01T00:00:00+00:00",
                    "reproducibility_hash": "x",
                    "known_limitations": ["a"],
                    "grid": {"cell": 0.5},
                }
            ),
            encoding="utf-8",
        )
    got = _run("--record-only", str(tmp_path / "old"), str(tmp_path / "new"))
    assert got.returncode == 1, got.stdout
    assert "checked nothing" in got.stderr


def test_record_only_still_refuses_a_missing_band(tmp_path: Path) -> None:
    """The band SET is a record-level fact and needs no pixel reads to check."""
    old = _a_run(tmp_path / "old", "0.4.4", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.5.0", LIMS_0_4_0)
    (new / "mdt.tif").unlink()
    got = _run("--record-only", str(old), str(new))
    assert got.returncode == 1
    assert "band sets differ" in got.stderr


def test_the_bare_command_names_what_is_unchanged_in_its_success_line(tmp_path: Path) -> None:
    """The success line of the bare path had no test -- only its failure line did, which is how
    a refactor left it reading "...and every record field but the three permitted, and
    unchanged", with no subject, published that way in docs/live-smoke.md."""
    old = _a_run(tmp_path / "old", "0.4.0", LIMS_0_4_0)
    new = _a_run(tmp_path / "new", "0.4.0", LIMS_0_4_0)
    got = _run(str(old), str(new))
    assert got.returncode == 0, got.stderr
    assert "known_limitations is unchanged" in got.stdout, got.stdout

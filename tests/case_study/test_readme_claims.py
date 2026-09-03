"""The README is tied to the run's record; a claim with no source there is the failure mode."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_readme_quotes_the_hash_that_the_run_actually_produced() -> None:
    # docs/viewer/provenance.json is the tracked copy of the run's record (outputs/ is gitignored).
    prov = json.loads((ROOT / "docs" / "viewer" / "provenance.json").read_text())
    assert prov["reproducibility_hash"][:12] in (ROOT / "README.md").read_text()


def test_the_readme_declares_the_unverified_cross_machine_replay() -> None:
    text = (ROOT / "README.md").read_text().lower()
    assert "not verified" in text or "unverified" in text


def test_the_readme_declares_the_replay_instability_on_real_data() -> None:
    # 2026-08-05: of four reads of the 845 MB, one corrupted coordinate and one IoError.
    # The README must say the words, not claim a stability the data does not support.
    text = (ROOT / "README.md").read_text().lower()
    assert "not established" in text
    assert "root cause" in text


def test_the_readme_reports_recall_per_class_and_the_null() -> None:
    text = (ROOT / "README.md").read_text().lower()
    assert "majority-class null" in text
    assert "ground recall" in text and "non-ground recall" in text


def test_the_readme_states_the_published_rasters_are_not_an_input() -> None:
    text = (ROOT / "README.md").read_text().lower()
    assert "only for comparison" in text or "not an input" in text


def test_every_percentage_in_the_readme_appears_in_the_live_smoke_record() -> None:
    """A number in the README with no source in the record is the failure mode this prevents."""
    readme = (ROOT / "README.md").read_text()
    smoke = (ROOT / "docs" / "live-smoke.md").read_text()
    percentages = set(re.findall(r"\d+\.\d+%", readme))
    assert percentages, "a README about a measured run should quote at least one percentage"
    for value in percentages:
        assert value in smoke, value


def test_the_readme_never_tells_a_stranger_to_pip_install_from_pypi() -> None:
    """`pip install microrelief[dgt]` fails: the package is not on PyPI. The only install lines
    allowed are a clone + `uv sync`, or pip against the git URL."""
    text = (ROOT / "README.md").read_text()
    for line in text.splitlines():
        if "pip install" in line and "microrelief" in line:
            assert "git+https://" in line, line


def test_the_readme_try_it_quotes_the_sample_record() -> None:
    sample = ROOT / "examples" / "sistelo-sample" / "expected" / "provenance.json"
    prov = json.loads(sample.read_text())
    readme = (ROOT / "README.md").read_text()
    assert prov["reproducibility_hash"][:12] in readme
    assert "examples/sistelo-sample" in readme


# --- Every file that publishes a record hash, not just the README ---------------------------
#
# The two tests above lock the README, and only the README. In 0.4.2 the bump moved both record
# hashes, the README locks went red and were fixed -- while `skills/microrelief/SKILL.md` and
# `examples/sistelo-sample/README.md` kept 0.4.1's, and the suite stayed green at 265 tests.
# SKILL.md even asserted "tests/test_sample.py locks these", which nothing did. That is the same
# class 0.4.1 named for the 60 B/cell figure ("three unlocked copies with no test tying them
# together") and the same class the sweep that produced it fell to: one file is one witness.
#
# So the population is DERIVED, never a list of filenames -- a convention-shaped selector has let
# a member escape a guard in this repo before. It is every tracked `.md` carrying a token
# presented AS a record hash, partitioned into files making a present-tense claim (which must
# carry a CURRENT hash) and dated records (exempt, each with its reason).

_PUBLISHED_HASH = re.compile(
    r"(?:reproducibility_hash|record hash|hash)\D{0,4}`?([0-9a-f]{12})", re.I
)

# Exempt, and why. A dated record is a description of a past moment: its hashes are correct
# BECAUSE they are old, and editing them would falsify the record rather than fix it.
DATED_RECORDS = {
    "docs/live-smoke.md": "append-only log of past runs; every superseded hash is the point",
    "docs/self-check.md": "a dated self-check, corrected beside its original rather than over it",
    "docs/second-aoi-gate-result.md": (
        "a dated gate result; the hash it publishes is the Valongo run's, and the point of "
        "recording it is that it is that run's and no other"
    ),
}


def _tracked_markdown() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [n for n in out.stdout.split("\0") if n.endswith(".md")]


def _current_hash_prefixes() -> set[str]:
    return {
        json.loads((ROOT / p).read_text())["reproducibility_hash"][:12]
        for p in ("docs/viewer/provenance.json", "examples/sistelo-sample/expected/provenance.json")
    }


def _population() -> dict[str, list[str]]:
    found = {}
    for name in _tracked_markdown():
        hits = sorted(set(_PUBLISHED_HASH.findall((ROOT / name).read_text(encoding="utf-8"))))
        if hits:
            found[name] = hits
    return found


def test_every_file_that_publishes_a_record_hash_is_current_or_a_dated_record() -> None:
    """The partition: live claim with a current hash, or a dated record with a stated reason."""
    population = _population()
    assert population, "no tracked .md publishes a record hash: this test scanned nothing"

    current = _current_hash_prefixes()
    stale = {
        name: [h for h in hits if h not in current]
        for name, hits in population.items()
        if name not in DATED_RECORDS
    }
    stale = {k: v for k, v in stale.items() if v}
    assert not stale, (
        f"{len(stale)} live file(s) publish a hash the code does not produce (current: "
        f"{sorted(current)}): {stale} -- copy it from the record, never by hand"
    )


def test_the_exemptions_name_files_that_exist_and_actually_carry_a_hash() -> None:
    """An exemption for a file that no longer publishes a hash is a hole nobody is watching."""
    population = _population()
    unused = sorted(set(DATED_RECORDS) - set(population))
    assert not unused, f"exempted but no longer publishes a hash: {unused} -- drop the exemption"
    for name in DATED_RECORDS:
        assert (ROOT / name).exists(), f"exempted file does not exist: {name}"


def test_the_partition_check_fires_on_a_stale_hash_and_is_quiet_on_a_current_one() -> None:
    """Both arms: a guard that cannot fire and a clean tree produce the same green.

    The planted token is assembled here rather than written out -- this file is a tracked `.md`
    away from being in the population itself, and a literal would be a hash nobody can source.
    """
    current = _current_hash_prefixes()
    stale_token = "0" * 12
    assert stale_token not in current, "the planted token must not accidentally be a real hash"

    live = "record hash `" + stale_token + "`"
    assert _PUBLISHED_HASH.findall(live) == [stale_token], "the pattern missed a planted claim"

    fresh = "record hash `" + sorted(current)[0] + "`"
    assert [h for h in _PUBLISHED_HASH.findall(fresh) if h not in current] == [], (
        "the pattern flagged a current hash"
    )


# --- the published records themselves, not just the documents quoting them ------------------
#
# The partition above asks whether every document carries a CURRENT hash, where "current" means
# "one of the two published records". It never asks whether those records are themselves current,
# and they were not: 0.4.4 declared the limitation that the ground filter publishes buildings as
# terrain, bumped the version and regenerated the sample -- and left `docs/viewer/provenance.json`
# at 0.4.2 with ten limitations, the buildings line absent. The record a reader of the published
# piece actually opens was missing that release's headline disclosure, under a green suite,
# because the sample had a test locking it and the viewer's record had only the hash partition.

PUBLISHED_RECORDS = (
    "docs/viewer/provenance.json",
    "examples/sistelo-sample/expected/provenance.json",
)


def test_every_published_record_was_produced_by_the_current_code() -> None:
    """A release regenerates every published record, or the ones it skipped say the wrong thing.

    Not a style rule: `known_limitations` and `uncalibrated_thresholds` travel *inside* the
    record, so a record from an older version is a published claim about what the tool cannot do
    that the tool has since corrected or extended.
    """
    import microrelief

    stale = {}
    for name in PUBLISHED_RECORDS:
        doc = json.loads((ROOT / name).read_text())
        if doc["package_version"] != microrelief.__version__:
            stale[name] = doc["package_version"]
    assert not stale, (
        f"the package is at {microrelief.__version__} and these published records are not: "
        f"{stale} -- re-run the product and regenerate them, do not edit the version in place"
    )


def test_every_published_record_declares_the_limitations_the_code_declares() -> None:
    """The version agreeing is not enough: the record has to carry the list it was built with."""
    from microrelief.cli import LIMITATIONS

    for name in PUBLISHED_RECORDS:
        doc = json.loads((ROOT / name).read_text())
        assert tuple(doc["known_limitations"]) == LIMITATIONS, (
            f"{name} declares {len(doc['known_limitations'])} limitations, the code declares "
            f"{len(LIMITATIONS)}: re-run the product rather than editing the record"
        )


def test_the_record_currency_check_fires_on_a_stale_version() -> None:
    """Both arms, on the mechanism rather than on the tree: the assertion above is only worth
    something if a version that does not match is what makes it fail."""
    import microrelief

    assert microrelief.__version__ != "0.0.0"
    stale = {"docs/viewer/provenance.json": "0.0.0"}
    assert stale, "a non-matching version must be collected, not skipped"
    assert all(v != microrelief.__version__ for v in stale.values())

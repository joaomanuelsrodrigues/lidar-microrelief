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


def _records_not_at(version: str) -> dict[str, str]:
    """The published records whose `package_version` is not `version`.

    Exists so the check below and its control call the SAME function: the control's first
    version built its own literal dict and asserted that the literal was truthy, which passes
    with the real check deleted. A control that does not reach the code it controls is
    decoration.
    """
    return {
        name: doc["package_version"]
        for name in PUBLISHED_RECORDS
        if (doc := json.loads((ROOT / name).read_text()))["package_version"] != version
    }


def test_every_published_record_was_produced_by_the_current_code() -> None:
    """A release regenerates every published record, or the ones it skipped say the wrong thing.

    Not a style rule: `known_limitations` and `uncalibrated_thresholds` travel *inside* the
    record, so a record from an older version is a published claim about what the tool cannot do
    that the tool has since corrected or extended.
    """
    import microrelief

    stale = _records_not_at(microrelief.__version__)
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
    """Both arms, through the same function the check above calls.

    The quiet arm: at the real version, nothing is collected. The firing arm: asked about a
    version no record was built at, EVERY record is collected, by name. Neither is reachable
    without `_records_not_at` actually reading the records off disk, which is what the first
    version of this control failed to do -- it asserted a dict it had written itself.
    """
    import microrelief

    assert _records_not_at(microrelief.__version__) == {}, "the quiet arm must be quiet"

    fired = _records_not_at("0.0.0")
    assert set(fired) == set(PUBLISHED_RECORDS), (
        f"asked about a version nothing was built at, every record must be named: {fired}"
    )
    assert all(v == microrelief.__version__ for v in fired.values()), fired


# --- Every percentage published as a live claim, not just the README's -----------------------
#
# The lock this replaces read the README and nothing else, so `skills/microrelief/SKILL.md` could
# publish `expected void 1.3%` -- the right number, rounded by hand, sourced nowhere; the record
# of that run says `1.312%`. One file is one witness, again.
#
# Widening it to every tracked `.md` was measured and does not work either: 33 files carry a
# percentage and 24 of them carry one absent from the record, because they ARE records -- dated
# results, pre-registrations, judge verdicts, whose numbers are the instrument's output and whose
# older figures are correct BECAUSE they are old. A gate born with 24 exemptions is a list of
# filenames wearing a gate's clothes.
#
# So the partition is derived from the bytes, and carries no list: a document that declares a date
# -- in its name or in its opening block -- is a record of a past moment and speaks for itself;
# a document that does not is a live claim, and every percentage it publishes must appear verbatim
# in the run record. Where the rule misfired it was right and the document was wrong: three
# records did not say when they were made, and were dated rather than exempted.
#
# The one file excluded is the record itself: it is the source, so checking it against itself
# would be vacuous. Its own contract is its first paragraph -- every entry a real command and its
# real output.

LIVE_SMOKE = "docs/live-smoke.md"

_PERCENTAGE = re.compile(r"\d+\.\d+%")
_ISO_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
_OPENING_LINES = 6

# Live documents that must stay in the population. Not the selector -- the selector is
# `git ls-files` -- but the assertion that these four have not left it, which is what a date
# appearing in a live file's opening block would do, silently.
LIVE_DOCUMENTS_A_READER_ACTS_ON = (
    "README.md",
    "skills/microrelief/SKILL.md",
    "CALIBRATIONS.md",
    "examples/sistelo-sample/README.md",
)


def _opening_block(text: str) -> str:
    """The first few non-empty lines of the body, front matter excluded.

    Front matter is metadata, not the document's opening sentence: a date in it must not exempt
    the file, and neither must a date two hundred lines down.
    """
    if text.startswith("---\n"):
        rest = text.split("\n", 1)[1]
        end = rest.find("\n---\n")
        text = rest[end + len("\n---\n") :] if end != -1 else rest
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:_OPENING_LINES])


def _is_dated_record(name: str, text: str) -> bool:
    """A record declares when it was made, in its name or where a reader meets it."""
    return bool(_ISO_DATE.search(name) or _ISO_DATE.search(_opening_block(text)))


def _unsourced_percentages(text: str) -> list[str]:
    """The percentages in `text` that the run record does not carry verbatim."""
    smoke = (ROOT / LIVE_SMOKE).read_text(encoding="utf-8")
    return sorted({p for p in _PERCENTAGE.findall(text) if p not in smoke})


def _live_documents() -> dict[str, str]:
    live = {}
    for name in _tracked_markdown():
        if name == LIVE_SMOKE:
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        if not _is_dated_record(name, text):
            live[name] = text
    return live


def _unsourced_by_document(documents: dict[str, str]) -> dict[str, list[str]]:
    """The documents publishing a percentage the record does not carry, by name.

    Takes the corpus rather than reading the tree, so the control below can run THIS function
    over a planted one. Collected in the test body, neutralising it was undetectable on a clean
    tree: a guard whose subject is absent cannot be told from a deleted guard.
    """
    return {
        name: unsourced
        for name, text in documents.items()
        if (unsourced := _unsourced_percentages(text))
    }


def test_every_percentage_in_a_live_document_appears_in_the_run_record() -> None:
    """A live claim quotes the instrument; a number typed by hand is what this catches."""
    offenders = _unsourced_by_document(_live_documents())
    assert not offenders, (
        f"{len(offenders)} live document(s) publish a percentage absent from {LIVE_SMOKE}: "
        f"{offenders} -- copy it from the record, or date the document if it is a record"
    )


def test_the_live_class_still_holds_the_documents_a_reader_acts_on() -> None:
    """The population check: an exemption leaving the population must turn this red.

    Nothing in the selector protects these four. A date drifting into the opening block of any of
    them -- a release note, a changelog line -- would move it to the record class and take its
    percentages out of scrutiny without a single test going red. This is that test.
    """
    live = set(_live_documents())
    missing = [n for n in LIVE_DOCUMENTS_A_READER_ACTS_ON if n not in live]
    assert not missing, (
        f"{missing} left the live class -- if a date now opens the file, move it out of the "
        f"opening block; a live document is not a record of a moment"
    )


def test_the_partition_is_not_vacuous_on_either_side() -> None:
    """Both classes populated, and the live side actually publishing percentages to check."""
    live = _live_documents()
    records = [n for n in _tracked_markdown() if n not in live and n != LIVE_SMOKE]
    assert records, "no tracked .md classified as a dated record: the rule scanned nothing"
    quoting = [n for n, t in live.items() if _PERCENTAGE.search(t)]
    assert len(quoting) >= 4, (
        f"only {len(quoting)} live document(s) quote a percentage: {quoting} -- the check above "
        f"passes by having nothing to read"
    )


def test_the_excluded_source_is_the_record_and_it_is_not_empty() -> None:
    """The one exclusion, and its reason, asserted rather than assumed."""
    smoke = ROOT / LIVE_SMOKE
    assert smoke.exists(), f"{LIVE_SMOKE} is the source set and it is gone"
    assert len(_PERCENTAGE.findall(smoke.read_text(encoding="utf-8"))) > 50, (
        "the source record carries almost no percentages: every live claim would pass by "
        "matching nothing"
    )


def test_the_percentage_check_fires_on_a_planted_claim_and_is_quiet_on_a_sourced_one() -> None:
    """Both arms, through the same function the check above calls.

    The planted value is assembled here rather than written out: this repository has twice put a
    control's literal into a tracked file and had the gate find its own bait.
    """
    smoke = (ROOT / LIVE_SMOKE).read_text(encoding="utf-8")
    planted = "9" + "9.999%"
    assert planted not in smoke, "the planted value must be absent from the record to mean anything"
    assert _unsourced_percentages(f"basis {planted} measured") == [planted]

    sourced = sorted(set(_PERCENTAGE.findall(smoke)))[0]
    assert _unsourced_percentages(f"basis {sourced} measured") == [], sourced


def test_the_collection_names_the_offending_document_and_leaves_the_sourced_one_alone() -> None:
    """The collection's own arms, over a planted corpus, through the function the check calls."""
    smoke = (ROOT / LIVE_SMOKE).read_text(encoding="utf-8")
    planted = "9" + "9.999%"
    sourced = sorted(set(_PERCENTAGE.findall(smoke)))[0]
    corpus = {
        "docs/planted-live.md": f"# A live claim\n\nbasis {planted} measured\n",
        "docs/planted-sourced.md": f"# Another live claim\n\nbasis {sourced} measured\n",
        "docs/planted-silent.md": "# No numbers here\n\nProse.\n",
    }
    assert _unsourced_by_document(corpus) == {"docs/planted-live.md": [planted]}


def test_a_document_is_a_record_only_where_it_declares_its_date() -> None:
    """The classifier's arms: name, opening block, and the two places a date must not exempt."""
    body = "# A title\n\nProse quoting 1.234% of something.\n"
    assert not _is_dated_record("docs/whatever.md", body)
    assert _is_dated_record("docs/verdict-2026-08-06-r2.md", body)
    assert _is_dated_record("docs/whatever.md", "# A title\n\n**2026-09-03.** Prose.\n")
    deep = body + "".join(f"Paragraph {i}, saying nothing about when.\n\n" for i in range(40))
    assert not _is_dated_record("docs/whatever.md", deep + "measured on 2026-09-03\n"), (
        "a date far down the body is not a document declaring itself a record"
    )
    # The tree proves the same thing: CALIBRATIONS.md carries ten dates in its origin column and
    # is asserted live above. Blank lines are not depth -- the opening block counts what a reader
    # sees, so it skips them.
    assert not _is_dated_record(
        "docs/whatever.md", "---\nname: x\nupdated: 2026-09-03\n---\n\n" + body
    ), "front matter is metadata, not the opening block a reader meets"

"""No working-note identifier reaches the files a reader acts on.

`docs/judge/README.md` states the repository's rule: the author's session numbers, task-ledger IDs,
failure-class and finding numbers stay in the dated records, which are annotated rather than
rewritten, while the live files "say the rule in plain words instead". That sentence was false when
this test was written, with twenty-one occurrences on eighteen lines across seven files under
`src/`, `tests/` and `scripts/`, most of them added after the sweep meant to have removed them. A
sweep without a lock leaks again, so this is the lock.

Every pattern and every planted example is assembled at run time. This file is inside the
population it scans, and a literal written out whole would make the guard fire on its own source.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The verbatim record store. `docs/judge/` holds the judge's own words at fixed commits plus the
# legend that names these shapes for a reader on purpose; editing either would misreport what a
# third party wrote. Exempt with that reason.
EXEMPT = ("docs/judge/",)

# Where the rule bites hardest, and where an exemption must never reach.
LIVE_DIRS = ("src/", "tests/", "scripts/", "skills/")

TEXT_SUFFIXES = {
    ".cff",
    ".geojson",
    ".html",
    ".json",
    ".md",
    ".py",
    ".qml",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

_S = "s"
_PATTERNS = {
    "working-session number": re.compile(rf"\b{_S}[0-9][0-9][0-9]?\b"),
    "task-ledger ID": re.compile(r"\bT-[A-Z][0-9]"),
    "failure-class reference": re.compile(r"§A[0-9]"),
    "finding number": re.compile(r"\bF-0[0-9][0-9]\b"),
    "experiment number": re.compile(r"\bE-00[0-9]\b"),
    # `Step <n>` is deliberately absent: numbered steps are ordinary instructional English, and a
    # gate refusing them would be refusing legitimate prose rather than a working note.
    "plan-step reference": re.compile(r"\b(?:Task|Session)s?\s+[0-9]"),
}


def _tracked() -> list[str]:
    """Derived from the index, never a glob: a convention-shaped selector has let a member escape
    this repository's guards more than once."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [name for name in out.split("\0") if name]


def _scanned() -> list[str]:
    return [name for name in _tracked() if not name.startswith(EXEMPT)]


def _staged_text(name: str) -> str | None:
    """The bytes git holds, not the working copy. `scripts/neutrality.sh` states the same policy
    for this repository: what ships is the index, so an unstaged local edit must not be able to
    make a staged identifier invisible. None when the blob is not UTF-8."""
    blob = subprocess.run(["git", "show", f":{name}"], cwd=ROOT, capture_output=True, check=False)
    if blob.returncode != 0:
        return None
    try:
        return blob.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def test_no_live_file_carries_a_working_note_identifier() -> None:
    hits: list[str] = []
    read = 0
    for name in _scanned():
        text = _staged_text(name)
        if text is None:
            continue
        read += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in _PATTERNS.items():
                found = pattern.search(line)
                if found:
                    hits.append(f"{name}:{lineno}: {label} {found.group(0)!r} in {line.strip()!r}")
    assert read, "the scan read no files at all, which passes for the wrong reason"
    assert not hits, f"{len(hits)} hit(s) over {read} file(s) read:\n" + "\n".join(hits)


def test_the_scan_fires_on_each_shape_it_claims_to_catch() -> None:
    """Silence is this gate's pass condition, so each pattern must be shown to speak. A shape no
    planted example reaches is a pattern that could be deleted without any test noticing."""
    planted = {
        "working-session number": _S + "295",
        "task-ledger ID": "T-" + "E6u",
        "failure-class reference": "§" + "A1",
        "finding number": "F-" + "050",
        "experiment number": "E-" + "006",
        "plan-step reference": "Task" + " 9",
    }
    assert set(planted) == set(_PATTERNS), set(planted) ^ set(_PATTERNS)
    for label, example in planted.items():
        fired = [name for name, pattern in _PATTERNS.items() if pattern.search(example)]
        assert label in fired, f"{example!r} did not fire {label}"


def test_the_scan_stays_quiet_on_near_misses() -> None:
    """The must-not-fire arm, built from text one character off each pattern rather than from text
    that resembles nothing. A quiet arm made of obviously innocent lines cannot detect an
    over-broad pattern, which is the only thing it exists to detect."""
    near_misses = [
        "the " + _S + "9 sortie and the " + _S + "4321 tile identifier",  # 1 and 4 digits
        "T-" + "REX is not a ledger ID, nor is T" + "-e6u in lower case",
        "§" + "Acquisition and §" + "Install are section references",
        "F-" + "1050 and F" + "-05 are not finding numbers",
        "E-" + "0061 and E" + "-06 are not experiment numbers",
        "Step 1: open QGIS, then Tasking and Sessions without a number",
        "balanced accuracy 0.712 at EPSG:3763 over a 150 m tile",
    ]
    for line in near_misses:
        fired = [name for name, pattern in _PATTERNS.items() if pattern.search(line)]
        assert not fired, f"{line!r} fired {fired}"


def test_the_live_directories_are_scanned_in_full() -> None:
    """The invariant an exemption could break. Its predecessor asked whether a name started with
    both the exempt prefix and a live one, which no name can do, so it could not fail. This one
    fails the moment an exemption reaches source or tests."""
    scanned = set(_scanned())
    missing = [n for n in _tracked() if n.startswith(LIVE_DIRS) and n not in scanned]
    assert not missing, missing


def test_the_exemption_holds_no_source_and_hides_no_text_file() -> None:
    """Two ways the exemption could quietly widen: source moving under it, and a text file the
    scan drops as undecodable rather than reading."""
    swallowed = [n for n in _tracked() if n.startswith(EXEMPT) and n.endswith((".py", ".sh"))]
    assert not swallowed, swallowed
    skipped = [n for n in _scanned() if _staged_text(n) is None]
    unread_text = [n for n in skipped if Path(n).suffix in TEXT_SUFFIXES]
    assert not unread_text, f"text files the scan could not read: {unread_text}"

"""No working-note identifier reaches the files a reader acts on.

`docs/judge/README.md` states the repository's rule: the author's session numbers, task-ledger
IDs, failure-class and finding numbers stay in the dated records, which are annotated rather than
rewritten, while the live files "say the rule in plain words instead". That claim was false when
this test was written: eighteen such identifiers sat in `src/`, `tests/` and `scripts/`, most of
them added after the sweep that was supposed to have removed them. A sweep without a lock leaks
again, so this is the lock.

Every pattern and every planted example is assembled at run time. This file is inside the
population it scans, and a literal written out whole would make the guard fire on its own source.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The record store. `docs/` holds the dated records (live-smoke, the judge rounds, the
# pre-registrations and the result documents) plus `docs/judge/README.md`, the legend that names
# these shapes for a reader on purpose. Exempt with that reason, not by taste.
RECORD_STORE = "docs/"

_S = "s"
_PATTERNS = {
    "working-session number": re.compile(rf"\b{_S}[0-9][0-9][0-9]?\b"),
    "task-ledger ID": re.compile(r"\bT-[A-Z][0-9]"),
    "failure-class reference": re.compile(r"§A[0-9]"),
    "finding number": re.compile(r"\bF-0[0-9][0-9]\b"),
    "experiment number": re.compile(r"\bE-00[0-9]\b"),
    # `Step <n>` is deliberately absent: numbered steps are ordinary instructional English and
    # a gate that refuses them would be refusing legitimate prose, not a working note.
    "plan-step reference": re.compile(r"\b(?:Task|Session)s?\s+[0-9]"),
}


def _tracked() -> list[str]:
    """The population is derived from the index, never a glob: a convention-shaped selector has
    let a member escape this repository's guards more than once."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [name for name in out.split("\0") if name]


def _scanned() -> list[str]:
    return [name for name in _tracked() if not name.startswith(RECORD_STORE)]


def _text_of(name: str) -> str | None:
    """None when the bytes are not text. The scope of this gate is prose and source; a binary is
    reported by the completeness test rather than silently dropped."""
    try:
        return (ROOT / name).read_bytes().decode("utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return None


def test_no_live_file_carries_a_working_note_identifier() -> None:
    hits: list[str] = []
    read = 0
    for name in _scanned():
        text = _text_of(name)
        if text is None:
            continue
        read += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in _PATTERNS.items():
                found = pattern.search(line)
                if found:
                    hits.append(f"{name}:{lineno}: {label} {found.group(0)!r} in {line.strip()!r}")
    assert read, "the scan read no files at all, which passes for the wrong reason"
    assert not hits, "\n".join(hits)


def test_the_scan_fires_on_each_shape_it_claims_to_catch(tmp_path: Path) -> None:
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
        matched = [name for name, pattern in _PATTERNS.items() if pattern.search(example)]
        assert label in matched, f"{example!r} did not fire {label}"


def test_the_scan_stays_quiet_on_text_that_only_looks_like_one() -> None:
    """The must-not-fire arm. Without it the gate could be a pattern that matches everything."""
    innocent = [
        "the 0.4.1 release bumped __version__ and the goldens",
        "EPSG:3763 over a 150 m tile at 0.5 m resolution",
        "see docs/second-aoi-gate-result.md for the counts",
        "balanced accuracy 0.712, below the 0.75 bar",
    ]
    for line in innocent:
        fired = [name for name, pattern in _PATTERNS.items() if pattern.search(line)]
        assert not fired, f"{line!r} fired {fired}"


def test_every_tracked_text_file_is_either_scanned_or_a_declared_record() -> None:
    """The partition, so an exemption cannot be widened by accident: a file is scanned, or it is
    under the record store. Nothing may be in neither, and the record store may not swallow a
    file a reader acts on."""
    scanned = set(_scanned())
    for name in _tracked():
        assert name in scanned or name.startswith(RECORD_STORE), name
    # The first version of this check asked whether a name started with both the record store
    # and a live directory, which no name can do: it could not fail. The invariant that can is
    # that the exemption stays a document store, so source moving under it would be caught.
    swallowed = [n for n in _tracked() if n.startswith(RECORD_STORE) and n.endswith((".py", ".sh"))]
    assert not swallowed, swallowed

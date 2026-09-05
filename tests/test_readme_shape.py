"""The README's shape is measured, not asserted.

Ten comparable repositories were read before this file was written: six from the domain (PDAL,
WhiteboxTools, laspy, RichDEM, xDEM, pdemtools) and four for voice (demcoreg, nanoGPT, llm,
pyroSAR). Their median README is 718 words, their median emphasis 0.51 bold spans per 100 words.
Not one of the ten uses a dash as sentence punctuation, and not one carries a date. This README
carried 4282 words, 61 dashes used as punctuation, 13 dates and 1.61 bold spans per 100 words,
which is what these checks exist to keep it from drifting back to.

The dash check is one notch stricter than that measurement: it counts en-dashes too, and the
previous README's single en-dash was a numeric range rather than an aside. A range reads as well
written out, and a guard that has to tell a range from an aside is a classifier nobody needs, so
the count here is 62 where the measured rule says 61. The two numbers are kept apart on purpose.

Population: `README.md`, and only it. That is the whole rule, not a shortcut. Most tracked markdown
in this repository carries dashes and dates and is meant to: those files are dated records and
depth pages, and a transcript is allowed to read like a transcript. At the commit that added these
checks the split was 40 of 48 tracked `.md` carrying a dash and 26 carrying a date, re-derivable by
running `_shape` below over `git ls-tree -r --name-only HEAD`. That is a snapshot, not an
invariant. Widening the population is a separate decision needing its own baseline, not a
tightening of this one.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The bounds are the doorway's, not a record of what the file happens to weigh today. The floor is
# the bottom of the length this README was rewritten against, and it exists because every other
# check here passes on an empty file: zero words has no dashes, no dates and no bold. The ceiling
# is the current length plus room for three more declared limitations, at the ~60 words a bullet
# in that section runs to, because the section that has to stay complete is the one that grows: it
# mirrors the record's `known_limitations` one for one. The rewrite aimed at 1000-1500 words and
# landed above it; that miss is recorded in its commit rather than dissolved into this number.
MIN_WORDS = 1000
MAX_WORDS = 1950
MAX_BOLD_PER_100_WORDS = 0.60


def _shape(text: str) -> dict[str, float]:
    """The measurement the checks and their controls share, so neither can drift from the other."""
    words = len(text.split())
    return {
        "words": words,
        "dashes": text.count("—") + text.count("–"),
        "dates": len(re.findall(r"\d{4}-\d{2}-\d{2}", text)),
        "bold_per_100w": (text.count("**") // 2) / words * 100 if words else 0.0,
    }


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_readme_uses_no_dash_as_punctuation() -> None:
    shape = _shape(_readme())
    assert shape["dashes"] == 0, (
        f"{shape['dashes']} em- or en-dash(es) in the README; none of the ten comparators uses one "
        "as sentence punctuation, so a comma, a colon or a full stop is the repair, and a numeric "
        "range is written out"
    )


def test_the_readme_carries_no_dates() -> None:
    shape = _shape(_readme())
    assert shape["dates"] == 0, (
        f"{shape['dates']} date(s) in the README: a measurement keeps its date in the document "
        "that records it, which is where a reader checking the claim is going anyway"
    )


def test_the_readme_stays_a_doorway() -> None:
    shape = _shape(_readme())
    assert MIN_WORDS <= shape["words"] <= MAX_WORDS, (
        f"{shape['words']} words, outside {MIN_WORDS}-{MAX_WORDS}: above it, depth belongs in "
        "docs/, linked; below it, the evidence this README exists to carry has gone missing"
    )
    assert shape["bold_per_100w"] <= MAX_BOLD_PER_100_WORDS, (
        f"{shape['bold_per_100w']:.2f} bold spans per 100 words against "
        f"{MAX_BOLD_PER_100_WORDS}: bold marks a noun, never an argument"
    )


def test_the_shape_measurement_fires_on_each_violation_and_is_quiet_on_the_readme() -> None:
    """Both arms, through the same function the checks above call.

    Each planted violation is assembled at run time rather than written out; the only dash
    literals in this file are the two patterns `_shape` counts. A control that cannot fire and a
    clean README produce the same green.
    """
    clean = _shape(_readme())
    assert clean["dashes"] == 0 and clean["dates"] == 0, "the quiet arm must be quiet"
    assert MIN_WORDS <= clean["words"] <= MAX_WORDS, "the quiet arm must be quiet"

    assert _shape("a sentence " + chr(0x2014) + " and its aside")["dashes"] == 1
    assert _shape("a sentence " + chr(0x2013) + " and its aside")["dashes"] == 1
    assert _shape("measured on 2026-" + "01-01")["dates"] == 1
    assert _shape("word " * (MAX_WORDS + 1))["words"] > MAX_WORDS
    assert _shape("**a** **b** " + "word " * 98)["bold_per_100w"] > MAX_BOLD_PER_100_WORDS

    # The degenerate document: an empty README satisfies every other check here, which is why the
    # floor is one of them.
    empty = _shape("")
    assert empty["dashes"] == 0 and empty["dates"] == 0 and empty["bold_per_100w"] == 0.0
    assert empty["words"] < MIN_WORDS

"""The README is tied to the run's record; a claim with no source there is the failure mode."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_readme_quotes_the_hash_that_the_run_actually_produced() -> None:
    # viewer/provenance.json is the tracked copy of the run's record (outputs/ is gitignored).
    prov = json.loads((ROOT / "viewer" / "provenance.json").read_text())
    assert prov["reproducibility_hash"][:12] in (ROOT / "README.md").read_text()


def test_the_readme_declares_the_unverified_cross_machine_replay() -> None:
    text = (ROOT / "README.md").read_text().lower()
    assert "not verified" in text or "unverified" in text


def test_the_readme_declares_the_replay_instability_on_real_data() -> None:
    # s260: of four reads of the 845 MB, one corrupted coordinate and one IoError.
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

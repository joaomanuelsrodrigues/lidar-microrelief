from pathlib import Path

import microrelief


def test_version_is_exposed() -> None:
    assert microrelief.__version__ == "0.1.0"


def test_rubric_is_committed_before_pipeline_code() -> None:
    """The rubric is a pre-registration: it must exist from the first commit onward."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "RUBRIC.md").exists()
    assert (root / "CALIBRATIONS.md").exists()
    assert (root / "ATTRIBUTION.md").exists()

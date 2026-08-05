import tomllib
from pathlib import Path

import microrelief


def test_version_is_exposed_and_the_two_sources_agree() -> None:
    """`__version__` is not decoration: it goes into `reproducibility_hash` and into every
    exported raster's tags, so it is the only thing that makes a *code* change visible to a
    reader holding an old output. `pyproject.toml` carries the same number for the wheel.

    Asserting a literal here would have to be edited on every bump and checks nothing about the
    relationship. Asserting that the two sources agree checks the thing that can actually go
    wrong — they live in different files and nothing else ties them together.
    """
    root = Path(__file__).resolve().parents[1]
    declared = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    assert microrelief.__version__ == declared
    assert microrelief.__version__, "an empty version would hash and tag as an empty string"


def test_rubric_is_committed_before_pipeline_code() -> None:
    """The rubric is a pre-registration: it must exist from the first commit onward."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "RUBRIC.md").exists()
    assert (root / "CALIBRATIONS.md").exists()
    assert (root / "ATTRIBUTION.md").exists()

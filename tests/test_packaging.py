import json
import subprocess
import sys
import tomllib
from pathlib import Path

import microrelief

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_exposed_and_the_two_sources_agree() -> None:
    """`__version__` is not decoration: it goes into `reproducibility_hash` and into every
    exported raster's tags, so it is the only thing that makes a *code* change visible to a
    reader holding an old output. `pyproject.toml` carries the same number for the wheel.

    Asserting a literal here would have to be edited on every bump and checks nothing about the
    relationship. Asserting that the two sources agree checks the thing that can actually go
    wrong — they live in different files and nothing else ties them together.
    """
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert microrelief.__version__ == declared
    assert microrelief.__version__, "an empty version would hash and tag as an empty string"


def test_rubric_is_committed_before_pipeline_code() -> None:
    """The rubric is a pre-registration: it must exist from the first commit onward."""
    assert (ROOT / "RUBRIC.md").exists()
    assert (ROOT / "CALIBRATIONS.md").exists()
    assert (ROOT / "ATTRIBUTION.md").exists()


def test_the_human_facing_version_copies_agree_with_the_package() -> None:
    """CITATION.cff and the skill's frontmatter carry the version for readers and agent hosts; the
    bump guard watches only src/, so this is the only thing that ties them to the code."""
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "microrelief" / "SKILL.md").read_text(encoding="utf-8")
    assert f"version: {microrelief.__version__}\n" in cff
    assert f'version: "{microrelief.__version__}"' in skill


def test_the_module_entry_point_actually_runs_the_cli(tmp_path: Path) -> None:
    """`python -m microrelief.cli` is a documented way in, and without an `if __name__ ==
    "__main__"` guard it exits 0 having done nothing -- a silent success indistinguishable in
    any exit-code check from a real run. So this asserts the *artefact*, not the return code.

    The console script is exercised throughout the suite; this is the only test that enters
    through the module form, which is what a reader whose PATH lacks the script reaches for.
    """
    out = tmp_path / "out"
    sample = ROOT / "examples" / "sistelo-sample"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "microrelief.cli",
            "run",
            "--aoi",
            str(sample / "aoi.geojson"),
            "--laz",
            str(sample),
            "--out",
            str(out),
            "--attribution",
            (sample / "attribution.txt").read_text(encoding="utf-8").strip(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    record = out / "provenance.json"
    assert record.exists(), (
        f"python -m produced no record; rc={completed.returncode}, "
        f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
    )
    got = json.loads(record.read_text(encoding="utf-8"))
    assert got["package_version"] == microrelief.__version__

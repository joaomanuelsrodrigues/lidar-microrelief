import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

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

    # `uv.lock` records this package as a workspace member with its own version, and CI's
    # FIRST step is `uv sync --locked`, which refuses a lock that has drifted from
    # pyproject.toml. A bump that forgets `uv lock` therefore makes every later gate
    # unreachable while every local gate stays green -- measured in s293, where exactly that
    # shipped. This is the one version copy a CI failure, not a reader, notices.
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    member = lock.split('name = "microrelief"', 1)
    assert len(member) == 2, "uv.lock does not record microrelief as a member"
    locked = member[1].split("version = ", 1)[1].split("\n", 1)[0].strip().strip('"')
    assert locked == microrelief.__version__, (
        f"uv.lock records {locked}, package is {microrelief.__version__}; run `uv lock`"
    )


@pytest.mark.parametrize("module", ["microrelief", "microrelief.cli"])
def test_the_module_entry_point_actually_runs_the_cli(tmp_path: Path, module: str) -> None:
    """Both module forms, because they fail for different reasons and only one was fixed first.

    `python -m microrelief.cli` without an `if __name__ == "__main__"` guard exits 0 having
    done nothing -- a silent success no exit-code check can tell from a real run. `python -m
    microrelief` without a `__main__.py` fails loudly instead, and it is the form a reader
    whose PATH lacks the console script actually reaches for. 0.4.1 closed the first and left
    the second, which a review caught. So both are parametrised here, and both assert the
    *artefact*, never the return code.
    """
    out = tmp_path / "out"
    sample = ROOT / "examples" / "sistelo-sample"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
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


def test_importing_the_module_entry_point_does_not_run_the_cli() -> None:
    """`__main__.py` must run the CLI when executed, and do nothing at all when imported.

    Without a guard the module's body calls `main()` at import time, so `import
    microrelief.__main__` terminates the interpreter with argparse's usage -- and every
    import-based tool takes the whole process down with it: `pkgutil.walk_packages`, a doctest
    or coverage sweep over `src/`, an autodoc build, or an import-based version of
    `tests/test_layering.py` (which today only parses AST, so nothing here catches it).

    The assertion is the sentinel printed AFTER the import, not the return code: an exit code
    says the process ended, this says the process survived and kept going -- which is the
    property an importer actually needs.
    """
    completed = subprocess.run(
        [sys.executable, "-c", "import microrelief.__main__; print('SURVIVED')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    assert "SURVIVED" in completed.stdout, (
        f"importing the entry point ended the interpreter; rc={completed.returncode}, "
        f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
    )

"""CONTRIBUTING.md's Commands block claims to mirror the CI gate step for step; this test is the
only thing that makes the claim true after the next edit to either file. A replicated gate that
had drifted from the real one read green over a subset of it, twice. The workflow is parsed as
YAML because three hand-rolled line readers each missed a form the next review found."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STEP_KEYS = {"name", "run", "uses", "with", "continue-on-error"}


def _ci_steps() -> list[str]:
    """Every `run` of every step of every job, in order. A step key this mirror does not model
    (`shell`, `working-directory`, `env`) would change what the command does without changing its
    text, so it is refused rather than ignored."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps: list[str] = []
    for job in doc["jobs"].values():
        for step in job["steps"]:
            unknown = set(step) - STEP_KEYS
            assert not unknown, (
                f"step {step} uses keys the CONTRIBUTING.md mirror does not model: {unknown}"
            )
            if "run" in step:
                steps.extend(line.strip() for line in str(step["run"]).splitlines() if line.strip())
    return steps


def _commands_block() -> list[str]:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    block = text[text.index("## Commands") :]
    return [
        re.sub(r"\s+#.*$", "", ln.strip()) for ln in block.splitlines() if ln.startswith("    ")
    ]


def test_the_commands_block_equals_the_ci_steps_in_order() -> None:
    ci = _ci_steps()
    assert ci, "no run steps parsed from ci.yml"
    expected = [re.sub(r"^uv run (\S+)", r".venv/bin/\1", step) for step in ci]
    assert _commands_block() == expected


def test_the_commands_block_chains_nothing() -> None:
    assert not any("&&" in cmd for cmd in _commands_block()), _commands_block()

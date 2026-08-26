"""AGENTS.md's Commands block claims to mirror the CI gate; this is the only thing that makes the
claim true after the next edit to either file (the repo's own ledger: a replicated gate that
drifted from the real one read green over a subset, twice in 2026-08)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ci_steps() -> list[str]:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    steps: list[str] = []
    for line in text.splitlines():
        m = re.match(r"\s*-?\s*run:\s*(\S.*)$", line)
        if m and m.group(1) != "|":
            steps.append(m.group(1).strip())
    # multi-line `run: |` blocks: indented command lines that follow
    for m in re.finditer(r"run: \|\n((?:[ \t]+\S.*\n)+)", text):
        steps.extend(cmd.strip() for cmd in m.group(1).splitlines())
    return steps


def _commands_block() -> list[str]:
    text = (ROOT / "AGENTS.md").read_text()
    block = text[text.index("## Commands") :]
    return [ln.strip() for ln in block.splitlines() if ln.startswith("    ")]


def test_the_commands_block_mirrors_ci_step_for_step() -> None:
    ci, agents = _ci_steps(), _commands_block()
    assert ci, "no run: steps parsed from ci.yml"
    for step in ci:
        expected = re.sub(r"^uv run (\S+)", r".venv/bin/\1", step)
        assert any(cmd.split("#")[0].strip() == expected for cmd in agents), (
            step,
            expected,
            agents,
        )


def test_the_commands_block_chains_nothing() -> None:
    assert not any("&&" in cmd for cmd in _commands_block()), _commands_block()

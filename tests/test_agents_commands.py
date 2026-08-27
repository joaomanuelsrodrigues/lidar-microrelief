"""AGENTS.md's Commands block claims to mirror the CI gate step for step; this is the only thing
that makes the claim true after the next edit to either file (the repo's own ledger: a replicated
gate that drifted from the real one read green over a subset, twice in 2026-08)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


BLOCK = {"|", "|-", "|+", ">", ">-", ">+"}


def _steps(text: str) -> list[str]:
    """Every `run:` command, in order; a block scalar (`|`, `|-`, `>`, ...) contributes the
    non-blank lines indented deeper than its own key — blank lines inside a block are allowed by
    YAML and must not end it (they did, and the equality test read green over a subset)."""
    lines = text.splitlines()
    steps: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"(\s*)-?\s*run:\s*(\S.*)$", lines[i])
        if m and m.group(2).strip() not in BLOCK:
            steps.append(m.group(2).strip())
        elif m:
            indent = len(lines[i]) - len(lines[i].lstrip())
            i += 1
            while i < len(lines) and (
                not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
            ):
                if lines[i].strip():
                    steps.append(lines[i].strip())
                i += 1
            continue
        i += 1
    return steps


def _ci_steps() -> list[str]:
    return _steps((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def test_the_parser_keeps_commands_after_a_blank_line_inside_a_block() -> None:
    text = (
        "steps:\n  - run: uv sync\n  - name: gate\n    run: |\n"
        "      first\n\n      second\n  - run: last\n"
    )
    assert _steps(text) == ["uv sync", "first", "second", "last"]


def _commands_block() -> list[str]:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    block = text[text.index("## Commands") :]
    return [ln.strip().split("#")[0].strip() for ln in block.splitlines() if ln.startswith("    ")]


def test_the_commands_block_equals_the_ci_steps_in_order() -> None:
    ci = _ci_steps()
    assert ci, "no run: steps parsed from ci.yml"
    expected = [re.sub(r"^uv run (\S+)", r".venv/bin/\1", step) for step in ci]
    assert _commands_block() == expected


def test_the_commands_block_chains_nothing() -> None:
    assert not any("&&" in cmd for cmd in _commands_block()), _commands_block()

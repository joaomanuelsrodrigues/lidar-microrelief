"""AGENTS.md's Commands block claims to mirror the CI gate step for step; this is the only thing
that makes the claim true after the next edit to either file (the repo's own ledger: a replicated
gate that drifted from the real one read green over a subset, twice in 2026-08)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _steps(text: str) -> list[str]:
    """Every `run:` command, in order. The only block form this parser implements is a literal
    `|` (or `|-`) with nothing after it; any other scalar header raises rather than being read as
    a command or silently truncated. A block's lines are those indented deeper than the `run` KEY
    (not the list-item dash: a sibling key such as `name:` sits at the key's column and ends the
    block); blank lines inside a block are allowed by YAML and skipped."""
    lines = text.splitlines()
    steps: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"(\s*-?\s*)run:\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key_col, value = len(m.group(1)), m.group(2).strip()
        if value in {"|", "|-"}:
            i += 1
            while i < len(lines):
                line = lines[i]
                if not line.strip():
                    i += 1
                    continue
                if len(line) - len(line.lstrip()) <= key_col:
                    break
                steps.append(line.strip())
                i += 1
            continue
        if value.startswith(("|", ">")):
            raise ValueError(f"unsupported block scalar header in ci.yml line {i + 1}: {value!r}")
        if not value:
            raise ValueError(f"empty run: at ci.yml line {i + 1}")
        steps.append(value)
        i += 1
    return steps


def _ci_steps() -> list[str]:
    return _steps((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def test_the_parser_keeps_commands_after_a_blank_line_and_stops_at_a_sibling_key() -> None:
    text = (
        "steps:\n  - run: uv sync\n  - run: |\n      first\n\n      second\n"
        "    name: gate\n    env:\n      FOO: bar\n  - run: last\n"
    )
    assert _steps(text) == ["uv sync", "first", "second", "last"]


@pytest.mark.parametrize("header", [">", ">-", "| # comment", "|2"])
def test_the_parser_refuses_a_block_form_it_does_not_implement(header: str) -> None:
    with pytest.raises(ValueError):
        _steps(f"  - run: {header}\n      folded\n")


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

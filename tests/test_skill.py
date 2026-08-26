"""The skill file is how an agent drives the CLI; every flag it names must exist, and the
frontmatter must satisfy the Agent Skills spec so a host can load it."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "microrelief" / "SKILL.md"
CLI = ROOT / "src" / "microrelief" / "cli.py"


def _frontmatter() -> dict[str, str]:
    text = SKILL.read_text()
    assert text.startswith("---\n")
    block = text.split("---\n", 2)[1]
    pairs = (line.split(":", 1) for line in block.splitlines() if ":" in line and line[0] != " ")
    return {k.strip(): v.strip() for k, v in pairs}


def test_frontmatter_satisfies_the_agent_skills_spec() -> None:
    fm = _frontmatter()
    assert fm["name"] == SKILL.parent.name == "microrelief"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 0 < len(fm["description"]) <= 1024
    assert len(SKILL.read_text().splitlines()) <= 500


def test_every_flag_the_skill_names_is_a_flag_the_cli_accepts() -> None:
    accepted = set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', CLI.read_text()))
    named = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", SKILL.read_text()))
    assert named, "the skill names no flags at all"
    assert named <= accepted, named - accepted


def test_agents_md_is_the_one_source_and_claude_md_imports_it() -> None:
    assert (ROOT / "AGENTS.md").exists()
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text()

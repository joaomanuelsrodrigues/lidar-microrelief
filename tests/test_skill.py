"""The skill file is how an agent drives the CLI; every flag it names must exist, and the
frontmatter must satisfy the Agent Skills spec so a host can load it."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "microrelief" / "SKILL.md"
CLI = ROOT / "src" / "microrelief" / "cli.py"

# Public, widely known filenames, unlike the local tool directories the rule below catches without
# naming any. This half is an enumeration and therefore NOT exhaustive; it is the dot-component
# rule that covers what nobody has listed.
ASSISTANT_CONFIG = re.compile(
    r"^(CLAUDE|AGENTS|GEMINI|COPILOT)(\.local)?\.md$"
    r"|^copilot-instructions\.md$"
    r"|^\.(cursorrules|windsurfrules|clinerules|roomodes|continuerules)$"
    r"|^\.aider\.conf\.ya?ml$"
    r"|^\.mcp\.json$"
)
# Every dot-component this repository legitimately tracks, measured from the tree.
DOT_ALLOWED = {".github", ".gitignore", ".nojekyll"}


def _frontmatter() -> dict[str, str]:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    block = text.split("---\n", 2)[1]
    pairs = (line.split(":", 1) for line in block.splitlines() if ":" in line and line[0] != " ")
    return {k.strip(): v.strip() for k, v in pairs}


def test_frontmatter_satisfies_the_agent_skills_spec() -> None:
    fm = _frontmatter()
    assert fm["name"] == SKILL.parent.name == "microrelief"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 0 < len(fm["description"]) <= 1024
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) <= 500


def test_every_flag_the_skill_names_is_a_flag_the_cli_accepts() -> None:
    accepted = set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', CLI.read_text(encoding="utf-8")))
    named = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", SKILL.read_text(encoding="utf-8")))
    assert named, "the skill names no flags at all"
    assert named <= accepted, named - accepted


def test_the_contributor_guide_is_the_one_source() -> None:
    assert (ROOT / "CONTRIBUTING.md").exists()


def test_no_assistant_tooling_file_is_tracked() -> None:
    """The predecessor of this test asserted that CLAUDE.md existed and imported AGENTS.md. That
    arrangement was removed on purpose, so this asserts the removal instead of quietly dropping
    the guard: a tracked file that configures a coding assistant belongs in a private checkout,
    and a `.gitignore` naming those tools announces exactly what removing them was meant to stop
    announcing, so the ignore rules live in `.git/info/exclude`."""
    tracked = [
        name
        for name in subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split("\0")
        if name
    ]
    found = sorted(name for name in tracked if ASSISTANT_CONFIG.match(Path(name).name))
    assert not found, found
    # Derived rather than named. The first version listed the local tool directories so it could
    # assert `.gitignore` no longer mentions them, which republished in a tracked test exactly what
    # moving them out of `.gitignore` was meant to stop publishing. This names none of them, and it
    # reads EVERY path component rather than the first: the previous version required a name to
    # both start with a dot and contain a slash, so `src/.cursor/rules/x`, `docs/.claude/settings`,
    # `.mcp.json` and `.roomodes` all passed it while it claimed to catch anything unlisted.
    dotted = {part for name in tracked for part in name.split("/") if part.startswith(".")}
    assert dotted <= DOT_ALLOWED, sorted(dotted - DOT_ALLOWED)


def test_the_assistant_config_pattern_speaks_and_stays_quiet() -> None:
    """Silence is this guard's pass condition, so the pattern must be shown to fire. No tracked file
    matches it, which means an empty alternation, a typo, or `^$` would leave the suite green."""
    must_fire = [
        "CLAUDE.md",
        "CLAUDE.local.md",
        "AGENTS.md",
        "GEMINI.md",
        "COPILOT.md",
        "copilot-instructions.md",
        ".cursorrules",
        ".windsurfrules",
        ".clinerules",
        ".roomodes",
        ".continuerules",
        ".aider.conf.yml",
        ".aider.conf.yaml",
        ".mcp.json",
    ]
    for name in must_fire:
        assert ASSISTANT_CONFIG.match(name), name
    must_not_fire = [
        "README.md",
        "CONTRIBUTING.md",
        "RUBRIC.md",
        "SECURITY.md",
        "ATTRIBUTION.md",
        "recipes.md",
        "AGENT.md",
        "CLAUDES.md",
        ".gitignore",
        ".nojekyll",
        "mcp.json",
    ]
    for name in must_not_fire:
        assert not ASSISTANT_CONFIG.match(name), name

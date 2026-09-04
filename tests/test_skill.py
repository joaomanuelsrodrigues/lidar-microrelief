"""The skill file is how an agent drives the CLI; every flag it names must exist, and the
frontmatter must satisfy the Agent Skills spec so a host can load it."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "microrelief" / "SKILL.md"
CLI = ROOT / "src" / "microrelief" / "cli.py"


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
    # Public, widely known filenames, unlike the local tool directories the rule below catches
    # without naming. This half is an enumeration and therefore not exhaustive; the dot-directory
    # rule below is the derived half, and it is what catches a tool nobody has listed yet.
    assistant_config = re.compile(
        r"^(CLAUDE|AGENTS|GEMINI|COPILOT)(\.local)?\.md$"
        r"|^copilot-instructions\.md$"
        r"|^\.(cursorrules|windsurfrules|clinerules)$"
        r"|^\.aider\.conf\.ya?ml$"
    )
    found = sorted(name for name in tracked if assistant_config.match(Path(name).name))
    assert not found, found
    # Derived rather than named. The first version of this guard listed the local tool directories
    # so it could assert `.gitignore` no longer mentions them, which republished in a tracked test
    # exactly what moving them out of `.gitignore` was meant to stop publishing. A dot-directory
    # allowlist catches any of them, and any future one, while naming none.
    dot_dirs = {name.split("/")[0] for name in tracked if name.startswith(".") and "/" in name}
    assert dot_dirs <= {".github"}, sorted(dot_dirs - {".github"})

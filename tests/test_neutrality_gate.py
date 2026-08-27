"""The gate that keeps private paths, e-mails and .env files out of what this repository publishes.

Its pass condition is silence, which is also what a gate that scanned nothing prints — so the
controls are planted violations that have to be caught (the script's own self-test builds a
temporary repository with one of each; the tests below run the real script on scratch
repositories), and the summary reports every denominator, derived here by a different instrument
than the script's own. The population is the index, read through git, from any directory.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "neutrality.sh"
HOME_PATH = "/home/" + "some" + "one/"  # assembled: this file is a tracked blob the gate reads


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """The script resolves the repository from the cwd (`git rev-parse --show-toplevel`)."""
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # a path with non-UTF-8 bytes is the gate's to judge, not this harness's
    )


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def _summary_for(repo: Path) -> str:
    """Independent of the script: modes from `git ls-files -s`, blobs from `git cat-file`; git's
    text rule is 'no NUL in the first 8000 bytes' and a line to read means a non-empty blob."""
    regular = symlink = gitlink = text = 0
    for rec in _git(repo, "ls-files", "-s", "-z").split(b"\0"):
        if not rec:
            continue
        mode, sha = rec.split(b" ")[:2]
        if mode == b"120000":
            symlink += 1
        elif mode == b"160000":
            gitlink += 1
        else:
            regular += 1
            data = _git(repo, "cat-file", "blob", sha.decode())
            if data and b"\0" not in data[:8000]:
                text += 1
    return (
        f"neutrality: {regular + symlink + gitlink} tracked ({regular} regular, {symlink} symlink, "
        f"{gitlink} submodule not scanned); private paths over all bytes of {regular}; "
        f"e-mails over {text} text ({regular - text} binary or empty); 0 hits"
    )


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with one clean tracked file; the real script runs against it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "clean.md").write_text("nothing to see\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "clean.md"], cwd=repo, check=True)
    return repo


def test_the_self_test_plants_every_class_in_a_temporary_repository_and_catches_each() -> None:
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    for phrase in (
        "private path behind a NUL byte caught",
        "e-mail caught",
        "symlink target caught",
        ".env.local caught",
        ".venv/ contents ignored",
        "clean repo silent",
        ".env pattern matches .env.local and sub/dir/.env, not .envrc",
    ):
        assert phrase in result.stdout, (phrase, result.stdout)


def test_the_tracked_tree_is_clean_and_the_summary_names_every_denominator() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT) in result.stdout


def test_the_scan_covers_the_whole_tree_from_a_subdirectory() -> None:
    """Measured 2026-08-26: without `cd` to the root, `docs/` reported 32 files scanned, exit 0."""
    result = _run(cwd=ROOT / "docs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT) in result.stdout


def test_a_planted_env_file_fails_the_gate_at_any_depth_and_envrc_does_not(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    assert _run(cwd=repo).returncode == 0
    (repo / ".envrc").write_text("use nix\n", encoding="utf-8")
    assert _run(cwd=repo).returncode == 0
    (repo / ".env.local").write_text("TOKEN=x\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 1 and re.search(r"^\.env\.local$", result.stdout, re.M), (
        result.stdout
    )
    (repo / ".env.local").unlink()
    (repo / "sub").mkdir()
    (repo / "sub" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 1 and re.search(r"^sub/\.env$", result.stdout, re.M), result.stdout
    subprocess.run(["git", "add", "-f", "sub/.env"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "tracked .env file:" in result.stdout, result.stdout


def test_a_symlinked_env_file_is_caught(tmp_path: Path) -> None:
    """`find -type f` had passed it (review round 3)."""
    repo = _scratch_repo(tmp_path)
    (repo / ".env").symlink_to("clean.md")
    result = _run(cwd=repo)
    assert result.returncode == 1 and re.search(r"^\.env$", result.stdout, re.M), result.stdout


def test_a_tracked_env_under_a_non_ascii_path_is_caught(tmp_path: Path) -> None:
    """`git ls-files` without -z octal-quotes the path; an anchored pattern missed it (round 3)."""
    repo = _scratch_repo(tmp_path)
    (repo / "é").mkdir()
    (repo / "é" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "é/.env"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "tracked .env file:" in result.stdout, result.stdout


def test_an_ignored_virtualenv_collapses_and_a_real_env_beside_it_still_fails(
    tmp_path: Path,
) -> None:
    """Enumeration is git's own (`ls-files -o -i --directory`): an ignored directory is one entry,
    so a package's .env.example inside it is never seen; an un-ignored one is walked — the same
    view `git status` gives. A root `pyvenv.cfg` used to blind the previous prune (round 4)."""
    repo = _scratch_repo(tmp_path)
    (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    site = repo / ".venv" / "lib" / "site-packages" / "somepkg"
    site.mkdir(parents=True)
    (site / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (repo / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 0, result.stdout + result.stderr
    (repo / ".env.local").write_text("TOKEN=x\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 1 and re.search(r"^\.env\.local$", result.stdout, re.M), (
        result.stdout
    )
    assert ".venv/" not in result.stdout


def test_a_private_path_inside_a_binary_blob_is_caught(tmp_path: Path) -> None:
    """Measured 2026-08-27: a path in a PNG text chunk was invisible to `grep -I`."""
    repo = _scratch_repo(tmp_path)
    (repo / "figure.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00tEXtSource\x00rendered on " + HOME_PATH.encode() + b"\n"
    )
    subprocess.run(["git", "add", "figure.png"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "private path leak:" in result.stdout, (
        result.stdout + result.stderr
    )
    assert re.search(r"^figure\.png:\d+:/home/", result.stdout, re.M), result.stdout


def test_a_binary_only_index_and_a_newline_only_file_are_counted_not_fatal(tmp_path: Path) -> None:
    """On the working-tree version, each killed the script with a bare exit 123 and no summary."""
    repo = _scratch_repo(tmp_path)
    subprocess.run(["git", "rm", "-qf", "clean.md"], cwd=repo, check=True)
    (repo / "b.bin").write_bytes(b"x\0y")
    subprocess.run(["git", "add", "b.bin"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 0 and _summary_for(repo) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails over 0 text (1 binary or empty)" in result.stdout
    (repo / "nl.txt").write_text("\n\n", encoding="utf-8")
    subprocess.run(["git", "add", "nl.txt"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 0 and _summary_for(repo) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails over 1 text (1 binary or empty)" in result.stdout


def test_a_tracked_file_deleted_from_the_working_tree_is_still_scanned(tmp_path: Path) -> None:
    """The index is what ships; the working tree is not consulted."""
    repo = _scratch_repo(tmp_path)
    (repo / "clean.md").write_text(f"see {HOME_PATH}x\n", encoding="utf-8")
    subprocess.run(["git", "add", "clean.md"], cwd=repo, check=True)
    (repo / "clean.md").unlink()
    result = _run(cwd=repo)
    assert result.returncode == 1 and "clean.md:1:/home/" in result.stdout, (
        result.stdout + result.stderr
    )


def test_a_symlink_is_scanned_by_its_link_text_even_when_named_minus_n(tmp_path: Path) -> None:
    """Round 4: a tracked symlink was scanned by its target's bytes, never by the link text git
    publishes; and a path named `-n` vanished in an `echo` and the gate went green."""
    repo = _scratch_repo(tmp_path)
    (repo / "-n").symlink_to(HOME_PATH + "x")
    subprocess.run(["git", "add", "--", "-n"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "leak in a symlink target:" in result.stdout, (
        result.stdout + result.stderr
    )
    assert "-n -> /home/" in result.stdout


def test_a_submodule_is_counted_as_not_scanned(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", "160000," + "0" * 39 + "1,vendored"],
        cwd=repo,
        check=True,
    )
    result = _run(cwd=repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 submodule not scanned" in result.stdout and _summary_for(repo) in result.stdout


def test_a_late_nul_file_is_scanned_and_counted_by_the_same_rule(tmp_path: Path) -> None:
    """git decides text by the first 8000 bytes; a NUL after that leaves the file text for both
    the e-mail scan and the count, so they cannot disagree (round 4 had them disagree)."""
    repo = _scratch_repo(tmp_path)
    (repo / "big.txt").write_bytes(
        b"contact: someone" + b"@" + b"example.org\n" + b"a" * 9000 + b"\n\0\n"
    )
    subprocess.run(["git", "add", "big.txt"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "big.txt:1:someone" in result.stdout, result.stdout
    (repo / "big.txt").write_bytes(b"plain\n" + b"a" * 9000 + b"\n\0\n")
    subprocess.run(["git", "add", "big.txt"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 0 and _summary_for(repo) in result.stdout, result.stdout
    assert "e-mails over 2 text (0 binary or empty)" in result.stdout

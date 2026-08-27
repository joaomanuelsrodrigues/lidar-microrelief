"""The gate that keeps private paths, e-mails and tracked .env files out of what this repository
publishes.

Its pass condition is silence, which is also what a gate that scanned nothing prints — so the
controls are planted violations that have to be caught (the script's own self-test builds a
temporary repository with one of each; the tests below run the real script on scratch
repositories in an isolated git environment), the summary reports every denominator, derived
here by a different instrument than the script's own, and a broken instrument must exit 2
rather than print a summary. The population is the index, read through git, from any directory.
"""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "neutrality.sh"
HOME_PATH = "/home/" + "some" + "one/"  # assembled: this file is a tracked blob the gate reads
MAIL = "some" + "one" + "@" + "example.org"


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """No user or system git config, no inherited index/dir/work-tree: the machine cannot vary
    the answer (a global core.excludesFile once made the self-test's `git add` refuse a PNG)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(tmp_path), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", **extra)
    return env


def _run(cwd: Path, tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    """The script resolves the repository from the cwd (`git rev-parse --show-toplevel`)."""
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        env=_env(tmp_path, **extra),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # a path with non-UTF-8 bytes is the gate's to judge, not this harness's
    )


def _git(repo: Path, tmp_path: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, env=_env(tmp_path), capture_output=True, check=True
    ).stdout


EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _summary_for(repo: Path, tmp_path: Path) -> str:
    """Independent of the script: modes from `git ls-files -s`, blobs from `git cat-file`; the
    text rule is 'non-empty and no NUL byte anywhere'; the e-mail-shaped binary blobs are counted
    here too, never typed."""
    regular = symlink = gitlink = text = mail_binary = 0
    for rec in _git(repo, tmp_path, "ls-files", "-s", "-z").split(b"\0"):
        if not rec:
            continue
        mode, sha = rec.split(b" ")[:2]
        if mode == b"120000":
            symlink += 1
        elif mode == b"160000":
            gitlink += 1
        else:
            regular += 1
            data = _git(repo, tmp_path, "cat-file", "blob", sha.decode())
            if data and b"\0" not in data:
                text += 1
            elif EMAIL.search(data):
                mail_binary += 1
    return (
        f"neutrality: {regular + symlink + gitlink} tracked ({regular} regular, {symlink} symlink, "
        f"{gitlink} submodule not scanned); private paths over all bytes of {regular}; "
        f"e-mails judged in {text} text ({regular - text} binary or empty, e-mail-shaped bytes in "
        f"{mail_binary} of them not judged); 0 hits"
    )


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with one clean tracked file; the real script runs against it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "clean.md").write_text("nothing to see\n", encoding="utf-8")
    _git(repo, tmp_path, "init", "-q")
    _git(repo, tmp_path, "add", "clean.md")
    return repo


def test_the_self_test_plants_every_class_in_a_temporary_repository_and_catches_each(
    tmp_path: Path,
) -> None:
    result = _run(ROOT, tmp_path, "--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    for phrase in (
        "private path behind a NUL byte caught",
        "e-mail caught despite .gitattributes",
        "symlink target caught",
        "tracked .env at depth caught",
        "e-mail in a path holding a newline caught",
        "e-mail-shaped bytes in three binary blobs (one under a non-ASCII path, one with two runs) "
        "counted as blobs, not judged",
        "clean repo silent",
        "broken instrument exits 2 with no summary",
        "empty population exits 2 with no summary",
        ".env pattern matches .env.local and sub/dir/.env, not .envrc",
    ):
        assert f"self-test: {phrase}" in result.stdout, (phrase, result.stdout)


def test_the_tracked_tree_is_clean_and_the_summary_names_every_denominator(tmp_path: Path) -> None:
    """Reads the INDEX, not the working tree: an unstaged edit to a tracked file is invisible here
    and a staged one is judged before it is committed — stage, then run (measured 2026-08-27:
    a fixed literal in this very file kept failing until `git add`)."""
    result = _run(ROOT, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT, tmp_path) in result.stdout, result.stdout
    # one PNG in the tree carries e-mail-shaped bytes by coincidence (measured 2026-08-27); the
    # count above is derived, and this line only documents why it is not zero today
    assert "e-mail-shaped bytes in 1 of them not judged" in result.stdout


def test_the_scan_covers_the_whole_tree_from_a_subdirectory(tmp_path: Path) -> None:
    """Measured 2026-08-26: without `cd` to the root, `docs/` reported 32 files scanned, exit 0."""
    result = _run(ROOT / "docs", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT, tmp_path) in result.stdout


def test_a_tracked_env_file_at_any_depth_is_caught_and_envrc_is_not(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    (repo / ".envrc").write_text("use nix\n", encoding="utf-8")
    _git(repo, tmp_path, "add", ".envrc")
    assert _run(repo, tmp_path).returncode == 0
    (repo / "sub").mkdir()
    (repo / "sub" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    assert _run(repo, tmp_path).returncode == 0  # untracked: not this gate's question
    _git(repo, tmp_path, "add", "-f", "sub/.env")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "tracked .env file:" in result.stdout, result.stdout
    assert re.search(r"^sub/\.env$", result.stdout, re.M)


def test_a_tracked_env_under_a_non_ascii_path_is_caught(tmp_path: Path) -> None:
    """`git ls-files` without -z octal-quotes the path; an anchored pattern missed it (round 3)."""
    repo = _scratch_repo(tmp_path)
    (repo / "é").mkdir()
    (repo / "é" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "-f", "é/.env")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "tracked .env file:" in result.stdout, result.stdout


def test_a_private_path_inside_a_binary_blob_is_caught(tmp_path: Path) -> None:
    """Measured 2026-08-27: a path in a PNG text chunk was invisible to `grep -I`."""
    repo = _scratch_repo(tmp_path)
    (repo / "figure.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00tEXtSource\x00rendered on " + HOME_PATH.encode() + b"\n"
    )
    _git(repo, tmp_path, "add", "figure.png")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "private path leak:" in result.stdout, (
        result.stdout + result.stderr
    )
    assert re.search(r"^figure\.png:\d+:/home/", result.stdout, re.M), result.stdout


def test_an_email_in_a_binary_blob_is_counted_not_judged(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"maybe " + MAIL.encode() + b"\0\n")
    _git(repo, tmp_path, "add", "blob.bin")
    result = _run(repo, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(repo, tmp_path) in result.stdout


def test_an_email_is_caught_even_when_gitattributes_marks_the_file_no_diff(tmp_path: Path) -> None:
    """`git grep -I` obeys `.gitattributes`; a tracked `*.md -diff` moved a text file out of its
    population (round 5). The text rule is the script's own, so the attribute changes nothing."""
    repo = _scratch_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.md -diff\n", encoding="utf-8")
    (repo / "clean.md").write_text(f"contact: {MAIL}\n", encoding="utf-8")
    _git(repo, tmp_path, "add", ".gitattributes", "clean.md")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "e-mail leak:" in result.stdout, result.stdout + result.stderr
    assert "clean.md:1:someone" in result.stdout


def test_a_binary_only_index_and_a_newline_only_file_are_counted_not_fatal(tmp_path: Path) -> None:
    """On the working-tree version, each killed the script with a bare exit 123 and no summary."""
    repo = _scratch_repo(tmp_path)
    _git(repo, tmp_path, "rm", "-qf", "clean.md")
    (repo / "b.bin").write_bytes(b"x\0y")
    _git(repo, tmp_path, "add", "b.bin")
    result = _run(repo, tmp_path)
    assert result.returncode == 0 and _summary_for(repo, tmp_path) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails judged in 0 text (1 binary or empty" in result.stdout
    (repo / "nl.txt").write_text("\n\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "nl.txt")
    result = _run(repo, tmp_path)
    assert result.returncode == 0 and _summary_for(repo, tmp_path) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails judged in 1 text (1 binary or empty" in result.stdout


def test_a_tracked_file_deleted_from_the_working_tree_is_still_scanned(tmp_path: Path) -> None:
    """The index is what ships; the working tree is not consulted."""
    repo = _scratch_repo(tmp_path)
    (repo / "clean.md").write_text(f"see {HOME_PATH}x\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "clean.md")
    (repo / "clean.md").unlink()
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "clean.md:1:/home/" in result.stdout, (
        result.stdout + result.stderr
    )


def test_a_symlink_is_scanned_by_its_link_text_even_when_named_minus_n(tmp_path: Path) -> None:
    """Round 4: a tracked symlink was scanned by its target's bytes, never by the link text git
    publishes; and a path named `-n` vanished in an `echo` and the gate went green."""
    repo = _scratch_repo(tmp_path)
    (repo / "-n").symlink_to(HOME_PATH + "x")
    _git(repo, tmp_path, "add", "--", "-n")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "leak in a symlink target:" in result.stdout, (
        result.stdout + result.stderr
    )
    assert "-n -> /home/" in result.stdout


def test_a_submodule_is_counted_as_not_scanned(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    _git(
        repo, tmp_path, "update-index", "--add", "--cacheinfo", "160000," + "0" * 39 + "1,vendored"
    )
    result = _run(repo, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "1 submodule not scanned" in result.stdout and _summary_for(repo, tmp_path) in result.stdout
    )


def test_a_file_with_a_late_nul_is_binary_for_the_verdict_and_the_count_alike(
    tmp_path: Path,
) -> None:
    """One rule, the script's own — a NUL anywhere makes a blob binary — applied to the e-mail
    verdict and to the count, so they cannot disagree (round 4 had `grep -I` read a late-NUL file
    while the count called it skipped)."""
    repo = _scratch_repo(tmp_path)
    (repo / "big.txt").write_bytes(b"contact: " + MAIL.encode() + b"\n" + b"a" * 9000 + b"\n\0\n")
    _git(repo, tmp_path, "add", "big.txt")
    result = _run(repo, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(repo, tmp_path) in result.stdout
    assert (
        "e-mails judged in 1 text (1 binary or empty, e-mail-shaped bytes in 1 of them not judged)"
        in result.stdout
    )


def test_an_email_shaped_binary_blob_under_a_non_ascii_path_is_counted_not_judged(
    tmp_path: Path,
) -> None:
    """Round 6: the hit's path was recovered from ':'-delimited text, so a path git C-quotes never
    matched the binary list and the blob was judged as text — the verdict flipped with the user's
    core.quotePath."""
    repo = _scratch_repo(tmp_path)
    (repo / "é").mkdir()
    (repo / "é" / "blob.bin").write_bytes(b"x " + MAIL.encode() + b"\0\n")
    (repo / "run:2026.bin").write_bytes(b"y " + MAIL.encode() + b"\0\n")
    _git(repo, tmp_path, "add", "é/blob.bin", "run:2026.bin")
    result = _run(
        repo,
        tmp_path,
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="core.quotePath",
        GIT_CONFIG_VALUE_0="true",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "e-mail-shaped bytes in 2 of them not judged" in result.stdout


def test_an_empty_or_unopenable_index_exits_2_with_no_summary(tmp_path: Path) -> None:
    """Round 6: `git ls-files` in a process substitution had its status discarded, and an absent
    index file printed a green summary over zero blobs."""
    repo = _scratch_repo(tmp_path)
    result = _run(repo, tmp_path, GIT_INDEX_FILE=str(tmp_path / "no-such-index"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == "" and "instrument failure" in result.stderr


def test_a_broken_instrument_exits_2_with_no_summary(tmp_path: Path) -> None:
    """Round 5: an `exit 2` inside `$(...)` ended only the subshell and the gate printed a green
    summary over an index it never read."""
    repo = _scratch_repo(tmp_path)
    (repo / "clean.md").write_text(f"see {HOME_PATH}x\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "clean.md")
    result = _run(
        repo,
        tmp_path,
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="grep.patternType",
        GIT_CONFIG_VALUE_0="bogus",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == "" and "instrument failure" in result.stderr, (
        result.stdout + result.stderr
    )


def test_what_git_says_on_stderr_is_an_instrument_note_not_a_hit(tmp_path: Path) -> None:
    """Round 5: `2>&1` folded git's stderr into the hit list. Round 6: the first version of this
    control could not fail — nothing made git speak. GIT_TRACE makes every git call speak."""
    repo = _scratch_repo(tmp_path)
    result = _run(repo, tmp_path, GIT_TRACE="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "leak" not in result.stdout and _summary_for(repo, tmp_path) in result.stdout
    assert "neutrality: git grep said:" in result.stderr and "trace:" in result.stderr


def test_an_email_in_a_path_holding_a_newline_is_caught(tmp_path: Path) -> None:
    """Round 7: a per-path `grep -F` join read the path as a pattern LIST, and a real e-mail in
    such a file vanished from the verdict with a green summary."""
    repo = _scratch_repo(tmp_path)
    (repo / "q\nr.md").write_text(f"contact: {MAIL}\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "q\nr.md")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "e-mail leak:" in result.stdout, result.stdout + result.stderr
    assert "r.md:1:someone" in result.stdout


def test_two_email_shaped_runs_in_one_binary_blob_count_as_one_blob(tmp_path: Path) -> None:
    """The summary says 'N of them' — of the binary blobs — so the count is of blobs, the same
    thing `_summary_for` counts (round 7 had the script count matches)."""
    repo = _scratch_repo(tmp_path)
    (repo / "twice.bin").write_bytes(
        b"a " + MAIL.encode() + b" b other" + b"@" + b"example.com\0\n"
    )
    _git(repo, tmp_path, "add", "twice.bin")
    result = _run(repo, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(repo, tmp_path) in result.stdout and "in 1 of them" in result.stdout


def test_colour_config_does_not_change_the_verdict(tmp_path: Path) -> None:
    """Round 7: the NUL scan lacked --no-color; `color.grep=always` wrapped every name in ANSI
    escapes, no binary blob matched the join, and the tree's one PNG became a false red."""
    repo = _scratch_repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"maybe " + MAIL.encode() + b"\0\n")
    _git(repo, tmp_path, "add", "blob.bin")
    result = _run(
        repo,
        tmp_path,
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="color.grep",
        GIT_CONFIG_VALUE_0="always",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(repo, tmp_path) in result.stdout


def test_an_object_git_cannot_read_is_an_instrument_failure(tmp_path: Path) -> None:
    """`cat-file --batch-check` says `<sha> missing` and exits 0; round 7 found that fed to an
    integer test, which errored into the binary branch and the run stayed green."""
    repo = _scratch_repo(tmp_path)
    _git(
        repo, tmp_path, "update-index", "--add", "--cacheinfo", "100644," + "1" * 40 + ",ghost.txt"
    )
    result = _run(repo, tmp_path)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "instrument failure" in result.stderr

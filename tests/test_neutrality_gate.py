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
import shutil
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


def _git(repo: Path, tmp_path: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, env=_env(tmp_path), capture_output=True, check=True, input=input
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
        f"{mail_binary} of them not judged); 0 tracked files the staged .gitignore excludes; 0 hits"
    )


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with one clean tracked file; the real script runs against it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "clean.md").write_text("nothing to see\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".env*\n", encoding="utf-8")  # the gate's secrets rule is this
    _git(repo, tmp_path, "init", "-q")
    _git(repo, tmp_path, "add", "clean.md", ".gitignore")
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
        "e-mail in a path holding a newline caught",
        "tracked file the staged .gitignore excludes caught: sub/.env",
        "tracked file the staged .gitignore excludes caught: .env-prod",
        "tracked file the staged .gitignore excludes caught: .env/secret",
        "tracked file the staged .gitignore excludes caught: $'sub/.env\\n'",
        "e-mail-shaped bytes in binary blobs counted as blobs, not judged",
        "clean repo silent",
        "broken instrument exits 2 with no summary",
        "empty population exits 2 with no summary",
        "a staged .gitignore without .env* is an instrument failure, exit 2 with no summary",
        "the rule counts only in the staged .gitignore, not the working-tree file",
    ):
        assert f"self-test: {phrase}" in result.stdout, (phrase, result.stdout)


def test_the_tracked_tree_is_clean_and_the_summary_names_every_denominator(tmp_path: Path) -> None:
    """Reads the INDEX, not the working tree: an unstaged edit to a tracked file is invisible here
    and a staged one is judged before it is committed — stage, then run (measured 2026-08-27:
    a fixed literal in this very file kept failing until `git add`)."""
    result = _run(ROOT, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT, tmp_path) in result.stdout, result.stdout
    # Some PNGs in the tree carry e-mail-shaped bytes by coincidence in their compressed data
    # (first measured 2026-08-27, and the count moves whenever a raster is re-rendered: the
    # 0.5.0 run took it from one to two). It used to be pinned here as a literal, which made a
    # legitimate re-render fail a gate about neutrality; the number is derived by `_summary_for`
    # and already asserted above, so what is left to state is only that the phrase is present
    # and that this is why the count is not zero.
    assert re.search(r"e-mail-shaped bytes in \d+ of them not judged", result.stdout)


def test_the_scan_covers_the_whole_tree_from_a_subdirectory(tmp_path: Path) -> None:
    """Measured 2026-08-26: without `cd` to the root, `docs/` reported 32 files scanned, exit 0."""
    result = _run(ROOT / "docs", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(ROOT, tmp_path) in result.stdout


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
    """`git grep -I` obeys `.gitattributes`; a tracked `*.md -diff` moved a text file out of an
    earlier version's population. The text rule is the script's own, so the attribute changes
    nothing."""
    repo = _scratch_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.md -diff\n", encoding="utf-8")
    (repo / "clean.md").write_text(f"contact: {MAIL}\n", encoding="utf-8")
    _git(repo, tmp_path, "add", ".gitattributes", "clean.md")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "e-mail leak:" in result.stdout, result.stdout + result.stderr
    assert "clean.md:1:someone" in result.stdout


def test_a_binary_only_index_and_a_newline_only_file_are_counted_not_fatal(tmp_path: Path) -> None:
    """On the working-tree version, each killed the script with a bare exit 123 and no summary.
    The index also holds `.gitignore` — the rule the gate requires, so an index with no text blob
    at all cannot pass the precondition; this is the smallest population the gate accepts."""
    repo = _scratch_repo(tmp_path)
    _git(repo, tmp_path, "rm", "-qf", "clean.md")
    (repo / "b.bin").write_bytes(b"x\0y")
    _git(repo, tmp_path, "add", "b.bin")
    result = _run(repo, tmp_path)
    assert result.returncode == 0 and _summary_for(repo, tmp_path) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails judged in 1 text (1 binary or empty" in result.stdout
    (repo / "nl.txt").write_text("\n\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "nl.txt")
    result = _run(repo, tmp_path)
    assert result.returncode == 0 and _summary_for(repo, tmp_path) in result.stdout, (
        result.stdout + result.stderr
    )
    assert "e-mails judged in 2 text (1 binary or empty" in result.stdout


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
    verdict and to the count, so they cannot disagree (an earlier version had `grep -I` read a
    late-NUL file while the count called it skipped)."""
    repo = _scratch_repo(tmp_path)
    (repo / "big.txt").write_bytes(b"contact: " + MAIL.encode() + b"\n" + b"a" * 9000 + b"\n\0\n")
    _git(repo, tmp_path, "add", "big.txt")
    result = _run(repo, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _summary_for(repo, tmp_path) in result.stdout
    assert (
        "e-mails judged in 2 text (1 binary or empty, e-mail-shaped bytes in 1 of them not judged)"
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
    thing `_summary_for` counts (an earlier version counted matches)."""
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
    """`cat-file --batch-check` says `<sha> missing` and exits 0; an earlier version fed that
    to an integer test, which errored into the binary branch and the run stayed green."""
    repo = _scratch_repo(tmp_path)
    _git(
        repo, tmp_path, "update-index", "--add", "--cacheinfo", "100644," + "1" * 40 + ",ghost.txt"
    )
    result = _run(repo, tmp_path)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "instrument failure" in result.stderr


def test_the_self_test_cannot_read_a_broken_instrument_as_a_clean_repo(tmp_path: Path) -> None:
    """Round 8 (by mutation): `( check ) || true` swallowed fail_instrument's exit inside a
    subshell and an empty verdict file — the pass condition — printed "clean repo silent"."""
    result = _run(
        ROOT,
        tmp_path,
        "--self-test",
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="grep.patternType",
        GIT_CONFIG_VALUE_0="bogus",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "clean repo silent" not in result.stdout and "instrument failure" in result.stderr


def test_an_unmerged_index_is_an_instrument_failure(tmp_path: Path) -> None:
    """`git grep --cached` skips unmerged entries by construction; an earlier version's count
    had vouched for blobs the scan never read."""
    repo = _scratch_repo(tmp_path)
    sha = (
        _git(repo, tmp_path, "hash-object", "-w", "--stdin", input=b"see " + MAIL.encode() + b"\n")
        .decode()
        .strip()
    )
    info = f"100644 {sha} 1\tf.md\n100644 {sha} 2\tf.md\n100644 {sha} 3\tf.md\n"
    subprocess.run(
        ["git", "update-index", "--index-info"],
        cwd=repo,
        env=_env(tmp_path),
        input=info.encode(),
        check=True,
    )
    result = _run(repo, tmp_path)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert (
        "unmerged" in result.stderr and result.stderr.count("f.md") == 1
    )  # once per path, not per stage


def test_every_git_call_reports_what_it_said_including_the_symlink_read(tmp_path: Path) -> None:
    """Round 8: the per-symlink cat-file was the one call whose stderr was dropped."""
    repo = _scratch_repo(tmp_path)
    (repo / "lnk").symlink_to("clean.md")
    _git(repo, tmp_path, "add", "lnk")
    result = _run(repo, tmp_path, GIT_TRACE="1")
    assert result.returncode == 0, result.stdout + result.stderr
    for what in (
        "git rev-parse",
        "git ls-files",
        "git show (.gitignore)",
        "git cat-file --batch-check",
        "git grep (NUL scan)",
        "git grep",
        "git cat-file (symlink)",
        "git ls-files (ignored)",
    ):
        assert f"neutrality: {what} said:" in result.stderr, (what, result.stderr)


def _shim(tmp_path: Path, body: str) -> dict[str, str]:
    """A `git` on PATH that tampers with one command's output and delegates everything else."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    real = shutil.which("git")
    assert real
    (bin_dir / "git").write_text(
        f'#!/usr/bin/env bash\nREAL={real!r}\n{body}\nexec "$REAL" "$@"\n', encoding="utf-8"
    )
    (bin_dir / "git").chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}"}


def test_a_size_list_shorter_than_the_index_is_an_instrument_failure(tmp_path: Path) -> None:
    """Deleting the sizes-count guard left the suite green — found by mutation testing: this shim
    drops the last size `cat-file --batch-check` returns."""
    repo = _scratch_repo(tmp_path)
    env = _shim(
        tmp_path,
        'case "$*" in *"cat-file --batch-check"*) exec "$REAL" "$@" | sed \'$d\' ;; esac',
    )
    result = _run(repo, tmp_path, **env)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "sizes for" in result.stderr


def test_a_hit_under_a_path_the_index_does_not_list_is_an_instrument_failure(
    tmp_path: Path,
) -> None:
    """Deleting the unlisted-path guard left the suite green — found by mutation testing: this shim
    appends a record for a path the index does not hold to every pattern scan."""
    repo = _scratch_repo(tmp_path)
    env = _shim(
        tmp_path,
        'case "$*" in *" -n -o -E "*) "$REAL" "$@"; rc=$?; '
        'printf "ghost.md\\0007\\000%s\\n" "x"; exit $rc ;; esac',
    )
    result = _run(repo, tmp_path, **env)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "does not list" in result.stderr


def test_a_tracked_file_the_gitignore_excludes_is_caught_at_any_depth_and_by_any_name(
    tmp_path: Path,
) -> None:
    """The secrets rule is the repository's own `.env*`, evaluated by git: a regex of the gate's
    (`.env(\\..+)?`) let `.env-prod`, `.env_local` and `.env/secret` through. An
    untracked one is not this gate's question; a force-added one is."""
    repo = _scratch_repo(tmp_path)
    (repo / "sub").mkdir()
    (repo / ".env").mkdir()
    for name in ("sub/.env", ".env-prod", ".env_local", ".env/secret", "sub/.env\n", ".env "):
        (repo / name).write_text("TOKEN=x\n", encoding="utf-8")
    assert _run(repo, tmp_path).returncode == 0  # untracked: not this gate's question
    _git(
        repo,
        tmp_path,
        "add",
        "-f",
        "--",
        "sub/.env",
        ".env-prod",
        ".env_local",
        ".env/secret",
        "sub/.env\n",
        ".env ",
    )
    result = _run(repo, tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "tracked though the staged .gitignore excludes it:" in result.stdout
    for line in (
        "sub/.env",
        ".env-prod",
        ".env_local",
        ".env/secret",
        ".env ",
        "$'sub/.env\\n'",
    ):
        assert re.search("^" + re.escape(line) + "$", result.stdout, re.M), (line, result.stdout)


def test_a_tracked_env_under_a_non_ascii_path_is_caught(tmp_path: Path) -> None:
    """`git ls-files` without -z octal-quotes the path; an anchored pattern missed it."""
    repo = _scratch_repo(tmp_path)
    (repo / "é").mkdir()
    (repo / "é" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "-f", "é/.env")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "\né/.env\n" in result.stdout, result.stdout + result.stderr


def test_a_tracked_envrc_is_flagged_because_the_repository_ignores_it(tmp_path: Path) -> None:
    """`.envrc` is not a secrets file, but `.env*` ignores it — the rule is the repository's, and a
    force-added file it excludes is reported whatever its purpose (add an exemption to
    .gitignore, not to the gate)."""
    repo = _scratch_repo(tmp_path)
    (repo / ".envrc").write_text("use nix\n", encoding="utf-8")
    _git(repo, tmp_path, "add", "-f", ".envrc")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "\n.envrc\n" in result.stdout, result.stdout
    assert "staged .gitignore excludes it" in result.stdout


def test_a_repository_whose_gitignore_lacks_the_env_rule_is_an_instrument_failure(
    tmp_path: Path,
) -> None:
    repo = _scratch_repo(tmp_path)
    (repo / ".gitignore").write_text("", encoding="utf-8")
    _git(repo, tmp_path, "add", ".gitignore")
    result = _run(repo, tmp_path)
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "no '.env*' line" in result.stderr
    # The rule in the WORKING-TREE file, or in a machine's global excludes, must not count
    (repo / ".gitignore").write_text(".env*\n", encoding="utf-8")  # unstaged
    assert _run(repo, tmp_path).returncode == 2
    excludes = tmp_path / "global-excludes"
    excludes.write_text(".env*\n", encoding="utf-8")
    result = _run(
        repo,
        tmp_path,
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="core.excludesFile",
        GIT_CONFIG_VALUE_0=str(excludes),
    )
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr


def test_an_unguarded_failure_is_exit_2_with_a_message_not_a_silent_hit(tmp_path: Path) -> None:
    """Round 9 (by mutation): a bare failing command inside `check` exited 1 — the hit code —
    with nothing printed; the ERR trap makes it an instrument failure with the line."""
    repo = _scratch_repo(tmp_path)
    mutant = tmp_path / "mutant.sh"
    mutant.write_text(
        SCRIPT.read_text(encoding="utf-8").replace("  classify\n", "  classify\n  false\n", 1),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(mutant)],
        cwd=repo,
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 2 and result.stdout == "", result.stdout + result.stderr
    assert "unguarded command failed" in result.stderr


def test_a_negation_in_the_staged_gitignore_exempts_by_design(tmp_path: Path) -> None:
    """The rule is the repository's: `!.env.keep` beside `.env*` is the author's exemption, and
    the gate honours it rather than carrying a rule of its own."""
    repo = _scratch_repo(tmp_path)
    (repo / ".gitignore").write_text(".env*\n!.env.keep\n", encoding="utf-8")
    (repo / ".env.keep").write_text("KEEP=1\n", encoding="utf-8")
    (repo / ".env.drop").write_text("TOKEN=x\n", encoding="utf-8")
    _git(repo, tmp_path, "add", ".gitignore", ".env.keep")
    assert _run(repo, tmp_path).returncode == 0
    _git(repo, tmp_path, "add", "-f", ".env.drop")
    result = _run(repo, tmp_path)
    assert (
        result.returncode == 1
        and "\n.env.drop\n" in result.stdout
        and ".env.keep" not in result.stdout
    )


def test_a_symlink_target_holding_a_nul_is_rendered_without_a_bash_warning(tmp_path: Path) -> None:
    """Round 10 (by mutation): `$(cat)` dropped the NUL with a bash warning on stderr — a third
    voice on the channel the header promises is git's notes only."""
    repo = _scratch_repo(tmp_path)
    sha = (
        _git(repo, tmp_path, "hash-object", "-w", "--stdin", input=HOME_PATH.encode() + b"x\0y\n")
        .decode()
        .strip()
    )
    _git(repo, tmp_path, "update-index", "--add", "--cacheinfo", f"120000,{sha},lnk")
    result = _run(repo, tmp_path)
    assert result.returncode == 1 and "lnk -> /home/" in result.stdout, (
        result.stdout + result.stderr
    )
    assert "x?y" in result.stdout and "warning" not in result.stderr, result.stdout + result.stderr

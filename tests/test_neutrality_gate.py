"""The gate that keeps private paths, e-mails and .env files out of a repository about to go public.

Its pass condition is silence, which is also what a gate that scanned nothing prints — so the
controls are planted violations that have to be caught, and the scan reports how many files it
read (not how many are tracked: binaries and empty files are never read), derived here by a
different instrument than the script's own. It runs over the whole tree from any directory.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "neutrality.sh"


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """The script resolves the repository from the cwd (`git rev-parse --show-toplevel`)."""
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )


def _expected_summary() -> str:
    """Independent of the script: a file grep -I skips is empty or holds a NUL byte."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout
    paths = [p for p in out.decode("utf-8").split("\0") if p]
    skipped = sum(1 for p in paths if (d := (ROOT / p).read_bytes()) == b"" or b"\0" in d)
    return (
        f"neutrality: scanned {len(paths)} tracked files for private paths (all bytes), "
        f"{len(paths) - skipped} text files for e-mails ({skipped} binary or empty skipped), 0 hits"
    )


def test_the_self_test_catches_both_planted_violation_classes_and_checks_the_env_pattern() -> None:
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test: private path caught" in result.stdout
    assert "self-test: private path behind a NUL byte caught" in result.stdout
    assert "self-test: e-mail caught" in result.stdout
    assert (
        "self-test: .env pattern matches .env.local and sub/dir/.env, not .envrc" in result.stdout
    )


def test_the_tracked_tree_is_clean_and_the_scan_names_what_it_read() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert _expected_summary() in result.stdout


def test_the_scan_covers_the_whole_tree_from_a_subdirectory() -> None:
    """Measured 2026-08-26: without `cd` to the root, `docs/` reported 32 files scanned, exit 0."""
    result = _run(cwd=ROOT / "docs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _expected_summary() in result.stdout


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with one clean tracked file; the real script runs against it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "clean.md").write_text("nothing to see\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "clean.md"], cwd=repo, check=True)
    return repo


def test_a_planted_env_file_fails_the_gate_at_any_depth_and_envrc_does_not(tmp_path: Path) -> None:
    """The first rewrite of this check (`ls .env .env.*`) let a planted `.env.local` pass, and the
    second only looked at the root; this control runs the real script on real planted files."""
    repo = _scratch_repo(tmp_path)
    clean = _run(cwd=repo)
    assert clean.returncode == 0, clean.stdout + clean.stderr

    (repo / ".envrc").write_text("use nix\n", encoding="utf-8")
    assert _run(cwd=repo).returncode == 0

    (repo / ".env.local").write_text("TOKEN=x\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 1 and "./.env.local" in result.stdout, result.stdout + result.stderr
    (repo / ".env.local").unlink()

    (repo / "sub").mkdir()
    (repo / "sub" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    result = _run(cwd=repo)
    assert result.returncode == 1 and "./sub/.env" in result.stdout, result.stdout + result.stderr

    subprocess.run(["git", "add", "-f", "sub/.env"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "tracked .env file:" in result.stdout, result.stdout


def test_a_tracked_file_missing_from_the_working_tree_fails_the_gate(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    (repo / "clean.md").unlink()
    result = _run(cwd=repo)
    assert result.returncode == 1 and "clean.md" in result.stdout, result.stdout + result.stderr


def test_a_private_path_inside_a_binary_file_is_caught(tmp_path: Path) -> None:
    """Measured 2026-08-27: a path in a PNG text chunk was invisible to `grep -I`."""
    repo = _scratch_repo(tmp_path)
    (repo / "figure.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00tEXtSource\x00rendered on /home/" + b"some" + b"one/\n"
    )
    subprocess.run(["git", "add", "figure.png"], cwd=repo, check=True)
    result = _run(cwd=repo)
    assert result.returncode == 1 and "private path leak:" in result.stdout, (
        result.stdout + result.stderr
    )

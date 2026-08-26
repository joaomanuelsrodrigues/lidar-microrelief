"""The gate that keeps private paths and e-mails out of a repository about to go public.

Its pass condition is silence, which is also what a gate that scanned nothing prints — so the
control is a planted violation that has to be caught, and the scan reports how many files it read
(not how many are tracked: binaries and empty files are never read). It runs over the whole tree
from any directory.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "neutrality.sh"


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def _expected_summary() -> str:
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    n_tracked = tracked.count("\n")
    skipped = subprocess.run(
        "git ls-files -z | xargs -0 -r grep -IL .",
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.count("\n")
    return (
        f"neutrality: scanned {n_tracked - skipped} text files of {n_tracked} tracked "
        f"({skipped} binary or empty skipped), 0 hits"
    )


def test_the_self_test_catches_both_planted_violation_classes_and_checks_the_env_pattern() -> None:
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test: private path caught" in result.stdout
    assert "self-test: e-mail caught" in result.stdout
    assert "self-test: .env pattern matches .env.local, not .envrc" in result.stdout


def test_the_tracked_tree_is_clean_and_the_scan_names_what_it_read() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert _expected_summary() in result.stdout


def test_the_scan_covers_the_whole_tree_from_a_subdirectory() -> None:
    """Measured 2026-08-26: without `cd` to the root, `docs/` reported 32 files scanned, exit 0."""
    result = _run(cwd=ROOT / "docs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _expected_summary() in result.stdout

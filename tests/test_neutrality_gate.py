"""The gate that keeps private paths and e-mails out of a repository about to go public.

Its pass condition is silence, which is also what a gate that scanned nothing prints — so the
control is a planted violation that has to be caught, and the scan reports how many files it read.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "neutrality.sh"


def test_the_self_test_catches_both_planted_violation_classes() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--self-test"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test: private path caught" in result.stdout
    assert "self-test: e-mail caught" in result.stdout


def test_the_tracked_tree_is_clean_and_the_scan_names_its_denominator() -> None:
    result = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout.count("\n")
    assert f"neutrality: scanned {tracked} tracked files, 0 hits" in result.stdout

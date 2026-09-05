"""The scan that reads the history rather than the index.

The neutrality gate reads what the current tree publishes; making a repository public publishes
every blob every ref still reaches, including files deleted releases ago. This is the tests for
the instrument that asks the second question. Its own pass condition is silence too, so the tests
below plant a violation that only the HISTORY carries -- the scratch tip is clean and an
index-scoped scan finds nothing in it -- and require the scan to find it, then require silence on
a clean history, then require exit 2 where the instrument cannot be trusted.

The real run over this repository's own history is not exercised here: CI checks out with
`fetch-depth: 2`, so a full scan there would print a truncated denominator that means nothing.
The script refuses a shallow repository for that reason, and that refusal is tested.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "histscan.sh"
GATE = ROOT / "scripts" / "neutrality.sh"
# Assembled: this file is a tracked blob that both scans read.
HOME_PATH = "/home/" + "some" + "one/keys"
FIXTURE_MAIL = "t" + "@" + "example.invalid"


def _env(tmp_path: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        HOME=str(tmp_path),
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL=FIXTURE_MAIL,
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL=FIXTURE_MAIL,
    )
    return env


def _run(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=repo, env=env, capture_output=True, text=True
    )


def _repo(tmp_path: Path, env: dict[str, str], name: str, commits: list[str]) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    for i, body in enumerate(commits):
        (repo / "note.md").write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "--", "note.md"], cwd=repo, env=env, check=True)
        subprocess.run(["git", "commit", "-qm", f"c{i}"], cwd=repo, env=env, check=True)
    return repo


def test_the_scripts_self_test_passes() -> None:
    """The script's own three arms, run as CI runs them."""
    r = subprocess.run(["bash", str(SCRIPT), "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "self-test: passed" in r.stdout


def test_it_finds_a_leak_the_index_scoped_gate_cannot_see(tmp_path: Path) -> None:
    """The whole reason the script exists, asserted as a difference between the two scans."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, "dirty", [f"a note about {HOME_PATH}\n", "a note about nothing\n"])

    tip = subprocess.run(["git", "grep", "-qaE", "/home/[A-Za-z0-9._-]+/"], cwd=repo, env=env)
    assert tip.returncode != 0, "the scratch tip is not clean; the comparison proves nothing"

    r = _run(repo, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "HIT   private-path" in r.stdout
    assert "1 judged hit(s)" in r.stdout


def test_it_is_silent_on_a_history_that_never_carried_one(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, "clean", ["a note about nothing\n", "still nothing\n"])
    r = _run(repo, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "HIT" not in r.stdout
    assert "0 judged hit(s)" in r.stdout


def test_it_refuses_a_shallow_clone_rather_than_scanning_a_truncated_history(
    tmp_path: Path,
) -> None:
    """A shallow scan's green is the vacuous kind: a small denominator over a history that is not
    there. This is what keeps the script from being cited off a CI checkout."""
    env = _env(tmp_path)
    origin = _repo(tmp_path, env, "origin", [f"a note about {HOME_PATH}\n", "a note about none\n"])
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{origin}", str(shallow)],
        env=env,
        check=True,
        capture_output=True,
    )
    r = _run(shallow, env)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "shallow" in r.stderr
    assert "histscan:" not in r.stdout, "an instrument failure must not print a summary"


def test_it_reads_the_gates_patterns_and_refuses_to_invent_its_own(tmp_path: Path) -> None:
    """One rule, one definition. A repository that publishes one and enforces another has the one
    it enforces, so the scan reads the gate's literals rather than keeping a copy that can drift.
    """
    text = GATE.read_text(encoding="utf-8")
    assert len([ln for ln in text.splitlines() if ln.startswith("PRIVATE_PATH=")]) == 1
    assert len([ln for ln in text.splitlines() if ln.startswith("EMAIL=")]) == 1

    env = _env(tmp_path)
    broken = tmp_path / "scripts"
    broken.mkdir()
    (broken / "neutrality.sh").write_text("# no patterns here\n", encoding="utf-8")
    (broken / "histscan.sh").write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    repo = _repo(tmp_path, env, "any", ["a note about nothing\n"])
    r = subprocess.run(
        ["bash", str(broken / "histscan.sh")], cwd=repo, env=env, capture_output=True, text=True
    )
    assert r.returncode == 2, r.stdout + r.stderr
    assert "PRIVATE_PATH" in r.stderr
    assert "histscan:" not in r.stdout


def test_a_judged_hit_is_text_and_a_binary_one_is_listed_not_hidden(tmp_path: Path) -> None:
    """An address-shaped run of bytes inside compressed data is a coincidence, not an address --
    but hiding it would be a scan choosing what to report. It is listed, unjudged, and the exit
    code stays clean."""
    env = _env(tmp_path)
    repo = tmp_path / "binary"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    address = "some" + "one" + "@" + "example.org"
    (repo / "blob.bin").write_bytes(b"\x00\x01" + address.encode() + b"\x00note\n")
    subprocess.run(["git", "add", "--", "blob.bin"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=repo, env=env, check=True)
    r = _run(repo, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "LIST  e-mail-shaped" in r.stdout
    assert "0 judged hit(s), 1 listed not judged" in r.stdout


def test_the_reported_byte_total_is_what_git_says_those_blobs_weigh(tmp_path: Path) -> None:
    """The always-on control, checked against a denominator derived here by another instrument.

    The scan requires every blob's read to match the size git declares; a truncated or failed
    read would otherwise look exactly like a blob with nothing in it. This asserts the total it
    reports, computed from `cat-file --batch-check` rather than from the scan's own accounting.
    """
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, "weighed", ["a note about nothing\n", "a longer note about it\n"])
    (repo / "second.md").write_text("a third blob, of a different length\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "second.md"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-qm", "c2"], cwd=repo, env=env, check=True)

    objects = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    shas = "\n".join(line.split(" ")[0] for line in objects if line)
    sizes = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectsize)"],
        cwd=repo,
        env=env,
        input=shas,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    expected = sum(int(ln.split()[1]) for ln in sizes.splitlines() if ln.startswith("blob "))
    assert expected > 0

    r = _run(repo, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"{expected} byte(s) read" in r.stdout, (r.stdout, expected)


def test_it_finds_a_leak_reachable_only_from_a_branch_that_is_not_HEAD(tmp_path: Path) -> None:
    """The script's actual claim: every ref, not the checked-out one.

    A scan of `HEAD`'s ancestry passes this repository's other tests -- the leak in them is an
    ancestor of the tip. It is not the claim being made. Here the leaking commit is reachable
    only from a side branch, which is precisely what a flip publishes and a tip-scoped scan
    cannot see.
    """
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, "sidebranch", ["a note about nothing\n"])
    subprocess.run(["git", "checkout", "-qb", "side"], cwd=repo, env=env, check=True)
    (repo / "note.md").write_text(f"a note about {HOME_PATH}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "note.md"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-qm", "the leak, on a branch"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "checkout", "-q", "-"], cwd=repo, env=env, check=True)

    reachable_from_head = subprocess.run(
        ["git", "rev-list", "--objects", "HEAD"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    on_all_refs = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert len(on_all_refs) > len(reachable_from_head), "the fixture does not exercise the claim"

    r = _run(repo, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "HIT   private-path" in r.stdout


def test_a_short_read_is_an_instrument_failure_not_a_blob_with_nothing_in_it(
    tmp_path: Path,
) -> None:
    """The always-on control, killed the only way it can be: by breaking the read.

    Deleting the check while the read is correct changes nothing a test can see -- in production
    there is no independently known byte total, so this comparison is the only thing that would
    notice. A `git` shim on PATH truncates `cat-file blob` and the scan must refuse rather than
    report silence over three bytes per blob.
    """
    import shutil

    real_git = shutil.which("git")
    assert real_git
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, "truncated", [f"a note about {HOME_PATH}\n", "a note about it\n"])

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'case " $* " in\n'
        f'  *" cat-file blob "*) {real_git} "$@" | head -c 3; exit 0 ;;\n'
        f'  *) exec {real_git} "$@" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    env["PATH"] = f"{shim_dir}:{env['PATH']}"

    r = _run(repo, env)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "git declares" in r.stderr, r.stderr
    assert "judged hit(s)" not in r.stdout, "an instrument failure must not print a summary"


def test_an_address_in_a_text_blob_is_judged_a_hit(tmp_path: Path) -> None:
    """The other half of the e-mail rule: listed in a binary blob, JUDGED in a text one.

    Without this, turning every e-mail hit into an unjudged listing passes the whole file --
    measured, it did.
    """
    env = _env(tmp_path)
    address = "some" + "one" + "@" + "example.org"
    repo = _repo(tmp_path, env, "addressed", [f"write to {address}\n", "a note about nothing\n"])
    r = _run(repo, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "HIT   e-mail" in r.stdout
    assert "1 judged hit(s), 0 listed not judged" in r.stdout

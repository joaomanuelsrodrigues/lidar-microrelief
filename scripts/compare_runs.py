"""Are two runs the same run?

Not a file-hash comparison: `package_version` and `reproducibility_hash` are written into every
raster's tags, so a version bump changes all six files' bytes while changing nothing that was
measured. What must be identical is the data — every cell of every band, NoData included — and
every field of the record except the three the bump is allowed to move. `known_limitations` is
the one field that changes on purpose, so it is asserted rather than permitted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

PERMITTED_RECORD_DIFFS = {"package_version", "created_utc", "reproducibility_hash"}

# `known_limitations` changes on purpose at a release that declares something new. It is NOT in
# PERMITTED_RECORD_DIFFS: permitting the field wholesale would let any limitation appear or
# vanish unnoticed, and the whole point of this instrument is that every difference is one we
# named in advance. So it is asserted instead — the new record must be the old one plus exactly
# the lines below, in order. They are written out here rather than imported from
# `cli.LIMITATIONS` on purpose: importing them would make the instrument agree with whatever the
# code says, and a typo in either place would pass. Two independent statements that must match
# is the check, which is also why each release keeps its own entry instead of being rewritten:
# an old acceptance command recorded in `docs/live-smoke.md` must still replay.
EXPECTED_NEW_LIMITATIONS = {
    "0.4.0": (
        "Calling select_tiles as a library function bypasses the AOI-vs-tile CRS check, which "
        "lives at the CLI's composition root.",
        "scripts/measure_risers.py takes no --crs, so it can only work an AOI that declares its "
        "own projected CRS.",
    ),
    "0.4.1": (
        "The reproducibility hash does not cover the attribution string: two runs differing "
        "only in --attribution share a hash, so a product can be relabelled and keep its anchor.",
        "The only resource ceiling is a cell count (200,000,000 cells, ~12 GB of per-cell "
        "arrays), not a memory bound: a grid inside it can still exhaust memory, and that "
        "failure is an OOM kill rather than a refusal with a reason.",
    ),
}


def compare(old: Path, new: Path, expect_new_limitations: bool = False) -> int:
    problems: list[str] = []

    old_bands = sorted(p.name for p in old.glob("*.tif"))
    new_bands = sorted(p.name for p in new.glob("*.tif"))
    if old_bands != new_bands:
        problems.append(f"band sets differ: {old_bands} vs {new_bands}")
    if not old_bands:
        # Silence-by-nothing-scanned and silence-by-clean-comparison must not look alike.
        problems.append(f"no rasters found in {old}; this comparison checked nothing")

    compared = 0
    for name in old_bands:
        if name not in new_bands:
            continue
        with rasterio.open(old / name) as a, rasterio.open(new / name) as b:
            ba, bb = a.read(1), b.read(1)
            if ba.shape != bb.shape:
                problems.append(f"{name}: shape {ba.shape} vs {bb.shape}")
                continue
            # `!=` is the whole comparison, and NaN != NaN, so a NaN anywhere would report as a
            # difference between a run and itself. `export._prepare` writes explicit NoData
            # instead of NaN precisely so that cannot happen — this asserts that premise rather
            # than assuming it, because if it ever stopped holding the verdict below would be
            # wrong in the direction that reads as "investigate", not as "clean" (2026-08-05).
            nans = [
                label
                for label, arr in (("old", ba), ("new", bb))
                if arr.dtype.kind == "f" and bool(np.isnan(arr).any())
            ]
            if nans:
                problems.append(f"{name}: NaN present in {', '.join(nans)}; != cannot compare it")
            differing = int((ba != bb).sum())
            if differing:
                problems.append(f"{name}: {differing} of {ba.size} cells differ")
            if a.nodata != b.nodata:
                problems.append(f"{name}: nodata {a.nodata} vs {b.nodata}")
            if a.transform != b.transform:
                problems.append(f"{name}: transform moved")
        compared += 1
        print(f"{name}: {ba.size} cells compared")
    print(f"{compared} raster(s) compared")

    doc_a = json.loads((old / "provenance.json").read_text())
    doc_b = json.loads((new / "provenance.json").read_text())
    for key in sorted(set(doc_a) | set(doc_b)):
        if key in PERMITTED_RECORD_DIFFS or key == "known_limitations":
            continue
        if doc_a.get(key) != doc_b.get(key):
            problems.append(f"provenance.{key} changed")
    for key in sorted(PERMITTED_RECORD_DIFFS):
        print(f"provenance.{key}: {doc_a.get(key)} -> {doc_b.get(key)}")

    old_lims = tuple(doc_a.get("known_limitations") or ())
    new_lims = tuple(doc_b.get("known_limitations") or ())
    # The release is READ FROM THE NEW RUN, not passed in: the record already says which
    # version produced it, and a flag would let you assert 0.4.0's additions against a 0.4.1
    # record by accident. It also keeps this an `action="store_true"` flag -- an optional-value
    # flag placed before the two positionals makes argparse swallow one of them, which silently
    # broke both acceptance commands recorded in docs/live-smoke.md (measured, s293).
    release = str(doc_b.get("package_version") or "")
    # An unknown release is a refusal, and a refusal makes exactly ONE claim. Falling back to
    # the old list here and then comparing against it produced a second problem line asserting
    # an expectation the instrument had just said it does not hold -- "known_limitations is not
    # the old list plus the two declared gaps" beside "no expected limitations are recorded
    # here" -- which sends a reader after a limitations bug that does not exist (s295).
    unknown_release = expect_new_limitations and release not in EXPECTED_NEW_LIMITATIONS
    if unknown_release:
        problems.append(
            f"the new run declares version {release!r}, for which no expected limitations "
            f"are recorded here; known: {', '.join(sorted(EXPECTED_NEW_LIMITATIONS))}"
        )
    expected = (
        old_lims + EXPECTED_NEW_LIMITATIONS[release]
        if expect_new_limitations and not unknown_release
        else old_lims
    )
    if not unknown_release and new_lims != expected:
        wanted = (
            "the old list plus the two declared gaps" if expect_new_limitations else "unchanged"
        )
        problems.append(
            f"provenance.known_limitations is not {wanted}: "
            f"expected {len(expected)} entries, got {len(new_lims)}; "
            f"added {sorted(set(new_lims) - set(old_lims))}, "
            f"removed {sorted(set(old_lims) - set(new_lims))}"
        )
    print(f"provenance.known_limitations: {len(old_lims)} -> {len(new_lims)} entries")

    if problems:
        print("\nDIFFERENCES:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(
        "\nidentical in every band and every record field but the three permitted, and "
        + (
            "known_limitations gained exactly the two declared gaps"
            if expect_new_limitations
            else "known_limitations unchanged"
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The argv contract, exposed so a test can parse the commands recorded in the docs.

    `main()` used to build this inline, which meant the only way to check a recorded command
    line was to run the whole comparison. Every command written into `docs/live-smoke.md` is a
    claim about what this parser accepts, and twice now such a claim was published without ever
    being run (s293, s295) -- so the claim is now checkable against the parser itself.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument(
        "--expect-new-limitations",
        action="store_true",
        help="require known_limitations to be the old list plus exactly the two gaps the NEW "
        "run's own version declares (known: " + ", ".join(sorted(EXPECTED_NEW_LIMITATIONS)) + "). "
        "OFF by default, because a run-to-run control compares two builds of the same version, "
        "where the list must be unchanged. Takes no value on purpose -- see the comment in "
        "compare(); exercised in the recorded position by tests/test_compare_runs.py.",
    )
    return ap


def main() -> int:
    args = build_parser().parse_args()
    return compare(args.old, args.new, args.expect_new_limitations)


if __name__ == "__main__":
    raise SystemExit(main())

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

# `known_limitations` also changes, because Task 7 Step 3 appends two declared gaps to it. It is
# NOT in PERMITTED_RECORD_DIFFS: permitting the field wholesale would let any limitation appear or
# vanish unnoticed, and the whole point of this instrument is that every difference is one we
# named in advance. So it is asserted instead — the new record must be the old one plus exactly
# these two lines, in order. They are written out here rather than imported from `cli.LIMITATIONS`
# on purpose: importing them would make the instrument agree with whatever the code says, and a
# typo in either place would pass. Two independent statements that must match is the check.
EXPECTED_NEW_LIMITATIONS = (
    "Calling select_tiles as a library function bypasses the AOI-vs-tile CRS check, which "
    "lives at the CLI's composition root.",
    "scripts/measure_risers.py takes no --crs, so it can only work an AOI that declares its "
    "own projected CRS.",
)


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
    expected = old_lims + EXPECTED_NEW_LIMITATIONS if expect_new_limitations else old_lims
    if new_lims != expected:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument(
        "--expect-new-limitations",
        action="store_true",
        help="require known_limitations to be the old list plus exactly the two gaps Task 7 "
        "Step 3 declares. OFF by default, because a run-to-run control compares two builds of "
        "the same version, where the list must be unchanged. Only the 0.3.0-vs-0.4.0 "
        "acceptance in Step 6 passes it.",
    )
    args = ap.parse_args()
    return compare(args.old, args.new, args.expect_new_limitations)


if __name__ == "__main__":
    raise SystemExit(main())

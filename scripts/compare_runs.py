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
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

PERMITTED_RECORD_DIFFS = {"package_version", "created_utc", "reproducibility_hash"}


class ChangeError(ValueError):
    """A declared transformation does not apply to the list it was handed."""


@dataclass(frozen=True)
class LimitationChange:
    """What one release does to the declared list, as an ordered transformation.

    Two operations, applied in this order: `replaced` rewrites a line **in place**, keeping its
    position; `added` appends. An append-only expectation could not express a release that swaps
    a component — the rewritten line would read as one unexpected removal plus one unexpected
    addition, which is the difference this instrument exists to name rather than to report.
    """

    replaced: tuple[tuple[str, str], ...] = ()
    added: tuple[str, ...] = ()

    @property
    def declared(self) -> int:
        return len(self.replaced) + len(self.added)


def apply_change(old: tuple[str, ...], change: LimitationChange) -> tuple[str, ...]:
    """The old list under one release's declared transformation.

    A replacement whose `old` half is not in the list is a **refusal**, not an append: a typo
    there would otherwise add a second copy and leave both looking declared.
    """
    out = list(old)
    for before, after in change.replaced:
        if before not in out:
            raise ChangeError(
                f"the release declares a replacement of a line the old run does not carry: "
                f"{before!r}"
            )
        out[out.index(before)] = after
    return tuple(out) + change.added


# `known_limitations` changes on purpose at a release that declares something new. It is NOT in
# PERMITTED_RECORD_DIFFS: permitting the field wholesale would let any limitation appear or
# vanish unnoticed, and the whole point of this instrument is that every difference is one we
# named in advance. So it is asserted instead — the new record must be the old one under exactly
# the transformation below. The lines are written out here rather than imported from
# `cli.LIMITATIONS` on purpose: importing them would make the instrument agree with whatever the
# code says, and a typo in either place would pass. Two independent statements that must match
# is the check, which is also why each release keeps its own entry instead of being rewritten:
# an old acceptance command recorded in `docs/live-smoke.md` must still replay.
RELEASE_LIMITATIONS = {
    "0.4.0": LimitationChange(
        added=(
            "Calling select_tiles as a library function bypasses the AOI-vs-tile CRS check, "
            "which lives at the CLI's composition root.",
            "scripts/measure_risers.py takes no --crs, so it can only work an AOI that declares "
            "its own projected CRS.",
        )
    ),
    "0.4.1": LimitationChange(
        added=(
            "The reproducibility hash does not cover the attribution string: two runs differing "
            "only in --attribution share a hash, so a product can be relabelled and keep its "
            "anchor.",
            "The only resource ceiling is a cell count (200,000,000 cells, ~12 GB of per-cell "
            "arrays), not a memory bound: a grid inside it can still exhaust memory, and that "
            "failure is an OOM kill rather than a refusal with a reason.",
        )
    ),
    "0.4.4": LimitationChange(
        added=(
            "The ground filter does not remove buildings, and the basis band calls the result "
            "measured: over cells holding official building returns and no ground return, 77.2% "
            "publish as measured ground at the site shipped here and 89.7% at a built site, both "
            "measured 2026-08-31. No parameter fixes it: the best single height threshold "
            "separates a roof from the terrain it stands on at 0.712 balanced accuracy and the "
            "best width threshold at 0.528 (docs/ground-filter-diagnosis.md).",
        )
    ),
    # 0.5.0 swaps the ground filter, so one declared limitation stops being true of the shipped
    # tool and is rewritten in place rather than left standing beside its successor. The 89.7%
    # in the line it replaces is also the live defect this release carries out: that figure is
    # row C's, over a population `docs/reference-instrument-result.md` records as not
    # re-derivable, while the sentence names row B's. The right number for the population named
    # was 87.7%, and the filter that produced it is the one going away.
    "0.5.0": LimitationChange(
        replaced=(
            (
                "The ground filter does not remove buildings, and the basis band calls the "
                "result measured: over cells holding official building returns and no ground "
                "return, 77.2% publish as measured ground at the site shipped here and 89.7% at "
                "a built site, both measured 2026-08-31. No parameter fixes it: the best single "
                "height threshold separates a roof from the terrain it stands on at 0.712 "
                "balanced accuracy and the best width threshold at 0.528 "
                "(docs/ground-filter-diagnosis.md).",
                "The ground filter does not remove every building, and the basis band calls what "
                "it keeps measured: over cells holding official building returns and no ground "
                "return, 16.4% publish as measured ground at a built site near Valongo. The "
                "filter this release replaces published 87.7% of that same population "
                "(docs/reference-instrument-result.md).",
            ),
        ),
        added=(
            "Terrace preservation is measured, not enforced. This filter has no cap on how far "
            "it may cut, so that risers survive is an empirical result at one site: 91.078% of "
            "the cells the previous filter called measured ground are kept, and 95.082% of those "
            "standing on a step above 2.5 m (docs/p4-terrace-result.md). The filter it replaces "
            "guaranteed it by construction, through a parameter this one does not have.",
            "The grid cell must divide the 1 m analysis cell, so --cell takes 1/k metres and "
            "refuses anything else. The grid is also grown outward to whole analysis blocks, "
            "which can add one cell per axis beyond the requested AOI; a cell added there "
            "publishes what was measured in it, not undetermined, whenever it falls inside a "
            "source tile.",
        ),
    ),
}


def compare(
    old: Path, new: Path, expect_new_limitations: bool = False, record_only: bool = False
) -> int:
    problems: list[str] = []

    old_bands = sorted(p.name for p in old.glob("*.tif"))
    new_bands = sorted(p.name for p in new.glob("*.tif"))
    if not record_only:
        if old_bands != new_bands:
            problems.append(f"band sets differ: {old_bands} vs {new_bands}")
        if not old_bands:
            # Silence-by-nothing-scanned and silence-by-clean-comparison must not look alike.
            problems.append(f"no rasters found in {old}; this comparison checked nothing")

    compared = 0
    for name in [] if record_only else old_bands:
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
    if record_only:
        print(f"bands not compared ({len(new_bands)} present): --record-only")
    else:
        print(f"{compared} raster(s) compared")

    doc_a = json.loads((old / "provenance.json").read_text())
    doc_b = json.loads((new / "provenance.json").read_text())
    if record_only and str(doc_a.get("package_version")) == str(doc_b.get("package_version")):
        # Between two builds of one version the bands ARE the question. A flag able to skip them
        # there would be a way to pass a self-replay without replaying anything.
        print(
            "--record-only compares across a version boundary; both runs declare "
            f"{doc_b.get('package_version')!r}, where the bands are the whole comparison",
            file=sys.stderr,
        )
        return 2
    for key in sorted(set(doc_a) | set(doc_b)):
        if key in PERMITTED_RECORD_DIFFS or key == "known_limitations":
            continue
        if doc_a.get(key) != doc_b.get(key):
            if record_only:
                # Named, never merely allowed: a field that moved across a release is something
                # a reader has to see, and the difference between this mode and permitting the
                # field is that this one says which.
                print(f"provenance.{key}: changed (not asserted under --record-only)")
            else:
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
    unknown_release = expect_new_limitations and release not in RELEASE_LIMITATIONS
    if unknown_release:
        problems.append(
            f"the new run declares version {release!r}, for which no expected limitations "
            f"are recorded here; known: {', '.join(sorted(RELEASE_LIMITATIONS))}"
        )

    expected = old_lims
    wanted = "unchanged"
    if expect_new_limitations and not unknown_release:
        change = RELEASE_LIMITATIONS[release]
        # The count comes from the mapping, never from a sentence. "the two declared gaps" was
        # written into both this message and the success line, and was already false for 0.4.4,
        # which declared one: a number typed into a message is a published number (s295).
        wanted = (
            f"the old list under {release}'s declared transformation "
            f"({len(change.replaced)} replaced, {len(change.added)} added)"
        )
        try:
            expected = apply_change(old_lims, change)
        except ChangeError as exc:
            problems.append(str(exc))
            expected = new_lims  # the comparison below has nothing left to say
    if not unknown_release and new_lims != expected:
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
    verdict = (
        "the bands were not compared; every record field that moved is named above, and "
        if record_only
        else "identical in every band and every record field but the three permitted, and "
    )
    print(
        "\n"
        + verdict
        + (f"known_limitations is exactly {wanted}" if expect_new_limitations else wanted)
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
        help="require known_limitations to be the old list under exactly the transformation the "
        "NEW run's own version declares -- lines replaced in place, then lines added (known: "
        + ", ".join(sorted(RELEASE_LIMITATIONS))
        + "). "
        "OFF by default, because a run-to-run control compares two builds of the same version, "
        "where the list must be unchanged. Takes no value on purpose -- see the comment in "
        "compare(); exercised in the recorded position by tests/test_compare_runs.py.",
    )
    ap.add_argument(
        "--record-only",
        action="store_true",
        help="skip the band comparison and assert only the record. The one use is a release that "
        "changes every band ON PURPOSE -- swapping the ground filter, say -- where the "
        "band-identity spine has no verdict to give and the limitation transformation would "
        "otherwise never be exercised by an acceptance run. Refuses two runs of the same "
        "version, where the bands are the whole question. Record fields that moved are printed "
        "by name rather than permitted silently.",
    )
    return ap


def main() -> int:
    args = build_parser().parse_args()
    return compare(args.old, args.new, args.expect_new_limitations, args.record_only)


if __name__ == "__main__":
    raise SystemExit(main())

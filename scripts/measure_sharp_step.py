#!/usr/bin/env python3
"""The zone-wide instrument for `docs/sharp-step-preregistration.md`.

That document fixes, before this ran once on real data, a population (`S1` the P4-shaped range
term over Zone Z, `S2` those of its cells whose window also departs from a plane) and three
predicates over it. This script evaluates them and prints the reported block beside them.

Exit codes, and 1 carries two meanings that the last line of output tells apart:

    0   all three predicates pass
    1   at least one was refuted (FAIL), or at least one could not be evaluated against this
        cache (NOT EVALUABLE) -- the second is not a refutation, and the summary says which
    2   the instrument is broken, not the population: `S1` empty, or `S1` non-empty with not one
        computable residual. Neither must ever read as a pass.

    python scripts/measure_sharp_step.py --reference <zone-z-cache>.npz

The cache is the one `scripts/measure_risers.py build` writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microrelief.accumulate import CellStats  # noqa: E402
from microrelief.density import BASIS_MEASURED, compute_basis  # noqa: E402
from microrelief.ground import GroundParams, classify_ground  # noqa: E402
from microrelief.smrf import SmrfParams, classify_ground_smrf  # noqa: E402


def _sibling(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cgf = _sibling("compare_ground_filters")
# One definition of the zone, imported rather than restated: `docs/riser-measurement.md` fixes it
# and `scripts/measure_risers.py` is what that document's numbers came from.
ZONE: tuple[float, float, float, float] = _sibling("measure_risers").ZONE

# The five supported real steps of `docs/riser-measurement.md`. The four ranked ones are locked
# against `docs/figures/riser/report.json` by the tests; the terrace riser is not in that file --
# `top_clusters` holds the twenty tallest candidates and all of them are far above 2.98 m -- so it
# is sourced from the document's prose alone, which the pre-registration declares.
VERIFIED_STEPS: tuple[tuple[str, float, float], ...] = (
    ("terrace riser 2.98 m", -20132.8, 256319.2),
    ("built wall (rank 4)", -19899.25, 255961.75),
    ("churchyard wall (rank 8)", -19916.75, 256173.75),
    ("gully/lane edge (rank 10)", -20007.75, 255932.25),
    ("built wall (rank 11)", -19905.25, 255974.25),
)
G1_TOLERANCE_M = 2.0
# `SmrfParams`'s own defaults are PDAL's, kept verbatim in that dataclass, so the reference
# configuration is spelled by constructing it empty. The first version of this line retyped the
# five values under a comment claiming they had been taken from the sibling that owns them --
# a third unlocked copy of exactly the literals the comment warned about.
SMRF_REFERENCE = SmrfParams()
# The two basis parameters the pipeline still takes as flags. `GroundParams`'s four live in that
# dataclass; these two are declared only on `compare_ground_filters`'s parsers, so they are named
# here and locked against those declarations by this script's tests.
BASIS_K_MIN_RETURNS = 1
BASIS_D_MAX_INTERP_M = 2.0
G2_DEGREES = (31.0, 35.0, 40.0, 45.0, 50.0, 60.0)
NEAR_PLANAR_M = 0.10


@dataclass(frozen=True)
class Hit:
    """`inside` is not decoration: without it, a location the cache cannot contain reports
    `found=False`, which is byte-identical to a location present in the extent and absent from
    the population. The first is a question this cache cannot answer; the second is a failure."""

    name: str
    row: int
    col: int
    inside: bool
    # `inside` means the whole 2 m disc is searchable. When the centre is in frame but the disc
    # is not, the honest reason is a truncated neighbourhood, not "outside the extent" -- a
    # refusal with a false reason masks the true one.
    centre_inside: bool
    found: bool
    residual: float
    hit_row: int | None = None
    hit_col: int | None = None


@dataclass(frozen=True)
class G2Verdict:
    reached_s1: int
    entered_s2: int
    permitted: int
    of_n: int

    @property
    def passed(self) -> bool:
        """Both halves, with the first one derived rather than chosen.

        A ramp only reaches the range term if its slope spans the threshold across the window, so
        `permitted` is computed from geometry: at 0.5 m cells a 7-cell window separates cells by
        3.0 m along an axis and 4.243 m across the diagonal, and 31 and 35 degrees axis-aligned
        cannot span 2.5 m at either. Requiring *every* permitted ramp is exact; requiring a count
        would accept a regression that silently kills the ones left over.

        `permitted == 0` fails: with nothing able to reach `S1`, an empty `S2` says nothing, and
        an instrument that selects nothing would pass the second half perfectly.
        """
        return self.permitted > 0 and self.reached_s1 == self.permitted and self.entered_s2 == 0


def ramp_can_reach(
    degrees: float, diagonal: bool, window_cells: int, cell_m: float, step_threshold_m: float
) -> bool:
    """Can a planar ramp at this slope span the threshold inside the window at all?"""
    span = (window_cells - 1) * cell_m * (np.sqrt(2) if diagonal else 1.0)
    return bool(span * np.tan(np.radians(degrees)) > step_threshold_m)


def _floor_div(numerator: float, cell_m: float) -> int:
    """Floor, not truncation toward zero.

    `int()` rounds -0.6 to 0, so a location up to one cell north or west of the frame reported
    row 0 -- inside -- and printed "neighbourhood truncated at the frame edge" for a step that is
    genuinely outside the extent. A refusal with a false reason, at the exact boundary the
    distinction exists to draw.
    """
    return int(np.floor(numerator / cell_m))


def g1_hits(
    population: NDArray[np.bool_],
    origin_x: float,
    origin_y: float,
    cell_m: float,
    residual: NDArray[np.float64] | None = None,
    tolerance_m: float = G1_TOLERANCE_M,
) -> list[Hit]:
    """Is each verified step in the population, at its own cell or within `tolerance_m` of it?

    The tolerance is a distance in metres, not a neighbourhood in cells: a hit five cells away on
    a 0.5 m grid is 2.5 m away and does not count.
    """
    reach = int(np.floor(tolerance_m / cell_m))
    rows, cols = np.mgrid[-reach : reach + 1, -reach : reach + 1]
    within = (rows**2 + cols**2) * cell_m**2 <= tolerance_m**2 + 1e-9

    out = []
    for name, x, y in VERIFIED_STEPS:
        row = _floor_div(origin_y - y, cell_m)
        col = _floor_div(x - origin_x, cell_m)
        found = False
        value = float("nan")
        hit_row = hit_col = None
        # The whole disc, not just the centre. A location four cells from the crop edge is
        # searched over a silently truncated neighbourhood, so the S2 cell that would satisfy it
        # may be outside the frame -- and reporting that as a miss is the third face of the
        # conflation this instrument has now fixed twice (extent, then residual referent).
        centre_inside = 0 <= row < population.shape[0] and 0 <= col < population.shape[1]
        inside = (
            row - reach >= 0
            and col - reach >= 0
            and row + reach < population.shape[0]
            and col + reach < population.shape[1]
        )
        if inside:
            r0, r1 = max(row - reach, 0), min(row + reach + 1, population.shape[0])
            c0, c1 = max(col - reach, 0), min(col + reach + 1, population.shape[1])
            mask = within[
                r0 - (row - reach) : r1 - (row - reach), c0 - (col - reach) : c1 - (col - reach)
            ]
            hits = np.argwhere(population[r0:r1, c0:c1] & mask)
            found = bool(len(hits))
            if found:
                # The nearest accepted cell, not the centre: G1 accepts a hit anywhere in the
                # disc, so reading G3's residual at the exact centre would report `nan` --
                # undefined -- for a location G1 passed through a neighbour, and print that as a
                # failure. Unanswerable is not absent, one axis over from the extent question.
                offsets = hits + np.array([r0 - row, c0 - col])
                nearest = hits[int(np.argmin((offsets**2).sum(axis=1)))]
                hit_row, hit_col = int(nearest[0] + r0), int(nearest[1] + c0)
                if residual is not None:
                    value = float(residual[hit_row, hit_col])
        out.append(
            Hit(
                name=name,
                row=row,
                col=col,
                inside=inside,
                centre_inside=centre_inside,
                found=found,
                residual=value,
                hit_row=hit_row,
                hit_col=hit_col,
            )
        )
    return out


def g2_verdict(
    cell_m: float,
    window_cells: int = cgf.STEP_WINDOW_CELLS,
    step_threshold_m: float = cgf.P4B_GATE_THRESHOLD_M,
    residual_min_m: float = cgf.SHARP_STEP_RESIDUAL_MIN_M,
) -> G2Verdict:
    """Planar ramps holding no step, axis-aligned and diagonal, at each pre-registered slope."""
    size = 8 * window_cells
    rows, cols = np.mgrid[0:size, 0:size]
    reached = entered = total = permitted = 0
    for degrees in G2_DEGREES:
        gradient = np.tan(np.radians(degrees))
        for diagonal in (False, True):
            along = (rows + cols) / np.sqrt(2) if diagonal else cols
            surface = (along * cell_m * gradient).astype(np.float64)
            result = cgf.sharp_step_population(
                surface,
                cell_m=cell_m,
                window_cells=window_cells,
                step_threshold_m=step_threshold_m,
                residual_min_m=residual_min_m,
            )
            total += 1
            permitted += int(
                ramp_can_reach(degrees, diagonal, window_cells, cell_m, step_threshold_m)
            )
            reached += int(result.candidates.any())
            entered += int(result.population.any())
    return G2Verdict(reached_s1=reached, entered_s2=entered, permitted=permitted, of_n=total)


def g3_exceeds_median(value: float, residual: NDArray[np.float64], s1: NDArray[np.bool_]) -> bool:
    """Is this location more step-like than the typical cell the range term selects?

    An undefined residual is not a pass. `nan > x` is already False; it is spelled out because a
    silent False here would be indistinguishable from a measured failure.
    """
    if not np.isfinite(value):
        return False
    median = float(np.nanmedian(residual[s1]))
    return bool(value > median)


@dataclass(frozen=True)
class Cache:
    """The two cache shapes this instrument reads, behind one name.

    `scripts/measure_risers.py build` writes the zone surface with the grid as loose arrays;
    `compare_ground_filters.py reference` writes the P4 window with the grid inside `provenance`
    and PDAL's own answer beside ours. They are not interchangeable by key, and a script that
    assumed one would fail on the other with a `KeyError` naming a field, which reads like a
    corrupt file rather than the wrong cache.
    """

    surface: NDArray[np.float64]
    min_z_all: NDArray[np.float64]
    max_z_all: NDArray[np.float64]
    n_all: NDArray[np.int32]
    n_ground: NDArray[np.int32]
    origin_x: float
    origin_y: float
    cell_m: float
    pdal_ground: NDArray[np.bool_] | None
    shape_name: str


def read_cache(path: Path) -> Cache:
    with np.load(path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files}

    if "min_z_ground" in arrays:  # measure_risers.py build
        if "min_z_all" not in arrays:
            raise ValueError(
                f"{path} is a measure_risers build cache from before the all-returns surface was "
                f"kept, so the retention this instrument reports cannot be computed. Rebuild it. "
                f"Keys: {sorted(arrays)}"
            )
        return Cache(
            surface=arrays["min_z_ground"].astype(np.float64),
            min_z_all=arrays["min_z_all"].astype(np.float64),
            max_z_all=arrays["max_z_all"],
            n_all=arrays["n_all"],
            n_ground=arrays["n_ground"],
            origin_x=float(arrays["origin_x"]),
            origin_y=float(arrays["origin_y"]),
            cell_m=float(arrays["cell"]),
            pdal_ground=None,
            shape_name="measure_risers build",
        )
    if "provenance" in arrays:  # compare_ground_filters.py reference
        grid = json.loads(str(arrays["provenance"]))["grid"]
        return Cache(
            surface=arrays["min_z_ground_asprs"].astype(np.float64),
            min_z_all=arrays["min_z_all"].astype(np.float64),
            max_z_all=arrays["max_z_all"],
            n_all=arrays["n_all"],
            n_ground=arrays["n_ground_asprs"],
            origin_x=float(grid["origin_x"]),
            origin_y=float(grid["origin_y"]),
            cell_m=float(grid["cell"]),
            pdal_ground=arrays["n_reference_ground"] > 0,
            shape_name="compare_ground_filters reference",
        )
    raise ValueError(
        f"{path} is neither cache shape: it has neither `min_z_ground` (measure_risers build) "
        f"nor `provenance` (compare_ground_filters reference). Keys: {sorted(arrays)}"
    )


def measured_basis(
    cache: Cache, origin_x: float, origin_y: float, cell_m: float
) -> NDArray[np.bool_]:
    """Cells the old filter's basis calls measured, cropped like everything else.

    `docs/p4-terrace-preregistration.md`'s gate carries this term and `S1` does not, which is the
    whole difference between the two populations. Computed here rather than in a throwaway probe:
    the figure it produces goes into a record, and this repository has paid three times for a
    number whose artefact died with a scratchpad.
    """
    crop = lambda a: _crop(a, origin_x, origin_y, cell_m)  # noqa: E731
    ground = classify_ground(crop(cache.min_z_all), cell_m, GroundParams())
    stats = CellStats(
        min_z_all=crop(cache.min_z_all),
        max_z_all=crop(cache.max_z_all),
        n_all=crop(cache.n_all),
        n_ground_asprs=crop(cache.n_ground),
        min_z_ground_asprs=crop(cache.surface),
        n_outside=0,
    )
    basis: NDArray[np.bool_] = (
        compute_basis(ground, stats, cell_m, BASIS_K_MIN_RETURNS, BASIS_D_MAX_INTERP_M).basis
        == BASIS_MEASURED
    )
    return basis


def retention(keep: NDArray[np.bool_], population: NDArray[np.bool_]) -> float:
    """Share of `population` the ground filter retains, as a percentage.

    Reported, never gated. Zone Z holds the village core and SMRF exists to cut buildings, so a
    lower retention on `S2` than on `S1` is SMRF working -- `S2` is enriched in exactly the sharp
    built edges it is meant to remove. `nan` on an empty population rather than a division: no
    number is the honest report when there is nothing to report on.
    """
    n = int(population.sum())
    if n == 0:
        return float("nan")
    return 100.0 * float((keep & population).sum()) / n


def _crop_indices(origin_x: float, origin_y: float, cell_m: float) -> tuple[int, int]:
    """Top-left cell of the Zone Z crop, clamped to the array."""
    zminx, _, _, zmaxy = ZONE
    return max(int((origin_y - zmaxy) / cell_m), 0), max(int((zminx - origin_x) / cell_m), 0)


def _crop(array: NDArray[Any], origin_x: float, origin_y: float, cell_m: float) -> NDArray[Any]:
    zminx, zminy, zmaxx, zmaxy = ZONE
    col1 = int((zmaxx - origin_x) / cell_m)
    row1 = int((origin_y - zminy) / cell_m)
    row0, col0 = _crop_indices(origin_x, origin_y, cell_m)
    return array[row0:row1, col0:col1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="measure_sharp_step")
    ap.add_argument("--reference", type=Path, required=True, help="cache from measure_risers build")
    args = ap.parse_args(argv)

    cache = read_cache(args.reference)
    cell_m, origin_x, origin_y = cache.cell_m, cache.origin_x, cache.origin_y
    zminx, _, _, zmaxy = ZONE
    surface = _crop(cache.surface, origin_x, origin_y, cell_m)
    if surface.size == 0:
        raise ValueError(f"{args.reference} does not overlap Zone Z {ZONE}; nothing to measure")
    zone_origin_x = max(origin_x, zminx)
    zone_origin_y = min(origin_y, zmaxy)
    print(f"cache: {cache.shape_name}")

    result = cgf.sharp_step_population(surface, cell_m=cell_m)
    s1, s2, residual = result.candidates, result.population, result.residual
    n1, n2 = int(s1.sum()), int(s2.sum())

    print(f"zone {ZONE}, {surface.shape[0]}x{surface.shape[1]} cells at {cell_m:g} m")
    print(f"  observed cells: {int(np.isfinite(surface).sum()):,d}")
    print(f"  S1  step > {cgf.P4B_GATE_THRESHOLD_M:g} m                    {n1:>9,d}")
    print(f"  S2  and residual >= {cgf.SHARP_STEP_RESIDUAL_MIN_M:.2f} m           {n2:>9,d}")
    if n1 == 0:
        print("\nS1 is EMPTY. That is a broken instrument, not a must-not-fire pass.")
        return 2
    print(f"  removed                              {n1 - n2:>9,d}  ({100.0 * (n1 - n2) / n1:.1f}%)")

    values = residual[s1]
    usable = np.isfinite(values)
    if not usable.any():
        print(
            f"\nS1 holds {n1:,d} cells and NOT ONE has a computable residual. Every G3 would "
            f"fail for a reason that is not the measured one. Broken instrument, not a result."
        )
        return 2
    near = int((values[usable] < NEAR_PLANAR_M).sum())
    mid = int(
        ((values[usable] >= NEAR_PLANAR_M) & (values[usable] < cgf.SHARP_STEP_RESIDUAL_MIN_M)).sum()
    )
    # The three rows partition S1's removed cells, and the first two are the only ones drawn
    # from the computable subset -- printing all three under one "of N computable" header would
    # invite a reader to divide the third by a denominator it is not part of.
    print(f"\nwhat was removed, of S1's {n1:,d} cells:")
    print(f"  near-planar   residual <  {NEAR_PLANAR_M:.2f} m   {near:>9,d}")
    band = f"{NEAR_PLANAR_M:.2f} <= r < {cgf.SHARP_STEP_RESIDUAL_MIN_M:.2f}"
    print(f"  intermediate  {band} m   {mid:>9,d}")
    print(f"  no residual   under 4 observed cells   {int((~usable).sum()):>9,d}")
    print(f"  (residual computable for {int(usable.sum()):,d} of {n1:,d})")
    print("\nresidual percentiles over S1:")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q:<3d} {np.nanpercentile(values[usable], q):.3f} m")

    smrf = classify_ground_smrf(
        _crop(cache.min_z_all, origin_x, origin_y, cell_m), cell_m, SMRF_REFERENCE
    )
    pdal = (
        None if cache.pdal_ground is None else _crop(cache.pdal_ground, origin_x, origin_y, cell_m)
    )
    basis = measured_basis(cache, origin_x, origin_y, cell_m)
    print("\nretention (reported, gates nothing -- see the building caveat):")
    populations: tuple[tuple[str, NDArray[np.bool_]], ...] = (
        ("S1                    ", s1),
        ("S2                    ", s2),
        # P4's own gate carries a measured-basis term that S1 does not. Printed beside them so
        # the two are never read as the same population: the difference is what makes this
        # branch's retention figures incomparable with the published band table.
        ("S1 & measured basis   ", s1 & basis),
        ("S2 & measured basis   ", s2 & basis),
    )
    for label, mask in populations:
        theirs = "" if pdal is None else f"   PDAL {retention(pdal, mask):.1f}%"
        print(f"  {label} {int(mask.sum()):>9,d}   SMRF {retention(smrf, mask):5.1f}%{theirs}")

    failures: list[str] = []
    # Not the same thing as a failure, and never merged into one: a predicate this cache cannot
    # evaluate has not been refuted by it.
    incomplete: list[str] = []

    print(
        f"\nG1 must-fire: the five supported real steps, within {G1_TOLERANCE_M:g} m (n=5, small)"
    )
    hits = g1_hits(s2, zone_origin_x, zone_origin_y, cell_m, residual=residual)
    outside = [hit for hit in hits if not hit.inside]
    missed = [hit for hit in hits if hit.inside and not hit.found]
    for hit in hits:
        verdict = "n/a " if not hit.inside else ("PASS" if hit.found else "FAIL")
        if hit.inside:
            where = f"at ({hit.row}, {hit.col})"
        elif hit.centre_inside:
            where = f"neighbourhood truncated at the frame edge, near ({hit.row}, {hit.col})"
        else:
            where = "outside this cache's extent"
        print(f"  {verdict}  {hit.name:<28} {where}")
    # The two are separate states and both are reported. Folding them together would let a real
    # miss inside the frame be announced only as "not evaluable".
    if missed:
        failures.append(f"G1 ({len(missed)} of {len(hits)} in frame and not in S2)")
    if outside:
        print(
            f"  G1 is NOT EVALUABLE as pre-registered: {len(outside)} of {len(hits)} locations "
            f"are not searchable in this cache -- a question it cannot answer. Checked and "
            f"reported above: {len(hits) - len(outside)} of {len(hits)}."
        )
        # G3 is unevaluated at exactly the same locations, so it is named too. Naming only G1
        # is the `elif` defect one predicate over: the summary line is what a reader greps.
        incomplete.append(f"G1 and G3 ({len(outside)} of {len(hits)} not searchable)")

    verdict = g2_verdict(cell_m)
    span = f"{G2_DEGREES[0]:g}-{G2_DEGREES[-1]:g} deg"
    print(f"\nG2 must-not-fire: planar ramps at {span}, both directions")
    print(
        f"  reached S1  {verdict.reached_s1} of {verdict.permitted} geometry permits "
        f"({verdict.of_n} run; an axis-aligned ramp needs 39.8 deg to span the threshold)"
    )
    print(f"  entered S2  {verdict.entered_s2} of {verdict.of_n}   (must be 0)")
    print(f"  {'PASS' if verdict.passed else 'FAIL'}")
    if not verdict.passed:
        failures.append("G2")

    median = float(np.nanmedian(residual[s1]))
    print(f"\nG3 separation: each location's residual above the S1 median ({median:.3f} m)")
    for hit in hits:
        if not hit.inside:
            reason = (
                "neighbourhood truncated at the frame edge"
                if hit.centre_inside
                else "outside this cache's extent"
            )
            print(f"  n/a   {hit.name:<28} {reason}")
            continue
        if not hit.found:
            print(f"  n/a   {hit.name:<28} no S2 cell within {G1_TOLERANCE_M:g} m (see G1)")
            continue
        ok = g3_exceeds_median(hit.residual, residual, s1)
        at = "" if (hit.hit_row, hit.hit_col) == (hit.row, hit.col) else " (nearest S2 cell)"
        print(f"  {'PASS' if ok else 'FAIL'}  {hit.name:<28} residual {hit.residual:.3f} m{at}")
        if not ok:
            failures.append(f"G3 ({hit.name})")

    # Both, never one or the other: the summary line is what gets grepped and quoted into a
    # record, so a run that refuted one predicate and could not evaluate another has to say so.
    if failures:
        print(f"\nFAIL: {', '.join(failures)}")
    if incomplete:
        print(f"\nNOT EVALUABLE: {', '.join(incomplete)}. Nothing there was refuted.")
    if not failures and not incomplete:
        print("\nPASS")
    return 1 if failures or incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The zone-wide instrument for `docs/sharp-step-preregistration.md`.

That document fixes, before this ran once on real data, a population (`S1` the P4-shaped range
term over Zone Z, `S2` those of its cells whose window also departs from a plane) and three
predicates over it. This script evaluates them and prints the reported block beside them.

Exit codes are the verdict: 0 all three predicates pass, 1 one or more fails, **2** `S1` is empty
-- which is a broken instrument, not a clean must-not-fire, and must never read as a pass.

    python scripts/measure_sharp_step.py --reference <zone-z-cache>.npz

The cache is the one `scripts/measure_risers.py build` writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


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
G2_DEGREES = (31.0, 35.0, 40.0, 45.0, 50.0, 60.0)
NEAR_PLANAR_M = 0.10


@dataclass(frozen=True)
class Hit:
    name: str
    row: int
    col: int
    found: bool
    residual: float


@dataclass(frozen=True)
class G2Verdict:
    reached_s1: int
    entered_s2: int
    of_n: int

    @property
    def passed(self) -> bool:
        """Both halves. `reached_s1 == 0` means the ramps never reached the range term, so the
        empty `S2` says nothing -- an instrument selecting nothing would pass on that half alone."""
        return self.reached_s1 >= 8 and self.entered_s2 == 0


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
        row = int((origin_y - y) / cell_m)
        col = int((x - origin_x) / cell_m)
        found = False
        value = float("nan")
        if 0 <= row < population.shape[0] and 0 <= col < population.shape[1]:
            r0, r1 = max(row - reach, 0), min(row + reach + 1, population.shape[0])
            c0, c1 = max(col - reach, 0), min(col + reach + 1, population.shape[1])
            mask = within[
                r0 - (row - reach) : r1 - (row - reach), c0 - (col - reach) : c1 - (col - reach)
            ]
            found = bool((population[r0:r1, c0:c1] & mask).any())
            if residual is not None:
                value = float(residual[row, col])
        out.append(Hit(name=name, row=row, col=col, found=found, residual=value))
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
    reached = entered = total = 0
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
            reached += int(result.candidates.any())
            entered += int(result.population.any())
    return G2Verdict(reached_s1=reached, entered_s2=entered, of_n=total)


def g3_exceeds_median(value: float, residual: NDArray[np.float64], s1: NDArray[np.bool_]) -> bool:
    """Is this location more step-like than the typical cell the range term selects?

    An undefined residual is not a pass. `nan > x` is already False; it is spelled out because a
    silent False here would be indistinguishable from a measured failure.
    """
    if not np.isfinite(value):
        return False
    median = float(np.nanmedian(residual[s1]))
    return bool(value > median)


def _crop(array: NDArray[Any], origin_x: float, origin_y: float, cell_m: float) -> NDArray[Any]:
    zminx, zminy, zmaxx, zmaxy = ZONE
    col0, col1 = int((zminx - origin_x) / cell_m), int((zmaxx - origin_x) / cell_m)
    row0, row1 = int((origin_y - zmaxy) / cell_m), int((origin_y - zminy) / cell_m)
    return array[max(row0, 0) : row1, max(col0, 0) : col1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="measure_sharp_step")
    ap.add_argument("--reference", type=Path, required=True, help="cache from measure_risers build")
    args = ap.parse_args(argv)

    with np.load(args.reference, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files}
    cell_m = float(arrays["cell"])
    origin_x, origin_y = float(arrays["origin_x"]), float(arrays["origin_y"])
    zminx, _, _, zmaxy = ZONE
    surface = _crop(arrays["min_z_ground"].astype(np.float64), origin_x, origin_y, cell_m)
    zone_origin_x = max(origin_x, zminx)
    zone_origin_y = min(origin_y, zmaxy)

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
    near = int((values[usable] < NEAR_PLANAR_M).sum())
    mid = int(
        ((values[usable] >= NEAR_PLANAR_M) & (values[usable] < cgf.SHARP_STEP_RESIDUAL_MIN_M)).sum()
    )
    print(f"\nwhat was removed, of {int(usable.sum()):,d} cells with a computable residual:")
    print(f"  near-planar   residual <  {NEAR_PLANAR_M:.2f} m   {near:>9,d}")
    band = f"{NEAR_PLANAR_M:.2f} <= r < {cgf.SHARP_STEP_RESIDUAL_MIN_M:.2f}"
    print(f"  intermediate  {band} m   {mid:>9,d}")
    print(f"  no residual (window under 4 observed cells)  {int((~usable).sum()):>9,d}")
    print("\nresidual percentiles over S1:")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q:<3d} {np.nanpercentile(values[usable], q):.3f} m")

    failures = []

    print(
        f"\nG1 must-fire: the five supported real steps, within {G1_TOLERANCE_M:g} m (n=5, small)"
    )
    hits = g1_hits(s2, zone_origin_x, zone_origin_y, cell_m, residual=residual)
    for hit in hits:
        print(f"  {'PASS' if hit.found else 'FAIL'}  {hit.name:<28} at ({hit.row}, {hit.col})")
    if not all(hit.found for hit in hits):
        failures.append("G1")

    verdict = g2_verdict(cell_m)
    span = f"{G2_DEGREES[0]:g}-{G2_DEGREES[-1]:g} deg"
    print(f"\nG2 must-not-fire: planar ramps at {span}, both directions")
    print(f"  reached S1  {verdict.reached_s1} of {verdict.of_n}   (must be >= 8)")
    print(f"  entered S2  {verdict.entered_s2} of {verdict.of_n}   (must be 0)")
    print(f"  {'PASS' if verdict.passed else 'FAIL'}")
    if not verdict.passed:
        failures.append("G2")

    median = float(np.nanmedian(residual[s1]))
    print(f"\nG3 separation: each location's residual above the S1 median ({median:.3f} m)")
    for hit in hits:
        ok = g3_exceeds_median(hit.residual, residual, s1)
        print(f"  {'PASS' if ok else 'FAIL'}  {hit.name:<28} residual {hit.residual:.3f} m")
        if not ok:
            failures.append(f"G3 ({hit.name})")

    print(f"\n{'PASS' if not failures else 'FAIL: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

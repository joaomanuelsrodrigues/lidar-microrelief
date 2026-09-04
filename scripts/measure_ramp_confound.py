#!/usr/bin/env python3
"""How much of P4b's population is smooth slope rather than a step, and does the verdict care.

`step_magnitude` is a range in a window, so by construction it cannot tell a terrace riser from
a planar hillside steep enough to span the threshold. That is a declared limitation of
`docs/p4-terrace-preregistration.md`'s population, found by review after the P4 run. This script
is what measures its size, and it lives here because the first version of these numbers lived in
a session scratchpad -- which is the exact loss `compare_ground_filters.py`'s module docstring
exists to end, and it would have been reintroduced for the numbers that answer the review.

Discriminator: fit a least-squares plane to the observed cells of each window and take the RMS
residual. A uniform ramp is planar at any steepness and in any direction; a riser is not, because
the flats above and below sit either side of any plane through them.

    python scripts/measure_ramp_confound.py --reference <cache>.npz
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microrelief.accumulate import CellStats  # noqa: E402
from microrelief.density import BASIS_MEASURED, compute_basis  # noqa: E402
from microrelief.ground import GroundParams, classify_ground  # noqa: E402
from microrelief.smrf import SmrfParams, classify_ground_smrf  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "compare_ground_filters", Path(__file__).resolve().parent / "compare_ground_filters.py"
)
assert _SPEC is not None and _SPEC.loader is not None
cgf = importlib.util.module_from_spec(_SPEC)
sys.modules["compare_ground_filters"] = cgf
_SPEC.loader.exec_module(cgf)

# The bands the record reports. 0.10 m is "indistinguishable from planar at this noise level";
# 0.50 m is where the calibration puts a real wall.
RESIDUAL_BANDS_M = (0.10, 0.20, 0.30, 0.50)


def synthetic_ramp(degrees: float, cell_m: float, diagonal: bool) -> NDArray[np.float64]:
    """A planar surface holding no step, falling either along an axis or across the diagonal."""
    gradient = np.tan(np.radians(degrees))
    rows, cols = np.mgrid[0:40, 0:40]
    along = (rows + cols) / np.sqrt(2) if diagonal else cols
    return (along * cell_m * gradient).astype(np.float64)


def _calibrate(window_cells: int, cell_m: float) -> None:
    """What the statistic says about two surfaces whose answer is known in advance."""
    wall = np.where(np.mgrid[0:40, 0:40][1] >= 20, 2.6, 0.0).astype(np.float64)
    for name, surface in (
        ("uniform 45 deg ramp (no step)", synthetic_ramp(45.0, cell_m, diagonal=False)),
        ("2.6 m wall on flat ground", wall),
    ):
        step, defined = cgf.step_magnitude(surface, window_cells, cgf.STEP_MIN_FINITE)
        selected = defined & (step > cgf.P4B_GATE_THRESHOLD_M)
        cells = np.argwhere(selected)
        if not len(cells):
            print(f"  {name:<32} no cells over the gate threshold")
            continue
        residual = cgf.plane_residual(surface, cells, window_cells, cell_m)
        print(
            f"  {name:<32} n={len(cells):>6,d}  "
            f"median plane residual {np.nanmedian(residual):.3f} m"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="measure_ramp_confound")
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--step-window-cells", type=int, default=cgf.STEP_WINDOW_CELLS)
    args = ap.parse_args(argv)

    with np.load(args.reference, allow_pickle=False) as data:
        arrays: dict[str, NDArray[Any]] = {k: data[k] for k in data.files if k != "provenance"}
        provenance = json.loads(str(data["provenance"]))
    cell_m = float(provenance["grid"]["cell"])
    window = args.step_window_cells

    print("the slope at which a planar ramp, holding no step, enters the gate population:")
    span = (window - 1) * cell_m
    for label, separation in (("axis-aligned", span), ("diagonal", span * np.sqrt(2))):
        print(
            f"  {label:<14} window separation {separation:.3f} m -> "
            f"{np.degrees(np.arctan(cgf.P4B_GATE_THRESHOLD_M / separation)):.1f} deg"
        )
    print("\n  measured, share of a planar ramp's cells over the gate threshold:")
    print(f"    {'slope':>7}{'axis-aligned':>16}{'diagonal':>12}")
    for degrees in (28.0, 30.0, 31.0, 35.0, 40.0):
        shares = []
        for diagonal in (False, True):
            surface = synthetic_ramp(degrees, cell_m, diagonal)
            step, defined = cgf.step_magnitude(surface, window, cgf.STEP_MIN_FINITE)
            shares.append(
                100.0 * float((step[defined] > cgf.P4B_GATE_THRESHOLD_M).sum()) / int(defined.sum())
            )
        print(f"    {degrees:>5.0f}deg{shares[0]:>15.1f}%{shares[1]:>11.1f}%")

    print("\ncalibration on surfaces whose answer is known:")
    _calibrate(window, cell_m)

    surface = arrays["min_z_ground_asprs"].astype(np.float64)
    step, defined = cgf.step_magnitude(surface, window, cgf.STEP_MIN_FINITE)
    ground = classify_ground(arrays["min_z_all"], cell_m, GroundParams(4.0, 0.3, 0.3, 3.5))
    stats = CellStats(
        min_z_all=arrays["min_z_all"],
        max_z_all=arrays["max_z_all"],
        n_all=arrays["n_all"],
        n_ground_asprs=arrays["n_ground_asprs"],
        min_z_ground_asprs=arrays["min_z_ground_asprs"],
        n_outside=0,
    )
    measured = compute_basis(ground, stats, cell_m, 1, 2.0).basis == BASIS_MEASURED
    smrf = classify_ground_smrf(
        arrays["min_z_all"].astype(np.float64),
        cell_m,
        SmrfParams(cell=1.0, slope=0.15, scalar=1.25, threshold=0.5, window=None),
    )
    reference = arrays["n_reference_ground"] > 0

    gate = measured & defined & (step > cgf.P4B_GATE_THRESHOLD_M)
    cells = np.argwhere(gate)
    print(f"\nreal gate population at > {cgf.P4B_GATE_THRESHOLD_M:g} m: {len(cells):,d} cells")
    residual = cgf.plane_residual(surface, cells, window, cell_m)
    usable = np.isfinite(residual)
    print(f"  plane residual computable for {int(usable.sum()):,d}")
    for q in (10, 25, 50, 75, 90):
        print(f"    p{q:<3d} {np.nanpercentile(residual[usable], q):.3f} m")
    for bound in RESIDUAL_BANDS_M:
        share = 100.0 * float((residual[usable] < bound).sum()) / int(usable.sum())
        print(f"  residual < {bound:.2f} m (planar, i.e. ramp not step): {share:5.1f}%")

    rows, cols = cells[:, 0], cells[:, 1]
    keep_smrf, keep_reference = smrf[rows, cols], reference[rows, cols]
    print(f"\nSMRF retention by how planar the window is (bound: P4b >= {cgf.P4B_STEEP_MIN:g}%):")
    header = f"{'subset':<44}{'cells':>9}{'SMRF':>9}{'PDAL':>9}"
    print(header)
    print("-" * len(header))
    bands: list[tuple[str, NDArray[np.bool_]]] = [
        ("all gate cells (the measured P4b)", np.ones(len(residual), dtype=bool))
    ]
    for bound in RESIDUAL_BANDS_M:
        bands.append((f"residual >= {bound:.2f} m", (residual >= bound) & usable))
    bands.append(
        (
            f"residual <  {RESIDUAL_BANDS_M[0]:.2f} m  (the ramp-like cells)",
            (residual < RESIDUAL_BANDS_M[0]) & usable,
        )
    )
    for name, mask in bands:
        n = int(mask.sum())
        if not n:
            print(f"{name:<44}{n:>9,d}{'--':>9}{'--':>9}")
            continue
        print(
            f"{name:<44}{n:>9,d}"
            f"{100.0 * float(keep_smrf[mask].mean()):>8.1f}%"
            f"{100.0 * float(keep_reference[mask].mean()):>8.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

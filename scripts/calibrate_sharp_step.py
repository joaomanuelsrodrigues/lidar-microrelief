#!/usr/bin/env python3
"""Where the sharp-step threshold comes from, derived on geometry rather than on the data.

`docs/sharp-step-preregistration.md` cites this script for three curves, all synthetic, so they
can be produced before the population is computed once and cannot be an outcome:

    step floor    the smallest residual a clean step of the gate height gives, minimised over
                  sub-cell boundary offsets -- the worst case a real sharp riser can produce
    width curve   what a riser of that height reads as it is spread wider, up to the
                  max_riser_width `docs/riser-measurement.md` admits
    noise curve   what a planar ramp holding no step reads under Gaussian noise of a given scale

The threshold has to sit above the noise curve and below the step floor. That the two overlap
for wide risers is the instrument's declared limitation, not a defect of the threshold.

    python scripts/calibrate_sharp_step.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "compare_ground_filters", Path(__file__).resolve().parent / "compare_ground_filters.py"
)
assert _SPEC is not None and _SPEC.loader is not None
cgf = importlib.util.module_from_spec(_SPEC)
sys.modules["compare_ground_filters"] = cgf
_SPEC.loader.exec_module(cgf)

# The orientations and slopes the ramp control sweeps. A plane is planar in every direction, so
# a non-zero reading anywhere here would mean the statistic itself is wrong, not the threshold.
CONTROL_DEGREES = (25.0, 35.0, 45.0, 60.0)
NOISE_SIGMAS = (0.1, 0.2, 0.3)
NOISE_RAMP_DEGREES = 35.0
# 2.6 m, not 2.5: the candidate rule is strict, so a riser whose range is exactly 2.5 m never
# enters the population at any width and its curve would describe nothing.
RISER_M = 2.6


def step_floor(step_m: float, window_cells: int, cell_m: float) -> float:
    """The minimum over sub-cell boundary offsets, because the boundary need not fall on an edge."""
    size = 8 * window_cells
    _, cols = np.mgrid[0:size, 0:size]
    centre = size // 2
    residuals = []
    for shift in BOUNDARY_OFFSETS:
        profile = np.clip(cols - (centre - 0.5 + shift), 0.0, 1.0) * step_m
        residuals.append(
            cgf.plane_residual(
                profile.astype(np.float64),
                np.array([[centre, centre]], dtype=np.int64),
                window_cells,
                cell_m,
            )[0]
        )
    return float(np.nanmin(residuals))


# The sub-cell offsets the step floor is minimised over. A step's edge does not fall on a cell
# edge, and where it lands moves the residual; the floor takes the minimum, so a coarse sample
# over one cell of phase is the conservative side of its own claim.
BOUNDARY_OFFSETS = np.linspace(0.0, 1.0, 11, endpoint=False)
# The width curve needs more than that, and the first version did not have it. Its claim is
# about a POPULATION -- can a riser of this width be in S2 -- so the sweep has to cover every
# position the riser can take inside the window, not one cell of phase, and count only the
# positions where the centre cell is a candidate at all. A phase where the window's range falls
# under the threshold is not an alignment the population contains, and its residual (which can
# be much higher) is not evidence about anything.
WIDTH_PHASES = np.arange(-4.0, 4.0, 0.02)


def width_curve(
    step_m: float,
    window_cells: int,
    cell_m: float,
    step_threshold_m: float = cgf.P4B_GATE_THRESHOLD_M,
) -> list[tuple[float, float, float, float, int]]:
    """What a riser of `step_m`, `width` metres wide, can read where it is in the population.

    Returns `(width_m, centred, minimum, maximum, n_phases)`, swept over every position the
    riser can take relative to the window and **restricted to the positions where the centre
    cell is a candidate** -- range over `step_threshold_m`. Two earlier versions of this were
    narrower and each said something the geometry does not:

    * one sub-cell alignment only, beside a `step_floor` that swept eleven, which made "a 3.0 m
      riser is exactly planar" a property of the centred case rather than of the width;
    * eleven offsets over one cell of phase, which under-reports the maximum and, worse, has no
      reason to be the right window: a riser sitting off-centre is a different geometry, not a
      different phase of the same one.

    Restricting to candidate positions is what makes the band mean something. Off-centre
    positions where the range falls under the threshold read *higher* residuals, and reporting
    those would overstate what the population can hold -- those cells are not in it.
    """
    size = 8 * window_cells
    _, cols = np.mgrid[0:size, 0:size]
    centre = size // 2
    cell = np.array([[centre, centre]], dtype=np.int64)
    out = []
    for width_cells in range(1, window_cells):
        values, centred = [], float("nan")
        for shift in WIDTH_PHASES:
            profile = (
                np.clip((cols - (centre - width_cells / 2 + shift)) / width_cells, 0.0, 1.0)
                * step_m
            ).astype(np.float64)
            step, _ = cgf.step_magnitude(profile, window_cells, cgf.STEP_MIN_FINITE)
            if float(step[centre, centre]) <= step_threshold_m:
                continue
            residual = float(cgf.plane_residual(profile, cell, window_cells, cell_m)[0])
            values.append(residual)
            if abs(shift) < 1e-9:
                centred = residual
        out.append((width_cells * cell_m, centred, min(values), max(values), len(values)))
    return out


def noise_curve(
    degrees: float,
    sigmas: tuple[float, ...],
    window_cells: int,
    cell_m: float,
    draws: int = 500,
) -> list[tuple[float, float]]:
    """Median residual of a planar ramp holding no step, under Gaussian noise of each scale."""
    rng = np.random.default_rng(20260903)
    size = 8 * window_cells
    _, cols = np.mgrid[0:size, 0:size]
    centre = size // 2
    ramp = cols * cell_m * np.tan(np.radians(degrees))
    cell = np.array([[centre, centre]], dtype=np.int64)
    out = []
    for sigma in sigmas:
        values = [
            cgf.plane_residual(
                (ramp + rng.normal(0.0, sigma, ramp.shape)).astype(np.float64),
                cell,
                window_cells,
                cell_m,
            )[0]
            for _ in range(draws)
        ]
        out.append((sigma, float(np.median(values))))
    return out


def ramp_control(
    degrees: tuple[float, ...], window_cells: int, cell_m: float
) -> list[tuple[float, bool, float]]:
    """A planar ramp holds no step, so every row of this must read 0.000 in both orientations."""
    size = 8 * window_cells
    rows, cols = np.mgrid[0:size, 0:size]
    centre = size // 2
    cell = np.array([[centre, centre]], dtype=np.int64)
    out = []
    for angle in degrees:
        gradient = np.tan(np.radians(angle))
        for diagonal in (False, True):
            along = (rows + cols) / np.sqrt(2) if diagonal else cols
            surface = (along * cell_m * gradient).astype(np.float64)
            residual = cgf.plane_residual(surface, cell, window_cells, cell_m)[0]
            out.append((angle, diagonal, float(residual)))
    return out


def main() -> int:
    window_cells = cgf.STEP_WINDOW_CELLS
    cell_m = 0.5
    threshold = cgf.SHARP_STEP_RESIDUAL_MIN_M

    print(f"window {window_cells} cells at {cell_m:g} m = {window_cells * cell_m:g} m across")
    print(f"threshold under derivation: R = {threshold:.2f} m\n")

    floor = step_floor(cgf.P4B_GATE_THRESHOLD_M, window_cells, cell_m)
    print(f"step floor at the gate height ({cgf.P4B_GATE_THRESHOLD_M:g} m): {floor:.4f} m")
    print("  the smallest residual a clean step of that height can give, over sub-cell offsets\n")

    print(f"width curve, riser of {RISER_M:g} m, over every candidate position in the window:")
    print(
        f"    {'width':>7}{'centred':>10}{'min':>9}{'max':>9}{'phases':>9}   at R = {threshold:.2f}"
    )
    for width_m, centred, low, high, n in width_curve(RISER_M, window_cells, cell_m):
        if low >= threshold:
            side = "in at every position"
        elif high < threshold:
            side = "OUT at every position"
        else:
            side = "straddles R"
        print(f"  {width_m:>6.1f} m{centred:>10.3f}{low:>9.3f}{high:>9.3f}{n:>9d}   {side}")
    print("  a riser spread across the window can be a plane; that is the declared limitation\n")

    print(f"noise curve, planar ramp at {NOISE_RAMP_DEGREES:g} deg holding no step:")
    for sigma, residual in noise_curve(NOISE_RAMP_DEGREES, NOISE_SIGMAS, window_cells, cell_m):
        print(f"  sigma {sigma:.2f} m   median residual {residual:.3f} m")
    print("  the threshold must sit above what noise alone can manufacture\n")

    print("ramp control, planar surfaces holding no step (must be 0.000 throughout):")
    for angle, diagonal, residual in ramp_control(CONTROL_DEGREES, window_cells, cell_m):
        orientation = "diagonal" if diagonal else "axis    "
        print(f"  {angle:>4.0f} deg  {orientation}  {residual:.3f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

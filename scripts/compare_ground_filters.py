#!/usr/bin/env python3
"""Compare this filter's per-cell ground decision with a reference filter's, on one grid.

This is the acceptance check the in-repo SMRF implementation will be measured against, and the
instrument that re-derives the table in `docs/ground-filter-diagnosis.md`. It exists because that
table had no artefact behind it: the script that produced it was never in this tree and the PDAL
environment and classified tiles it ran against died with a session scratchpad.

Two steps, because they cost three orders of magnitude apart:

    reference   reads the delivery tiles and their SMRF-classified counterparts once, and reduces
                them to per-cell arrays on the AOI grid, with provenance. Minutes.
    compare     runs this repository's own `classify_ground` / `compute_basis` over those arrays
                and prints the population table. Seconds -- so it can be the inner loop of a
                calibration arc instead of a thing run once.

The delivery's ASPRS classification decides no cell in either filter. It names the population
being audited, which is the role it already has in `agreement()`; using it to decide cells would
make the comparison a tautology.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import laspy
import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import binary_erosion, convolve, maximum_filter, minimum_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microrelief.accumulate import (  # noqa: E402
    Accumulator,
    CellStats,
    _grouped_extrema,
)
from microrelief.cli import aoi_bounds  # noqa: E402
from microrelief.density import BASIS_INTERPOLATED, BASIS_MEASURED, compute_basis  # noqa: E402
from microrelief.grid import Grid, grid_for_bounds  # noqa: E402
from microrelief.ground import GroundParams, classify_ground  # noqa: E402
from microrelief.read import read_laz  # noqa: E402
from microrelief.smrf import SmrfParams, classify_ground_smrf  # noqa: E402

# PDAL's `filters.smrf` ignores this class in the pipeline recorded in `docs/live-smoke.md`, and
# passes those points through untouched. They are therefore not judged, and counting them as
# judged ground would credit the reference filter with a decision it never made.
IGNORED_CLASS = 7


class ReferenceBuildError(RuntimeError):
    """The two files cannot be compared, so nothing is computed from them."""


def judged_mask(
    classification: NDArray[np.uint8],
    return_number: NDArray[np.int32],
    number_of_returns: NDArray[np.int32],
    ignored_class: int = IGNORED_CLASS,
) -> NDArray[np.bool_]:
    """Which points the reference filter actually judged.

    PDAL's `returns` default is `[last, only]` and `only_ground` is false, so judged points come
    back as class 1 or 2 while unjudged points keep their delivery class. That makes a
    passed-through class-2 point indistinguishable from a judged ground point *by class alone* --
    which is why the mask is derived from return numbers here and verified against the recorded
    reclassification counts rather than assumed.
    """
    last_or_only = (number_of_returns == 1) | (return_number == number_of_returns)
    judged: NDArray[np.bool_] = last_or_only & (classification != ignored_class)
    return judged


def check_correspondence(
    ax: NDArray[Any],
    ay: NDArray[Any],
    az: NDArray[Any],
    bx: NDArray[Any],
    by: NDArray[Any],
    bz: NDArray[Any],
) -> None:
    """Refuse to zip two point files by index unless they really do correspond.

    PDAL preserves point order through this pipeline, but that is a property of the pipeline and
    not a promise of the format, and every per-point control below depends on it. Measured rather
    than assumed: a silent reorder would keep every count plausible and make every one of them
    about the wrong points.
    """
    if not (len(ax) == len(bx) and len(ay) == len(by) and len(az) == len(bz)):
        raise ReferenceBuildError(
            f"point count differs between the delivery tile and the reference output "
            f"({len(ax)} vs {len(bx)}); they cannot be zipped by index"
        )
    if not (np.array_equal(ax, bx) and np.array_equal(ay, by) and np.array_equal(az, bz)):
        raise ReferenceBuildError(
            "coordinate arrays differ between the delivery tile and the reference output; "
            "the reference filter reordered or moved points, so index correspondence is invalid"
        )


def interior(mask: NDArray[np.bool_], margin: int) -> NDArray[np.bool_]:
    """Cells at least `margin` cells inside the edge of `mask`.

    This is the "roof interior" population of `docs/ground-filter-diagnosis.md` row C: the cells
    of a building where no ground return shares the cell *and* which are not on the building's
    rim, where a 0.5 m cell legitimately holds both roof and ground returns.

    The raster border counts as an edge (`border_value=0`): a block running off the grid is not
    inside anything on that side, and treating the border as interior would inflate the population
    with cells whose neighbourhood was never observed.
    """
    if margin < 1:
        raise ValueError("margin must be at least 1 cell")
    size = 2 * margin + 1
    eroded: NDArray[np.bool_] = binary_erosion(
        mask, structure=np.ones((size, size), dtype=bool), border_value=0
    )
    return eroded


# The terrace population of `docs/p4-terrace-preregistration.md`. 7 cells at 0.5 m is 3.5 m
# across -- the horizontal extent the record's phrase "a real vertical step in 3.5 m" names, with
# the alternative reading (3.5 m as the height cap) declined there before any number was seen.
STEP_WINDOW_CELLS = 7
STEP_MIN_FINITE = 2
# Swept as the record swept it. Only the last one gates; the other two are reported.
STEP_THRESHOLDS_M = (1.5, 2.0, 2.5)
P4B_GATE_THRESHOLD_M = 2.5
# Reported beside P4b, so a reader can see whether the result is carried by sparse
# neighbourhoods, where two distant points on a slope give a large range with no step present.
STEP_DENSE_MIN_FINITE = 10


def step_magnitude(
    surface: NDArray[np.float64],
    window_cells: int = STEP_WINDOW_CELLS,
    min_finite: int = STEP_MIN_FINITE,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """The vertical range of `surface` in a square window, and where that range is defined.

    `surface` is the delivery's own class-2 minimum, never our DTM: `max_elevation_m` is the
    parameter that decides whether a riser survives our filter, so a surface our filter shaped
    would select the population by the very thing being audited. The same reason
    `scripts/measure_risers.py` gives for refusing it.

    Undefined, rather than zero, in two cases the caller must not conflate with a flat cell:

    * fewer than `min_finite` observed cells in the window -- a range needs two points, and one
      point is not a small range;
    * within `window_cells // 2` of the grid border, where the neighbourhood was never observed.
      A truncated window reports the range of whichever part happened to be inside, which is not
      the cell's step. This is `interior()`'s `border_value=0` reasoning on a numeric surface.
    """
    if window_cells < 3 or window_cells % 2 == 0:
        raise ValueError("window_cells must be an odd number of cells >= 3, so it has a centre")
    if min_finite < 2:
        raise ValueError("a range needs two points; min_finite below 2 would define one")

    finite = np.isfinite(surface)
    # Seeded at -inf/+inf rather than left as NaN. An accumulated max or min over NaN propagates
    # NaN, which would erase every window holding a single unobserved cell -- most of them.
    highs = maximum_filter(
        np.where(finite, surface, -np.inf), size=window_cells, mode="constant", cval=-np.inf
    )
    lows = minimum_filter(
        np.where(finite, surface, np.inf), size=window_cells, mode="constant", cval=np.inf
    )
    counts = convolve(
        finite.astype(np.int32),
        np.ones((window_cells, window_cells), dtype=np.int32),
        mode="constant",
        cval=0,
    )

    margin = window_cells // 2
    observed = np.zeros(surface.shape, dtype=bool)
    observed[margin : surface.shape[0] - margin, margin : surface.shape[1] - margin] = True

    defined: NDArray[np.bool_] = (counts >= min_finite) & observed
    step: NDArray[np.float64] = np.where(defined, highs - lows, np.nan)
    return step, defined


@dataclass(frozen=True)
class Reference:
    """Everything the comparison needs that costs a LAZ read."""

    min_z_all: NDArray[np.float32]
    max_z_all: NDArray[np.float32]
    n_all: NDArray[np.int32]
    n_ground_asprs: NDArray[np.int32]
    n_class5: NDArray[np.int32]
    n_class6: NDArray[np.int32]
    n_reference_ground: NDArray[np.int32]
    min_z_ground_asprs: NDArray[np.float32]
    # The minimum over the returns the reference filter actually reads (last/only, class 7 aside),
    # so that a difference in the *input* to the two filters is never read as a difference between
    # the filters. The pipeline's own surface is over all returns.
    min_z_judged: NDArray[np.float32]
    # The lowest point the reference filter called ground in each cell. Its distance above
    # `min_z_all` measures the one design difference of a cell-level membership test: the
    # reference calls a cell ground if *any* judged point passes, this package tests the lowest.
    min_z_reference_ground: NDArray[np.float32]
    grid: Grid
    cell: float
    controls: dict[str, int]
    provenance: dict[str, Any]


def _flat_counts(
    grid: Grid, x: NDArray[np.float64], y: NDArray[np.float64], keep: NDArray[np.bool_]
) -> NDArray[np.int64]:
    row, col, inside = grid.cell_indices(x, y)
    take = inside & keep
    flat = row[take] * grid.n_cols + col[take]
    counts: NDArray[np.int64] = np.bincount(flat, minlength=grid.n_cells)
    return counts


def _flat_min(
    grid: Grid,
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    z: NDArray[np.float64],
    keep: NDArray[np.bool_],
    into: NDArray[np.float64],
) -> None:
    """Fold the minimum of a subset of points into `into`, in place.

    Reuses the accumulator's own grouped reduction rather than restating it: this is the same
    sort-once, `reduceat` pattern, and two copies of it could drift apart while both look right.
    """
    row, col, inside = grid.cell_indices(x, y)
    take = inside & keep
    if not take.any():
        return
    flat = row[take] * grid.n_cols + col[take]
    cells, mins, _maxs, _counts = _grouped_extrema(flat, z[take])
    into[cells] = np.minimum(into[cells], mins)


def build_reference(
    tiles: list[Path], smrf_dir: Path, grid: Grid, cell: float, suffix: str
) -> Reference:
    """Read each delivery tile and its reference counterpart once, and reduce to per-cell arrays.

    The pipeline's own view of the delivery (`read_laz` + `Accumulator`) is used for the arrays the
    pipeline itself consumes, so `compare` runs the real `classify_ground` over the real inputs
    rather than over a parallel reconstruction of them.
    """
    accumulator = Accumulator(grid)
    n_class5 = np.zeros(grid.n_cells, dtype=np.int64)
    n_class6 = np.zeros(grid.n_cells, dtype=np.int64)
    n_reference_ground = np.zeros(grid.n_cells, dtype=np.int64)
    min_z_judged = np.full(grid.n_cells, np.inf, dtype=np.float64)
    min_z_reference_ground = np.full(grid.n_cells, np.inf, dtype=np.float64)
    controls = {"into_ground": 0, "out_of_ground": 0, "passed_through_class2": 0, "judged": 0}
    sources: list[dict[str, Any]] = []

    for tile in tiles:
        reference_path = smrf_dir / f"{tile.stem.split('-07-')[0]}{suffix}"
        if not reference_path.exists():
            raise ReferenceBuildError(f"no reference output for {tile.name} at {reference_path}")

        # The pipeline's own reader, for the arrays the pipeline consumes.
        batch = read_laz(tile, expect_epsg=grid.crs_epsg, footprint=None)
        accumulator.add(batch)

        delivery = laspy.read(str(tile))
        reference = laspy.read(str(reference_path))
        check_correspondence(
            np.asarray(delivery.X),
            np.asarray(delivery.Y),
            np.asarray(delivery.Z),
            np.asarray(reference.X),
            np.asarray(reference.Y),
            np.asarray(reference.Z),
        )

        delivery_class = np.asarray(delivery.classification, dtype=np.uint8)
        reference_class = np.asarray(reference.classification, dtype=np.uint8)
        judged = judged_mask(
            delivery_class,
            np.asarray(reference.return_number, dtype=np.int32),
            np.asarray(reference.number_of_returns, dtype=np.int32),
        )

        into = (reference_class == 2) & (delivery_class != 2) & judged
        out_of = (reference_class != 2) & (delivery_class == 2) & judged
        controls["into_ground"] += int(into.sum())
        controls["out_of_ground"] += int(out_of.sum())
        controls["passed_through_class2"] += int(((~judged) & (delivery_class == 2)).sum())
        controls["judged"] += int(judged.sum())

        x = np.asarray(delivery.x, dtype=np.float64)
        y = np.asarray(delivery.y, dtype=np.float64)
        n_class5 += _flat_counts(grid, x, y, delivery_class == 5)
        n_class6 += _flat_counts(grid, x, y, delivery_class == 6)
        n_reference_ground += _flat_counts(grid, x, y, judged & (reference_class == 2))

        z = np.asarray(delivery.z, dtype=np.float64)
        _flat_min(grid, x, y, z, judged, min_z_judged)
        _flat_min(grid, x, y, z, judged & (reference_class == 2), min_z_reference_ground)

        sources.append(
            {
                "tile": tile.name,
                "tile_sha256": batch.source_sha256,
                "reference": reference_path.name,
                "points": int(len(delivery.points)),
                # The reference filter ran once per tile, on its own bounds, while this package
                # runs on one AOI grid. Cells near these lines are where that difference lands,
                # so the comparison can report them apart instead of averaging over them.
                "bounds": [float(v) for v in batch.bounds],
            }
        )

    stats = accumulator.finish()
    shape = grid.shape

    def as_surface(values: NDArray[np.float64]) -> NDArray[np.float32]:
        """`inf` is the seed of a minimum that never ran, and NaN is how this package says so."""
        out = values.astype(np.float32)
        out[np.isinf(values)] = np.nan
        return out.reshape(shape)

    return Reference(
        min_z_all=stats.min_z_all,
        max_z_all=stats.max_z_all,
        n_all=stats.n_all,
        n_ground_asprs=stats.n_ground_asprs,
        min_z_ground_asprs=stats.min_z_ground_asprs,
        n_class5=n_class5.reshape(shape).astype(np.int32),
        n_class6=n_class6.reshape(shape).astype(np.int32),
        n_reference_ground=n_reference_ground.reshape(shape).astype(np.int32),
        min_z_judged=as_surface(min_z_judged),
        min_z_reference_ground=as_surface(min_z_reference_ground),
        grid=grid,
        cell=cell,
        controls=controls,
        provenance={"sources": sources},
    )


def _cmd_reference(args: argparse.Namespace) -> int:
    minx, miny, maxx, maxy, epsg = aoi_bounds(args.aoi, args.crs)
    grid = grid_for_bounds(minx, miny, maxx, maxy, args.cell, epsg)
    tiles = sorted(args.tiles.glob("*.laz"))
    if not tiles:
        print(f"no .laz files in {args.tiles}", file=sys.stderr)
        return 2

    reference = build_reference(tiles, args.smrf, grid, args.cell, args.suffix)

    pipeline_sha = ""
    if args.pipeline is not None:
        if not args.pipeline.exists():
            # Silently recording an empty hash would attribute the acceptance run to an
            # unidentified reference pipeline, and say nothing on the way past.
            print(f"--pipeline {args.pipeline} does not exist", file=sys.stderr)
            return 2
        pipeline_sha = hashlib.sha256(args.pipeline.read_bytes()).hexdigest()[:16]

    provenance = {
        "grid": {
            "origin_x": grid.origin_x,
            "origin_y": grid.origin_y,
            "cell": grid.cell,
            "n_rows": grid.n_rows,
            "n_cols": grid.n_cols,
            "crs_epsg": grid.crs_epsg,
        },
        "reference_filter": args.reference_name,
        "reference_pipeline_sha256_16": pipeline_sha,
        "controls": reference.controls,
        **reference.provenance,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        min_z_all=reference.min_z_all,
        max_z_all=reference.max_z_all,
        n_all=reference.n_all,
        n_ground_asprs=reference.n_ground_asprs,
        min_z_ground_asprs=reference.min_z_ground_asprs,
        n_class5=reference.n_class5,
        n_class6=reference.n_class6,
        n_reference_ground=reference.n_reference_ground,
        min_z_judged=reference.min_z_judged,
        min_z_reference_ground=reference.min_z_reference_ground,
        provenance=np.array(json.dumps(provenance)),
    )
    print(json.dumps(provenance, indent=2))
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


def _load_reference(path: Path) -> tuple[dict[str, NDArray[Any]], dict[str, Any]]:
    with np.load(path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files if k != "provenance"}
        provenance = json.loads(str(data["provenance"]))
    return arrays, provenance


def _share(mask: NDArray[np.bool_], population: NDArray[np.bool_]) -> float:
    n = int(population.sum())
    return 100.0 * float((mask & population).sum()) / n if n else float("nan")


def populations_of(
    arrays: dict[str, NDArray[Any]], roof_margin: int
) -> dict[str, NDArray[np.bool_]]:
    """The audited populations, defined once for every command that reports over them.

    Rows A and B, the canopy control and the plain-ground control all reproduce the recorded cell
    counts EXACTLY. Row C does not: "B, >= 2 cells inside the edge" names an erosion the record
    never defines operationally, and none of eight readings of it reaches the recorded 3,524,239
    (closest 3,487,782). Row C' is our reading, reported as ours and not as a replication -- see
    `docs/reference-instrument-result.md`.

    The delivery's ASPRS classification decides no cell in any filter here; it names who is being
    audited, which is the role it already has in `agreement()`.
    """
    has_c2 = arrays["n_ground_asprs"] > 0
    has_c5 = arrays["n_class5"] > 0
    has_c6 = arrays["n_class6"] > 0
    building = has_c6 & ~has_c2
    return {
        "A: any class-6 return": has_c6,
        "B: class-6, no class-2": building,
        "C': B eroded by roof-margin (OUR reading, not the recorded size)": interior(
            building, margin=roof_margin
        ),
        "control: canopy (class 5, no class 2, no class 6)": has_c5 & ~has_c2 & ~has_c6,
        "control: plain ground (class 2, no class 5, no class 6)": has_c2 & ~has_c5 & ~has_c6,
    }


@dataclass(frozen=True)
class Confusion:
    """Cell-by-cell agreement between our filter and the reference, over one population."""

    n: int
    both_ground: int
    ours_only: int
    reference_only: int
    neither: int

    @property
    def agreement(self) -> float:
        return 100.0 * (self.both_ground + self.neither) / self.n if self.n else float("nan")

    @property
    def kappa(self) -> float:
        """Cohen's kappa, because raw agreement is passed by the degenerate answer.

        On this AOI most cells are ground, so a filter that called everything ground would post a
        high agreement while agreeing about nothing. Kappa divides out that prevalence and scores
        it at 0 -- which is the whole reason a second number is here.
        """
        if not self.n:
            return float("nan")
        ours = self.both_ground + self.ours_only
        theirs = self.both_ground + self.reference_only
        expected = (ours * theirs + (self.n - ours) * (self.n - theirs)) / (self.n * self.n)
        observed = (self.both_ground + self.neither) / self.n
        return (observed - expected) / (1.0 - expected) if expected < 1.0 else float("nan")


def confusion(
    ours: NDArray[np.bool_], reference: NDArray[np.bool_], population: NDArray[np.bool_]
) -> Confusion:
    a, b = ours[population], reference[population]
    return Confusion(
        n=int(population.sum()),
        both_ground=int((a & b).sum()),
        ours_only=int((a & ~b).sum()),
        reference_only=int((~a & b).sum()),
        neither=int((~a & ~b).sum()),
    )


def seam_cells(provenance: dict[str, Any], grid: Grid, margin_m: float) -> NDArray[np.bool_]:
    """Cells within `margin_m` of the edge of any delivery tile.

    Not a defect of either filter and not corrected for: the reference ran once per tile on its
    own bounds, this package runs on one AOI grid, and those lines are where that difference
    lands. Reported apart so it cannot be mistaken for algorithmic disagreement.
    """
    xs = grid.origin_x + (np.arange(grid.n_cols) + 0.5) * grid.cell
    ys = grid.origin_y - (np.arange(grid.n_rows) + 0.5) * grid.cell
    seam = np.zeros(grid.shape, dtype=bool)
    for source in provenance.get("sources", []):
        bounds = source.get("bounds")
        if not bounds:
            continue
        minx, miny, maxx, maxy = bounds
        # The frame of one tile: inside its box grown by the margin, and not inside its box
        # shrunk by it. The first version of this unioned a row band with a column band, which
        # marks a cell deep inside one tile because some OTHER tile's edge shares its row --
        # and the single-tile test could not tell the two definitions apart.
        grown = ((ys >= miny - margin_m) & (ys <= maxy + margin_m))[:, None] & (
            (xs >= minx - margin_m) & (xs <= maxx + margin_m)
        )[None, :]
        shrunk = ((ys > miny + margin_m) & (ys < maxy - margin_m))[:, None] & (
            (xs > minx + margin_m) & (xs < maxx - margin_m)
        )[None, :]
        seam |= grown & ~shrunk
    return seam


def _cmd_compare(args: argparse.Namespace) -> int:
    arrays, provenance = _load_reference(args.reference)
    if "min_z_ground_asprs" not in arrays:
        print(
            f"{args.reference} was built before this array was cached; rebuild it with the "
            "`reference` command rather than running over a substituted surface",
            file=sys.stderr,
        )
        return 2
    grid_info = provenance["grid"]
    cell = float(grid_info["cell"])

    params = GroundParams(
        args.max_window_m, args.slope_threshold, args.elevation_threshold_m, args.max_elevation_m
    )
    is_ground = classify_ground(arrays["min_z_all"], cell, params)

    stats = CellStats(
        min_z_all=arrays["min_z_all"],
        max_z_all=arrays["max_z_all"],
        n_all=arrays["n_all"],
        n_ground_asprs=arrays["n_ground_asprs"],
        # The real array, not `min_z_all` standing in for it: `compute_basis` reads only
        # `n_all` today, so a substitution is invisible until the first honesty rule that
        # reads the ground surface, which would then be computed from the wrong one.
        min_z_ground_asprs=arrays["min_z_ground_asprs"],
        n_outside=0,
    )
    basis = compute_basis(is_ground, stats, cell, args.k_min_returns, args.d_max_interp_m)

    reference_ground = arrays["n_reference_ground"] > 0
    populations = populations_of(arrays, args.roof_margin)

    measured = basis.basis == BASIS_MEASURED
    interpolated = basis.basis == BASIS_INTERPOLATED

    print(f"reference filter: {provenance.get('reference_filter', '?')}")
    print(f"controls: {json.dumps(provenance.get('controls', {}))}")
    print()
    header = (
        f"{'population':<62}{'cells':>12}{'ours meas.':>12}{'ref ground':>12}{'ours interp':>12}"
    )
    print(header)
    print("-" * len(header))
    for name, population in populations.items():
        n = int(population.sum())
        print(
            f"{name:<62}{n:>12,d}"
            f"{_share(measured, population):>11.1f}%"
            f"{_share(reference_ground, population):>11.1f}%"
            f"{_share(interpolated, population):>11.1f}%"
        )
    print()
    roof = populations["C': B eroded by roof-margin (OUR reading, not the recorded size)"]
    print(f"falsely-measured roof cells, ours:      {int((measured & roof).sum()):,d}")
    print(f"falsely-measured roof cells, reference: {int((reference_ground & roof).sum()):,d}")
    return 0


# The acceptance predicates of `docs/smrf-build-preregistration.md`, fixed before the first run.
# They live here as well as there because a predicate quoted in prose and applied in code is two
# sets of literals that can drift; `tests/test_compare_ground_filters.py` fails if they disagree.
P1_PLAIN_GROUND_MIN = 97.0
P2_ROOF_MAX = 30.0
P3_AGREEMENT_MIN = 90.0
P3_KAPPA_MIN = 0.60

# P4, deferred out of that document because Valongo has terraces only incidentally, and fixed in
# `docs/p4-terrace-preregistration.md` before the terrace population was computed once.
P4A_TERRACE_MIN = 85.0
P4B_STEEP_MIN = 80.0


def _verdict(name: str, value: float, bound: float, direction: str) -> tuple[str, bool]:
    ok = value >= bound if direction == ">=" else value <= bound
    return f"{name}: {value:.3f} {direction} {bound} -> {'PASS' if ok else 'FAIL'}", ok


def _cmd_smrf(args: argparse.Namespace) -> int:
    """Run this repository's SMRF over the cached arrays and compare it, cell by cell.

    Seconds, not minutes: everything a LAZ read would provide is already in the reference file.
    """
    arrays, provenance = _load_reference(args.reference)
    grid_info = provenance["grid"]
    grid = Grid(
        origin_x=float(grid_info["origin_x"]),
        origin_y=float(grid_info["origin_y"]),
        cell=float(grid_info["cell"]),
        n_cols=int(grid_info["n_cols"]),
        n_rows=int(grid_info["n_rows"]),
        crs_epsg=int(grid_info["crs_epsg"]),
    )
    params = SmrfParams(
        cell=args.smrf_cell,
        slope=args.smrf_slope,
        scalar=args.smrf_scalar,
        threshold=args.smrf_threshold,
        window=args.smrf_window,
    )

    surface_name = args.surface
    if surface_name not in arrays:
        print(f"the reference file has no array named {surface_name}", file=sys.stderr)
        return 2
    surface = arrays[surface_name]

    is_ground = classify_ground_smrf(surface.astype(np.float64), grid.cell, params)
    reference_ground = arrays["n_reference_ground"] > 0
    measured = arrays["n_all"] > 0
    populations = populations_of(arrays, args.roof_margin)

    print(f"reference filter:  {provenance.get('reference_filter', '?')}")
    print(f"our surface:       {surface_name}")
    print(f"our SMRF params:   {params}  (window_m = {params.window_m})")
    print(f"controls:          {json.dumps(provenance.get('controls', {}))}")
    print()

    header = f"{'population':<62}{'cells':>12}{'ours ground':>13}{'ref ground':>12}"
    print(header)
    print("-" * len(header))
    shares: dict[str, float] = {}
    for name, population in populations.items():
        shares[name] = _share(is_ground, population)
        print(
            f"{name:<62}{int(population.sum()):>12,d}"
            f"{shares[name]:>12.1f}%{_share(reference_ground, population):>11.1f}%"
        )

    print()
    overall = confusion(is_ground, reference_ground, measured)
    print(f"cells compared (measured):       {overall.n:>12,d}")
    print(f"  both ground:                   {overall.both_ground:>12,d}")
    print(f"  ours only:                     {overall.ours_only:>12,d}")
    print(f"  reference only:                {overall.reference_only:>12,d}")
    print(f"  neither:                       {overall.neither:>12,d}")
    print(f"  agreement:                     {overall.agreement:>12.2f}%")
    print(f"  Cohen's kappa:                 {overall.kappa:>12.3f}")

    seam = seam_cells(provenance, grid, args.seam_margin_m)
    away = confusion(is_ground, reference_ground, measured & ~seam)
    print()
    print(f"excluding {args.seam_margin_m:g} m either side of a tile edge (reported, not a gate):")
    print(f"  cells compared:                {away.n:>12,d}")
    print(f"  agreement:                     {away.agreement:>12.2f}%")
    print(f"  Cohen's kappa:                 {away.kappa:>12.3f}")

    # The load-bearing assumption of a cell-level membership test, measured rather than argued:
    # the reference calls a cell ground if ANY judged point passes, this package tests the lowest
    # one. Where those are the same point the two tests ask the same question.
    lifted = arrays["min_z_reference_ground"] - arrays["min_z_all"]
    has_ref = reference_ground & np.isfinite(lifted)
    print()
    print("the reference's ground verdict came from a point above the cell minimum:")
    for bound in (0.05, 0.25, 1.00):
        share = _share(lifted > bound, has_ref)
        print(f"  more than {bound:>4.2f} m above:       {share:>12.2f}%")

    plain = shares["control: plain ground (class 2, no class 5, no class 6)"]
    roof = shares["B: class-6, no class-2"]
    print()
    print("pre-registered predicates (docs/smrf-build-preregistration.md):")
    lines = [
        _verdict("P1 plain ground called ground", plain, P1_PLAIN_GROUND_MIN, ">="),
        _verdict("P2 row B called ground", roof, P2_ROOF_MAX, "<="),
        _verdict("P3 agreement", overall.agreement, P3_AGREEMENT_MIN, ">="),
        _verdict("P3 kappa", overall.kappa, P3_KAPPA_MIN, ">="),
    ]
    for text, _ok in lines:
        print(f"  {text}")
    passed = all(ok for _text, ok in lines)
    print(f"\nVERDICT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def _cmd_terraces(args: argparse.Namespace) -> int:
    """P4: what the in-repo SMRF costs on the terraces, over the population fixed beforehand.

    The symmetric risk to the build's P1-P3. Those said SMRF stops publishing roofs as terrain;
    this asks what it removes from the thing the tool exists to publish. Population, surface and
    step operation are `docs/p4-terrace-preregistration.md`, committed before this ran.
    """
    # Usage errors return 2. `step_magnitude` raises ValueError for both of these, and an
    # uncaught traceback exits 1 -- the code a measured FAIL verdict uses, so a typo in a flag
    # would be indistinguishable from a filter that failed the predicate.
    if args.step_window_cells < 3 or args.step_window_cells % 2 == 0:
        print("--step-window-cells must be an odd number of cells >= 3", file=sys.stderr)
        return 2
    if args.step_min_finite < 2:
        print("--step-min-finite must be at least 2: a range needs two points", file=sys.stderr)
        return 2

    arrays, provenance = _load_reference(args.reference)
    # Derived from what this command actually reads, `args.surface` included, rather than listed
    # by hand: two of these entered the cache later than the others, so a cache built in between
    # passes a hand-written guard and then dies mid-table on a KeyError, at exit 1.
    for needed in sorted(
        {
            "min_z_all",
            "max_z_all",
            "n_all",
            "n_ground_asprs",
            "min_z_ground_asprs",
            "n_reference_ground",
            "min_z_reference_ground",
            args.surface,
        }
    ):
        if needed not in arrays:
            print(
                f"{args.reference} has no array named {needed}; rebuild it with the `reference` "
                "command rather than running over a substituted surface",
                file=sys.stderr,
            )
            return 2
    grid_info = provenance["grid"]
    cell = float(grid_info["cell"])

    # The current filter, at its shipped defaults -- the real one, not a reconstruction.
    ground_params = GroundParams(
        args.max_window_m, args.slope_threshold, args.elevation_threshold_m, args.max_elevation_m
    )
    ours_ground = classify_ground(arrays["min_z_all"], cell, ground_params)
    stats = CellStats(
        min_z_all=arrays["min_z_all"],
        max_z_all=arrays["max_z_all"],
        n_all=arrays["n_all"],
        n_ground_asprs=arrays["n_ground_asprs"],
        min_z_ground_asprs=arrays["min_z_ground_asprs"],
        n_outside=0,
    )
    basis = compute_basis(ours_ground, stats, cell, args.k_min_returns, args.d_max_interp_m)
    measured_ground = basis.basis == BASIS_MEASURED

    smrf_params = SmrfParams(
        cell=args.smrf_cell,
        slope=args.smrf_slope,
        scalar=args.smrf_scalar,
        threshold=args.smrf_threshold,
        window=args.smrf_window,
    )
    smrf_ground = classify_ground_smrf(arrays[args.surface].astype(np.float64), cell, smrf_params)
    reference_ground = arrays["n_reference_ground"] > 0

    step, defined = step_magnitude(
        arrays["min_z_ground_asprs"].astype(np.float64),
        args.step_window_cells,
        args.step_min_finite,
    )

    print(f"reference filter:  {provenance.get('reference_filter', '?')}")
    print(f"our surface:       {args.surface}")
    print(
        f"step surface:      min_z_ground_asprs (delivery class 2), "
        f"{args.step_window_cells}x{args.step_window_cells} window = "
        f"{args.step_window_cells * cell:g} m, >= {args.step_min_finite} finite"
    )
    print(f"our SMRF params:   {smrf_params}  (window_m = {smrf_params.window_m})")
    print(f"our filter params: {ground_params}")
    print(f"controls:          {json.dumps(provenance.get('controls', {}))}")
    print()

    header = f"{'population':<50}{'cells':>12}{'SMRF ground':>14}{'PDAL ground':>14}"
    print(header)
    print("-" * len(header))
    print(
        f"{'P4a: our measured ground':<50}{int(measured_ground.sum()):>12,d}"
        f"{_share(smrf_ground, measured_ground):>13.1f}%"
        f"{_share(reference_ground, measured_ground):>13.1f}%"
    )
    # The gate population is computed here, from the gate constant. Reading it out of the
    # sweep below would make editing that reported-only tuple raise KeyError on the gate path.
    gate_population = measured_ground & defined & (step > P4B_GATE_THRESHOLD_M)
    for bound in STEP_THRESHOLDS_M:
        population = measured_ground & defined & (step > bound)
        gate = "  (GATE)" if bound == P4B_GATE_THRESHOLD_M else ""
        label = f"P4b: ... on a step > {bound:g} m{gate}"
        print(
            f"{label:<50}{int(population.sum()):>12,d}"
            f"{_share(smrf_ground, population):>13.1f}%"
            f"{_share(reference_ground, population):>13.1f}%"
        )

    if not gate_population.any():
        # An empty population makes P4b's share `nan`, not 100%. Either way it is not a pass:
        # it is an instrument that selected nothing, and the pre-registration says so.
        print(
            f"\nP4b's population is EMPTY at > {P4B_GATE_THRESHOLD_M:g} m. That is a broken "
            "instrument, not a passing filter; no verdict is computed.",
            file=sys.stderr,
        )
        return 2

    print()
    print("reported, with nothing riding on it:")
    # Never looser than the gate: with `--step-min-finite` above the constant this would be
    # printed as the control on sparse neighbourhoods while admitting more of them than the
    # population it is controlling.
    dense_min_finite = max(STEP_DENSE_MIN_FINITE, args.step_min_finite)
    dense_step, dense_defined = step_magnitude(
        arrays["min_z_ground_asprs"].astype(np.float64),
        args.step_window_cells,
        dense_min_finite,
    )
    dense = measured_ground & dense_defined & (dense_step > P4B_GATE_THRESHOLD_M)
    print(
        f"  P4b at > {P4B_GATE_THRESHOLD_M:g} m requiring >= {dense_min_finite} finite "
        f"cells: {int(dense.sum()):,d} cells, SMRF {_share(smrf_ground, dense):.1f}%, "
        f"PDAL {_share(reference_ground, dense):.1f}%"
    )

    # The consistency control on the construction of the SMRF surface: where both filters call a
    # cell ground, do they agree about where the ground IS?
    lifted = arrays["min_z_reference_ground"] - arrays["min_z_all"]
    both = measured_ground & reference_ground & np.isfinite(lifted)
    n_both = int(both.sum())
    if n_both:
        median = float(np.median(lifted[both]))
        far = 100.0 * float((np.abs(lifted[both]) > 0.5).sum()) / n_both
        print(
            f"  where both our filter and PDAL call a cell ground: {n_both:,d} cells, "
            f"median difference {median:+.3f} m, {far:.2f}% differ by more than 0.5 m"
        )
    else:
        print("  where both our filter and PDAL call a cell ground: no such cells")

    p4a = _share(smrf_ground, measured_ground)
    p4b = _share(smrf_ground, gate_population)
    print()
    print("pre-registered predicates (docs/p4-terrace-preregistration.md):")
    lines = [
        _verdict("P4a our measured ground kept", p4a, P4A_TERRACE_MIN, ">="),
        _verdict(f"P4b kept on a step > {P4B_GATE_THRESHOLD_M:g} m", p4b, P4B_STEEP_MIN, ">="),
    ]
    for text, _ok in lines:
        print(f"  {text}")
    passed = all(ok for _text, ok in lines)
    print(f"\nVERDICT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="compare_ground_filters")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("reference", help="reduce delivery + reference tiles to per-cell arrays")
    r.add_argument("--tiles", type=Path, required=True)
    r.add_argument("--smrf", type=Path, required=True, help="directory of reference-filter output")
    r.add_argument("--suffix", default="-smrf.laz")
    r.add_argument("--aoi", type=Path, required=True)
    r.add_argument("--crs", type=int, default=None)
    r.add_argument("--cell", type=float, default=0.5)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--pipeline", type=Path, default=None, help="the reference pipeline JSON")
    r.add_argument("--reference-name", default="PDAL filters.smrf")
    r.set_defaults(func=_cmd_reference)

    c = sub.add_parser("compare", help="print the population table from a reference file")
    c.add_argument("--reference", type=Path, required=True)
    c.add_argument("--max-window-m", type=float, default=4.0)
    c.add_argument("--slope-threshold", type=float, default=0.3)
    c.add_argument("--elevation-threshold-m", type=float, default=0.3)
    c.add_argument("--max-elevation-m", type=float, default=3.5)
    c.add_argument("--k-min-returns", type=int, default=1)
    c.add_argument("--d-max-interp-m", type=float, default=2.0)
    c.add_argument("--roof-margin", type=int, default=2)
    c.set_defaults(func=_cmd_compare)

    # PDAL's own defaults, so the two filters are compared at the settings the reference ran with.
    # `--smrf-window` is left unset on purpose: `SmrfParams` then applies 18 * cell, which is what
    # `prepared()` does, and passing 18.0 here would hide that rule behind a literal.
    s = sub.add_parser("smrf", help="run this repository's SMRF and compare it cell by cell")
    s.add_argument("--reference", type=Path, required=True)
    s.add_argument(
        "--surface",
        default="min_z_all",
        choices=("min_z_all", "min_z_judged"),
        help="which minimum surface to hand the filter: the pipeline's (all returns) or the "
        "reference's own input rule (last/only)",
    )
    s.add_argument("--smrf-cell", type=float, default=1.0)
    s.add_argument("--smrf-slope", type=float, default=0.15)
    s.add_argument("--smrf-scalar", type=float, default=1.25)
    s.add_argument("--smrf-threshold", type=float, default=0.5)
    s.add_argument("--smrf-window", type=float, default=None)
    s.add_argument("--roof-margin", type=int, default=2)
    s.add_argument("--seam-margin-m", type=float, default=20.0)
    s.set_defaults(func=_cmd_smrf)

    t = sub.add_parser("terraces", help="P4: what our SMRF costs on the terraces")
    t.add_argument("--reference", type=Path, required=True)
    t.add_argument(
        "--surface",
        default="min_z_all",
        choices=("min_z_all", "min_z_judged"),
        help="the surface our SMRF reads, as in the `smrf` command",
    )
    t.add_argument("--step-window-cells", type=int, default=STEP_WINDOW_CELLS)
    t.add_argument("--step-min-finite", type=int, default=STEP_MIN_FINITE)
    t.add_argument("--max-window-m", type=float, default=4.0)
    t.add_argument("--slope-threshold", type=float, default=0.3)
    t.add_argument("--elevation-threshold-m", type=float, default=0.3)
    t.add_argument("--max-elevation-m", type=float, default=3.5)
    t.add_argument("--k-min-returns", type=int, default=1)
    t.add_argument("--d-max-interp-m", type=float, default=2.0)
    t.add_argument("--smrf-cell", type=float, default=1.0)
    t.add_argument("--smrf-slope", type=float, default=0.15)
    t.add_argument("--smrf-scalar", type=float, default=1.25)
    t.add_argument("--smrf-threshold", type=float, default=0.5)
    t.add_argument("--smrf-window", type=float, default=None)
    t.set_defaults(func=_cmd_terraces)

    args = ap.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

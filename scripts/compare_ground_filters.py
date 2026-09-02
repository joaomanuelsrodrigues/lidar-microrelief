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
from scipy.ndimage import binary_erosion

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microrelief.accumulate import Accumulator  # noqa: E402
from microrelief.cli import aoi_bounds  # noqa: E402
from microrelief.density import BASIS_INTERPOLATED, BASIS_MEASURED, compute_basis  # noqa: E402
from microrelief.grid import Grid, grid_for_bounds  # noqa: E402
from microrelief.ground import GroundParams, classify_ground  # noqa: E402
from microrelief.read import read_laz  # noqa: E402

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

        sources.append(
            {
                "tile": tile.name,
                "tile_sha256": batch.source_sha256,
                "reference": reference_path.name,
                "points": int(len(delivery.points)),
            }
        )

    stats = accumulator.finish()
    shape = grid.shape
    return Reference(
        min_z_all=stats.min_z_all,
        max_z_all=stats.max_z_all,
        n_all=stats.n_all,
        n_ground_asprs=stats.n_ground_asprs,
        n_class5=n_class5.reshape(shape).astype(np.int32),
        n_class6=n_class6.reshape(shape).astype(np.int32),
        n_reference_ground=n_reference_ground.reshape(shape).astype(np.int32),
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
    if args.pipeline is not None and args.pipeline.exists():
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
        n_class5=reference.n_class5,
        n_class6=reference.n_class6,
        n_reference_ground=reference.n_reference_ground,
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


def _cmd_compare(args: argparse.Namespace) -> int:
    arrays, provenance = _load_reference(args.reference)
    grid_info = provenance["grid"]
    cell = float(grid_info["cell"])

    params = GroundParams(
        args.max_window_m, args.slope_threshold, args.elevation_threshold_m, args.max_elevation_m
    )
    is_ground = classify_ground(arrays["min_z_all"], cell, params)

    from microrelief.accumulate import CellStats

    stats = CellStats(
        min_z_all=arrays["min_z_all"],
        max_z_all=arrays["max_z_all"],
        n_all=arrays["n_all"],
        n_ground_asprs=arrays["n_ground_asprs"],
        min_z_ground_asprs=arrays["min_z_all"],
        n_outside=0,
    )
    basis = compute_basis(is_ground, stats, cell, args.k_min_returns, args.d_max_interp_m)

    has_c2 = arrays["n_ground_asprs"] > 0
    has_c5 = arrays["n_class5"] > 0
    has_c6 = arrays["n_class6"] > 0
    reference_ground = arrays["n_reference_ground"] > 0

    # Rows A and B, the canopy control and the plain-ground control all reproduce the recorded
    # cell counts EXACTLY. Row C does not: "B, >= 2 cells inside the edge" names an erosion the
    # record never defines operationally, and none of eight readings of it reaches the recorded
    # 3,524,239 (closest 3,487,782). Row C' is our reading, reported as ours and not as a
    # replication -- see `docs/reference-instrument-result.md`.
    building = has_c6 & ~has_c2
    populations = {
        "A: any class-6 return": has_c6,
        "B: class-6, no class-2": building,
        "C': B eroded by roof-margin (OUR reading, not the recorded size)": interior(
            building, margin=args.roof_margin
        ),
        "control: canopy (class 5, no class 2, no class 6)": has_c5 & ~has_c2 & ~has_c6,
        "control: plain ground (class 2, no class 5, no class 6)": has_c2 & ~has_c5 & ~has_c6,
    }

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

    args = ap.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

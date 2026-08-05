"""Three verbs: find the tiles, check whether they can support the product, build it.

`select` and `precheck` need no credentials and no bytes — that split is deliberate, and it is why
the piece can be run end to end by a reader who has no DGT account.

`run` needs no network at all. What it cannot get offline — what the provider *declared* about each
tile — it takes from the file `select` wrote, or it publishes as absent. It never fills the gap with
the number it measured itself: two fields that agree by construction cannot answer the question they
exist for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pyproj import Transformer

from microrelief.accumulate import Accumulator
from microrelief.density import compute_basis, honesty_report
from microrelief.export import export
from microrelief.grid import Grid, grid_for_bounds
from microrelief.ground import GroundParams, agreement, classify_ground
from microrelief.precheck import check_selection
from microrelief.provenance import InputRef, build_provenance
from microrelief.read import read_laz
from microrelief.surfaces import build_surfaces
from microrelief.tiles import search_tiles, select_tiles

TILE_CRS_EPSG = 3763

UNCALIBRATED = (
    "cell",
    "k_min_returns",
    "d_max_interp_m",
    "max_window_m",
    "slope_threshold",
    "elevation_threshold_m",
    "max_elevation_m",
)
LIMITATIONS = (
    "Interpolated cells borrow the nearest measured value; no smoothing is applied.",
    "Ground is decided per cell, not per return; n_ground_asprs is the official count, not ours.",
    "Byte-identical replay is verified on one machine only; cross-machine replay is unverified.",
    "The ground-fraction term of the void expectation is a reference model, not a measurement.",
)


def aoi_bounds(path: Path) -> tuple[float, float, float, float, int]:
    """The AOI's working bounds in the tiles' CRS.

    A declared `properties.bounds_epsg3763` wins over the geometry (§A6: explicit structured input
    beats fuzzy extraction). This is not a preference. A ring written as the WGS84 image of a box in
    EPSG:3763 does not transform back to that box — on the committed AOI it misses by up to 3.8 mm,
    and the file says so in its own note. `grid_for_bounds` floors the origin and ceils the extent,
    so millimetres become half a cell: the grid grows from 3960x3960 to 3961x3962, gains 11,882
    cells that lie outside every tile and publish as `undetermined`, and lands on a different
    `reproducibility_hash`. Re-deriving the box from its own projection is a lossy round trip that
    the AOI file already saves us from taking.
    """
    doc = json.loads(path.read_text())
    properties = doc.get("properties") or {}
    declared = properties.get(f"bounds_epsg{TILE_CRS_EPSG}")
    if declared is not None:
        if not isinstance(declared, list) or len(declared) != 4:
            raise SystemExit(
                f"bounds_epsg{TILE_CRS_EPSG} must be four numbers "
                f"[minx, miny, maxx, maxy], got {declared!r}"
            )
        minx, miny, maxx, maxy = (float(v) for v in declared)
        return minx, miny, maxx, maxy, TILE_CRS_EPSG

    geom = doc["geometry"] if doc.get("type") == "Feature" else doc
    if geom.get("type") != "Polygon":
        raise SystemExit(f"AOI must be a Polygon, got {geom.get('type')}")
    ring = geom["coordinates"][0]
    epsg = int(geom.get("crs_epsg", 4326))
    if epsg == 4326:
        tf = Transformer.from_crs(4326, TILE_CRS_EPSG, always_xy=True)
        pts = [tf.transform(float(lon), float(lat)) for lon, lat in ring]
    elif epsg == TILE_CRS_EPSG:
        pts = [(float(a), float(b)) for a, b in ring]
    else:
        raise SystemExit(f"AOI declares EPSG:{epsg}; expected 4326 or {TILE_CRS_EPSG}")
    xs, ys = zip(*pts, strict=True)
    return min(xs), min(ys), max(xs), max(ys), TILE_CRS_EPSG


def _wgs84_bbox(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """The search bbox. Millimetres of round-trip error are harmless here — this only decides which
    tiles the catalogue is asked about, never where a cell lands."""
    tf = Transformer.from_crs(TILE_CRS_EPSG, 4326, always_xy=True)
    lon0, lat0 = tf.transform(bounds[0], bounds[1])
    lon1, lat1 = tf.transform(bounds[2], bounds[3])
    return lon0, lat0, lon1, lat1


def _selection_for(args: argparse.Namespace) -> Any:
    minx, miny, maxx, maxy, _ = aoi_bounds(args.aoi)
    bounds = (minx, miny, maxx, maxy)
    return select_tiles(
        search_tiles(_wgs84_bbox(bounds)), bounds, allow_mixed_epochs=args.allow_mixed_epochs
    )


def _cmd_select(args: argparse.Namespace) -> int:
    sel = _selection_for(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "aoi_bounds": list(sel.aoi_bounds),
                "covered_fraction": sel.covered_fraction,
                "flight_dates": list(sel.flight_dates),
                "sorties": [list(g) for g in sel.sorties],
                "mixed_epochs": sel.mixed_epochs,
                "dropped_duplicates": list(sel.dropped_duplicates),
                "tiles": [
                    {
                        "item_id": t.item_id,
                        "href": t.href,
                        "file_size": t.file_size,
                        "point_count": t.point_count,
                        "flight_date": t.flight_date,
                        "density": t.density,
                        # The box the catalogue derived from the returns. Carried through so `run`
                        # can check the bytes it reads against what the provider declared.
                        "bbox": [t.minx, t.miny, t.maxx, t.maxy],
                    }
                    for t in sel.tiles
                ],
            },
            indent=2,
        )
    )
    print(
        f"{len(sel.tiles)} tiles, coverage {sel.covered_fraction:.4f}, "
        f"{len(sel.sorties)} sortie(s), {len(sel.flight_dates)} stamp(s) -> {args.out.name}"
    )
    return 0


def _cmd_precheck(args: argparse.Namespace) -> int:
    sel = _selection_for(args)
    for e in check_selection(
        sel, args.cell, args.ground_fraction, args.max_void_fraction, args.allow_sparse
    ):
        print(
            f"{e.item_id}  {e.density:5.1f} pts/m2  {e.flight_date[:10]}  "
            f"void(open)={e.void_open_ground:.3%}  void(f={args.ground_fraction})={e.void_at_f:.1%}"
        )
    return 0


def _catalogue_facts(path: Path | None) -> dict[str, dict[str, Any]] | None:
    if path is None:
        return None
    doc = json.loads(path.read_text())
    return {str(t["item_id"]): t for t in doc["tiles"]}


def _read_inputs(
    paths: list[Path], grid: Grid, catalogue: dict[str, dict[str, Any]] | None
) -> tuple[Accumulator, list[InputRef], list[str]]:
    acc = Accumulator(grid)
    inputs: list[InputRef] = []
    flight_dates: list[str] = []
    for path in paths:
        entry = None
        if catalogue is not None:
            entry = catalogue.get(path.stem)
            if entry is None:
                raise SystemExit(
                    f"{path.stem} is not in the selection ({', '.join(sorted(catalogue))}); "
                    f"refusing to publish catalogue facts for some tiles and none for others"
                )
        declared = entry.get("bbox") if entry else None
        footprint = (
            (float(declared[0]), float(declared[1]), float(declared[2]), float(declared[3]))
            if declared
            else None
        )
        batch = read_laz(path, expect_epsg=grid.crs_epsg, footprint=footprint)
        acc.add(batch)
        minx, miny, maxx, maxy = batch.bounds
        area = (maxx - minx) * (maxy - miny)
        flight_date = str(entry["flight_date"]) if entry else None
        if flight_date is not None:
            flight_dates.append(flight_date)
        inputs.append(
            InputRef(
                item_id=path.stem,
                file_name=path.name,
                sha256=batch.source_sha256,
                point_count_catalogue=int(entry["point_count"]) if entry else None,
                point_count_measured=batch.n_points_in_file,
                density_measured=batch.density(area) if area > 0 else 0.0,
                flight_date=flight_date,
                point_count_noise_excluded=batch.n_noise_excluded,
            )
        )
    return acc, inputs, flight_dates


def _cmd_run(args: argparse.Namespace) -> int:
    minx, miny, maxx, maxy, epsg = aoi_bounds(args.aoi)
    paths = sorted(args.laz.glob("*.laz"))
    if not paths:
        print(f"no .laz files in {args.laz}", file=sys.stderr)
        return 2

    grid = grid_for_bounds(minx, miny, maxx, maxy, args.cell, epsg)
    acc, inputs, flight_dates = _read_inputs(paths, grid, _catalogue_facts(args.selection))
    stats = acc.finish()

    params = GroundParams(
        args.max_window_m, args.slope_threshold, args.elevation_threshold_m, args.max_elevation_m
    )
    is_ground = classify_ground(stats.min_z_all, args.cell, params)
    basis = compute_basis(is_ground, stats, args.cell, args.k_min_returns, args.d_max_interp_m)
    surfaces = build_surfaces(grid, stats, basis)

    # The grid's own area, not the AOI as asked for: `grid_for_bounds` snaps outward to whole
    # cells, and the honesty report counts cells of that grid. Dividing them by the requested
    # extent would put the count over a denominator it was never taken from (§A1/s258).
    grid_area = grid.n_cells * grid.cell * grid.cell
    honesty = honesty_report(basis.basis, stats, args.cell, grid_area)
    agree = agreement(is_ground, stats)

    prov = build_provenance(
        grid=grid,
        parameters={
            "cell": args.cell,
            "k_min_returns": args.k_min_returns,
            "d_max_interp_m": args.d_max_interp_m,
            "max_window_m": args.max_window_m,
            "slope_threshold": args.slope_threshold,
            "elevation_threshold_m": args.elevation_threshold_m,
            "max_elevation_m": args.max_elevation_m,
        },
        inputs=inputs,
        honesty=honesty.as_dict(),
        agreement=agree.as_dict(),
        flight_dates=flight_dates,
        uncalibrated=UNCALIBRATED,
        limitations=LIMITATIONS,
    )
    export(surfaces, prov, args.out)

    print(
        f"grid {grid.n_rows} x {grid.n_cols} cells of {grid.cell} m "
        f"({grid_area / 1e6:.4f} km2), {len(inputs)} tile(s), "
        f"{stats.n_outside} return(s) outside the AOI"
    )
    print(
        f"measured {honesty.fraction_measured:.1%} | interpolated "
        f"{honesty.fraction_interpolated:.1%} | undetermined {honesty.fraction_undetermined:.1%}"
    )
    print(
        f"expected void at f=1: {honesty.expected_void_fraction:.3%} "
        f"(measured density {honesty.measured_density:.1f} pts/m2)"
    )
    print(
        f"ground recall {agree.recall_ground:.3f} | non-ground recall "
        f"{agree.recall_nonground:.3f} | accuracy {agree.accuracy:.3f} | "
        f"majority-class null {agree.majority_class_null:.3f}"
    )
    print(
        f"flight dates {', '.join(prov.flight_dates) or '(none declared)'} | "
        f"mixed epochs {prov.mixed_epochs}"
    )
    print(f"reproducibility_hash {prov.reproducibility_hash}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="microrelief")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("select", "precheck", "run"):
        p = sub.add_parser(name)
        p.add_argument("--aoi", type=Path, required=True)
        p.add_argument("--allow-mixed-epochs", action="store_true")
        if name == "select":
            p.add_argument("--out", type=Path, required=True)
        if name in ("precheck", "run"):
            p.add_argument("--cell", type=float, default=0.5)
        if name == "precheck":
            p.add_argument("--ground-fraction", type=float, default=0.4)
            p.add_argument("--max-void-fraction", type=float, default=0.35)
            p.add_argument("--allow-sparse", action="store_true")
        if name == "run":
            p.add_argument("--laz", type=Path, required=True)
            p.add_argument("--out", type=Path, required=True)
            p.add_argument(
                "--selection",
                type=Path,
                default=None,
                help="the JSON written by `select`; without it the record declares that it does "
                "not know what the provider claimed, rather than repeating what we measured",
            )
            p.add_argument("--k-min-returns", type=int, default=1)
            p.add_argument("--d-max-interp-m", type=float, default=2.0)
            p.add_argument("--max-window-m", type=float, default=4.0)
            p.add_argument("--slope-threshold", type=float, default=0.3)
            p.add_argument("--elevation-threshold-m", type=float, default=0.3)
            p.add_argument("--max-elevation-m", type=float, default=3.0)

    args = ap.parse_args(argv)
    try:
        return {"select": _cmd_select, "precheck": _cmd_precheck, "run": _cmd_run}[args.cmd](args)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # a refusal is an exit code with a reason, not a traceback
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

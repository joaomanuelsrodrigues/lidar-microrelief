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
from microrelief.crs import CRSError, require_metric_crs
from microrelief.density import compute_basis, honesty_report
from microrelief.export import export
from microrelief.grid import Grid, grid_for_bounds
from microrelief.ground import GroundParams, agreement, classify_ground
from microrelief.precheck import check_tiles
from microrelief.provenance import InputRef, build_provenance
from microrelief.read import read_laz
from microrelief.surfaces import build_surfaces

# max_elevation_m is deliberately absent since 0.3.0: it carries a site measurement (tallest
# verified terrace riser 2.98 m, docs/riser-measurement.md) rather than a declared guess, which
# is what this list exists to disclose. The measured value is Sistelo's, not a constant of
# terraces - CALIBRATIONS.md says so in its row.
UNCALIBRATED = (
    "cell",
    "k_min_returns",
    "d_max_interp_m",
    "max_window_m",
    "slope_threshold",
    "elevation_threshold_m",
)
LIMITATIONS = (
    "Interpolated cells borrow the nearest measured value; no smoothing is applied.",
    "Ground is decided per cell, not per return; n_ground_asprs is the official count, not ours.",
    "Byte-identical replay on real data is not established: one corrupted and one failed read "
    "of four on 2026-08-05, neither reproduced in 192 controlled re-reads across backends, "
    "memory pressure and cold caches; root cause open (docs/live-smoke.md 2026-08-08).",
    "Cross-machine replay is unverified.",
    "The reproducibility hash sees code only through the package version; the bump is enforced "
    "only by a warn-class CI check.",
    "The ground-fraction term of the void expectation is a reference model, not a measurement.",
    "Calling select_tiles as a library function bypasses the AOI-vs-tile CRS check, which "
    "lives at the CLI's composition root.",
    "scripts/measure_risers.py takes no --crs, so it can only work an AOI that declares its "
    "own projected CRS.",
    "The reproducibility hash does not cover the attribution string: two runs differing "
    "only in --attribution share a hash, so a product can be relabelled and keep its anchor.",
    "The only resource ceiling is a cell count (200,000,000 cells, ~12 GB of per-cell "
    "arrays), not a memory bound: a grid inside it can still exhaust memory, and that "
    "failure is an OOM kill rather than a refusal with a reason.",
)


def aoi_bounds(path: Path, crs: int | None = None) -> tuple[float, float, float, float, int]:
    """The AOI's working bounds and the CRS they are in.

    A declared `properties.bounds` + `properties.bounds_epsg` wins over the geometry: an
    explicit declaration beats a value inferred from one. This is not a preference. A ring written
    as the WGS84 image of a box in a projected CRS does not transform back to that box — on the
    committed AOI it misses by up to 3.8 mm, and the file says so in its own note.
    `grid_for_bounds` floors the origin and ceils the extent, so millimetres become half a cell:
    the grid grew from 3960x3960 to 3961x3962, gained 11,882 cells lying outside every tile that
    publish as `undetermined`, and landed on a different `reproducibility_hash`. Re-deriving the
    box from its own projection is a lossy round trip the AOI file already saves us from taking.

    The ring path is kept anyway (operator ruling D-1): it is what a reader drawing their own
    polygon hands over, and the millimetre error is accepted on that path alone. What is not
    kept is the guess about *which* CRS to project into — that was Portugal's, welded into a
    general code path, and it is now either declared in the file or named with `--crs`.
    """
    doc = json.loads(path.read_text())
    properties = doc.get("properties") or {}
    declared = properties.get("bounds")
    if declared is not None:  # case 1
        epsg = properties.get("bounds_epsg")
        if not isinstance(epsg, int):
            raise SystemExit(
                "properties.bounds needs a sibling properties.bounds_epsg naming the CRS "
                "those numbers are in; refusing to assume one"
            )
        if not isinstance(declared, list) or len(declared) != 4:
            raise SystemExit(
                f"bounds must be four numbers [minx, miny, maxx, maxy], got {declared!r}"
            )
        require_metric_crs(epsg)
        minx, miny, maxx, maxy = (float(v) for v in declared)
        return minx, miny, maxx, maxy, epsg

    geom = doc["geometry"] if doc.get("type") == "Feature" else doc
    if geom.get("type") != "Polygon":
        raise SystemExit(f"AOI must be a Polygon, got {geom.get('type')}")
    ring = geom["coordinates"][0]
    ring_epsg = int(geom.get("crs_epsg", 4326))

    target = properties.get("bounds_epsg")  # case 2
    if not isinstance(target, int):
        target = crs  # case 4
    if target is not None:
        # A CRS was named. If it is unusable, say so as itself — the caller does not need to be
        # told how to name one, they need to be told why the one they named will not do.
        require_metric_crs(target)
        if target == ring_epsg:
            pts = [(float(a), float(b)) for a, b in ring]
        else:
            tf = Transformer.from_crs(ring_epsg, target, always_xy=True)
            pts = [tf.transform(float(a), float(b)) for a, b in ring]
        xs, ys = zip(*pts, strict=True)
        return min(xs), min(ys), max(xs), max(ys), target

    # Case 3, and case 5 when it fails: nothing was named, so the ring's own CRS has to serve as
    # the working one — which it can only do if it is metric.
    try:
        require_metric_crs(ring_epsg)
    except CRSError as exc:
        raise SystemExit(
            f"{exc}\n\n"
            f"This AOI is a ring in EPSG:{ring_epsg} and names no working CRS of its own. Name "
            f"the projection its numbers should be worked in, either with --crs <epsg> or by "
            f"adding properties.bounds_epsg to the file. This package will not assume a "
            f"national grid."
        ) from exc
    pts = [(float(a), float(b)) for a, b in ring]
    xs, ys = zip(*pts, strict=True)
    return min(xs), min(ys), max(xs), max(ys), ring_epsg


def _wgs84_bbox(
    bounds: tuple[float, float, float, float], epsg: int
) -> tuple[float, float, float, float]:
    """The search bbox. Millimetres of round-trip error are harmless here — this only decides
    which tiles the catalogue is asked about, never where a cell lands."""
    tf = Transformer.from_crs(epsg, 4326, always_xy=True)
    lon0, lat0 = tf.transform(bounds[0], bounds[1])
    lon1, lat1 = tf.transform(bounds[2], bounds[3])
    return lon0, lat0, lon1, lat1


def _dgt() -> Any:
    """Imported here, not at module scope: `run` needs no catalogue and no network, so the
    core install must not have to carry an HTTP client to use it."""
    try:
        from microrelief.providers import dgt
    except ImportError as exc:
        raise SystemExit(
            "the DGT provider needs the optional 'dgt' extra: pip install 'microrelief[dgt]'"
        ) from exc
    return dgt


def _selection_for(args: argparse.Namespace) -> Any:
    minx, miny, maxx, maxy, epsg = aoi_bounds(args.aoi, args.crs)
    bounds = (minx, miny, maxx, maxy)
    dgt = _dgt()
    tiles = dgt.search_tiles(_wgs84_bbox(bounds, epsg))

    # The AOI's CRS and the provider's are only ever paired HERE — this is the composition root,
    # and the pairing is a fact about the composition, not about either layer. Checked before the
    # overlap arithmetic, because that arithmetic is exactly what goes silently wrong: boxes in two
    # different CRSs do not overlap, so the failure would surface as "no tile intersects" and send
    # the reader looking for a coverage problem they do not have.
    # `len(tile_crs) == 1` was the wrong condition, and the way it was wrong is the point: a
    # single tile in a second CRS anywhere in the search box turned the check off, and
    # `select_tiles` compares CRSs only among the tiles that *touch* the AOI. Every searched
    # tile's box is compared against these bounds by `_overlap_area`, so what has to hold is
    # that all of them are in the AOI's CRS -- not that they agree among themselves.
    tile_crs = {t.crs_epsg for t in tiles}
    if tile_crs and tile_crs != {epsg}:
        named = ", ".join(f"EPSG:{c}" for c in sorted(tile_crs))
        advice = (
            f"Supply an AOI in EPSG:{next(iter(tile_crs))}, or set properties.bounds_epsg / "
            f"--crs accordingly."
            if len(tile_crs) == 1
            else f"This provider is serving {len(tile_crs)} coordinate systems over this box, "
            f"so no single AOI CRS matches them all; narrow the AOI or ask the provider."
        )
        raise SystemExit(
            f"the AOI is in EPSG:{epsg} and this provider's tiles are in {named}. "
            f"Comparing their boxes would intersect two different coordinate systems. {advice}"
        )

    return dgt.select_tiles(tiles, bounds, allow_mixed_epochs=args.allow_mixed_epochs)


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
    for e in check_tiles(
        sel.tiles, args.cell, args.ground_fraction, args.max_void_fraction, args.allow_sparse
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
) -> tuple[Accumulator, list[InputRef], list[str], bool]:
    acc = Accumulator(grid)
    inputs: list[InputRef] = []
    flight_dates: list[str] = []
    official_ground = True
    missing: list[str] = []
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
        if not batch.has_official_ground:
            official_ground = False
            missing.append(path.stem)
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
    if missing:
        # All-or-nothing on purpose: comparing over a mosaic where some tiles are classified
        # and others are not mixes 'measured non-ground' with 'never classified' in one
        # number. Named, so the reader knows which tiles.
        print(
            f"no ASPRS class 2 in {', '.join(sorted(missing))}; agreement with the official "
            f"classification is declared absent for this product, not computed over the rest",
            file=sys.stderr,
        )
    return acc, inputs, flight_dates, official_ground


def _cmd_run(args: argparse.Namespace) -> int:
    minx, miny, maxx, maxy, epsg = aoi_bounds(args.aoi, args.crs)
    paths = sorted(args.laz.glob("*.laz"))
    if not paths:
        print(f"no .laz files in {args.laz}", file=sys.stderr)
        return 2

    grid = grid_for_bounds(minx, miny, maxx, maxy, args.cell, epsg)
    acc, inputs, flight_dates, official_ground = _read_inputs(
        paths, grid, _catalogue_facts(args.selection)
    )
    stats = acc.finish()

    params = GroundParams(
        args.max_window_m, args.slope_threshold, args.elevation_threshold_m, args.max_elevation_m
    )
    is_ground = classify_ground(stats.min_z_all, args.cell, params)
    basis = compute_basis(is_ground, stats, args.cell, args.k_min_returns, args.d_max_interp_m)
    surfaces = build_surfaces(grid, stats, basis)

    # The grid's own area, not the AOI as asked for: `grid_for_bounds` snaps outward to whole
    # cells, and the honesty report counts cells of that grid. Dividing them by the requested
    # extent would put the count over a denominator it was never taken from (2026-08-04).
    grid_area = grid.n_cells * grid.cell * grid.cell
    honesty = honesty_report(basis.basis, stats, args.cell, grid_area)
    agree = agreement(is_ground, stats) if official_ground else None

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
        agreement=agree.as_dict() if agree is not None else None,
        attribution=args.attribution,
        flight_dates=flight_dates,
        uncalibrated=UNCALIBRATED,
        limitations=LIMITATIONS,
    )
    export(surfaces, prov, args.out, official_ground_available=official_ground)

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
    if agree is not None:
        print(
            f"ground recall {agree.recall_ground:.3f} | non-ground recall "
            f"{agree.recall_nonground:.3f} | accuracy {agree.accuracy:.3f} | "
            f"majority-class null {agree.majority_class_null:.3f}"
        )
    else:
        print(
            "agreement with the official classification: "
            "not available (no ASPRS class 2 in the input)"
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
        p.add_argument(
            "--crs",
            type=int,
            default=None,
            help="EPSG code of the projected, metre-based CRS to work in. Required only when "
            "the AOI is a bare WGS84 ring that declares no CRS of its own; a file carrying "
            "properties.bounds_epsg or geometry.crs_epsg has already said.",
        )
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
            # 3.5, not the original 3.0: the tallest verified terrace riser at the calibration
            # site measures 2.98 m, and a cap 2 cm above a riser is not above it within the
            # 0.2-0.3 m LiDAR error band (docs/riser-measurement.md, operator ruling 2026-08-08).
            p.add_argument("--max-elevation-m", type=float, default=3.5)
            p.add_argument(
                "--attribution",
                required=True,
                help="the source of the point cloud and its licence, written into "
                "provenance.json and into every raster's tags. Required: this package cannot "
                "know whose data it was handed, and guessing would publish a false claim.",
            )

    args = ap.parse_args(argv)
    try:
        return {"select": _cmd_select, "precheck": _cmd_precheck, "run": _cmd_run}[args.cmd](args)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # a refusal is an exit code with a reason, not a traceback
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # `python -m microrelief.cli ...`
    # Without this, the module form exits 0 having done nothing: a silent success that no
    # exit-code check can tell from a real run. Asserted by an artefact, not a return code
    # (tests/test_packaging.py). The form a reader without the console script on PATH
    # actually reaches for is `python -m microrelief`, which needs `__main__.py` beside this
    # file -- adding only this guard would have left that one failing (review, s293).
    raise SystemExit(main())

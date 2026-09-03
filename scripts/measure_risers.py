"""Measure terrace-riser heights on the official-ground minimum surface.

Instrument for `docs/riser-measurement.md`, which pre-registers the method, the zone, every
parameter below, and the verdict rule — read it first. This script deliberately measures the
per-cell minimum of official ASPRS class-2 returns (`min_z_ground_asprs`), never our own DTM:
`max_elevation_m` was the parameter being calibrated when this ran, so a surface shaped by our
own filter would have been circular. It stayed that way after 0.5.0 retired that parameter from
the pipeline, for the same reason — the riser heights are a property of the terrain, and reading
them off a surface our filter shaped would make them a property of the filter.

Two stages, so analysis does not re-read 845 MB:

    build:   PYTHONPATH=src .venv/bin/python scripts/measure_risers.py build \\
                 --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --cache /tmp/riser_surface.npz
    measure: PYTHONPATH=src .venv/bin/python scripts/measure_risers.py measure \\
                 --cache /tmp/riser_surface.npz --basis outputs/basis.tif --out /tmp/risers.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from microrelief.accumulate import Accumulator
from microrelief.cli import aoi_bounds
from microrelief.grid import grid_for_bounds
from microrelief.read import read_laz

# Zone Z and instrument parameters — pre-registered in docs/riser-measurement.md. Not production
# thresholds: nothing in src/ reads them.
ZONE = (-20400.0, 255600.0, -19600.0, 256400.0)  # minx, miny, maxx, maxy (EPSG:3763)
S_STEEP = 0.8
S_TREAD = 0.27
TREAD_LEN_M = 2.0
MAX_RISER_WIDTH_M = 3.0
MIN_HEIGHT_M = 0.5
CLUSTER_RADIUS_M = 5.0
RELIEF_MAX_LAG_M = 2.0


@dataclass
class Candidate:
    x: float
    y: float
    height_m: float
    width_m: float
    direction: str
    n_run: int  # steep-run samples, i.e. its official-ground support
    tread_before_m: float
    tread_after_m: float


def build(aoi: Path, laz_dir: Path, cache: Path) -> int:
    minx, miny, maxx, maxy, epsg = aoi_bounds(aoi)
    grid = grid_for_bounds(minx, miny, maxx, maxy, 0.5, epsg)
    acc = Accumulator(grid)
    for path in sorted(laz_dir.glob("*.laz")):
        acc.add(read_laz(path, expect_epsg=epsg))
        print(f"added {path.name}")
    stats = acc.finish()
    np.savez_compressed(
        cache,
        min_z_ground=stats.min_z_ground_asprs,
        n_ground=stats.n_ground_asprs,
        origin_x=grid.origin_x,
        origin_y=grid.origin_y,
        cell=grid.cell,
        crs_epsg=grid.crs_epsg,
    )
    print(f"cached official-ground surface {stats.min_z_ground_asprs.shape} -> {cache}")
    return 0


Profile = tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]


def profiles_by_direction(z: NDArray[np.float64], cell: float) -> list[tuple[str, float, list]]:
    """1-D profiles through the zone: rows, columns and both diagonals, each with its grid
    indices, so a detection can be placed back on the map."""
    n_rows, n_cols = z.shape
    rows_idx, cols_idx = np.indices(z.shape)
    zf, rf, cf = z[::-1], rows_idx[::-1], cols_idx[::-1]
    diag_range = range(-n_rows + 2, n_cols - 1)
    return [
        ("row", cell, [(z[r, :], rows_idx[r, :], cols_idx[r, :]) for r in range(n_rows)]),
        ("col", cell, [(z[:, c], rows_idx[:, c], cols_idx[:, c]) for c in range(n_cols)]),
        (
            "diag",
            cell * float(np.sqrt(2.0)),
            [
                (np.diagonal(z, o), np.diagonal(rows_idx, o), np.diagonal(cols_idx, o))
                for o in diag_range
            ],
        ),
        (
            "adiag",
            cell * float(np.sqrt(2.0)),
            [(np.diagonal(zf, o), np.diagonal(rf, o), np.diagonal(cf, o)) for o in diag_range],
        ),
    ]


def scan_profile(v: NDArray[np.float64], h: float, direction: str) -> list[tuple[int, Candidate]]:
    """Riser candidates on one profile, per the pre-registered definition. Strict adjacency: the
    bounding treads start at the steep run's end samples, no transition samples allowed. Returns
    (midpoint sample index, candidate) — coordinates are attached by the caller."""
    n = v.size
    if n < 3:
        return []
    slope = np.full(n - 1, np.nan)
    both = np.isfinite(v[:-1]) & np.isfinite(v[1:])
    slope[both] = (v[1:][both] - v[:-1][both]) / h

    tread_min = int(np.ceil(TREAD_LEN_M / h))
    max_run = int(np.floor(MAX_RISER_WIDTH_M / h))
    is_tread = np.abs(slope) <= S_TREAD  # NaN compares False: a broken gap is never a tread
    is_steep = np.abs(slope) >= S_STEEP

    # before[i]: consecutive tread gaps ending at gap i-1. after[j]: starting at gap j.
    before = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        before[i] = before[i - 1] + 1 if is_tread[i - 1] else 0
    after = np.zeros(n, dtype=np.int64)
    for i in range(n - 2, -1, -1):
        after[i] = after[i + 1] + 1 if is_tread[i] else 0

    found: list[tuple[int, Candidate]] = []
    i = 0
    while i < n - 1:
        if not is_steep[i]:
            i += 1
            continue
        sign = np.sign(slope[i])
        j = i
        while j < n - 1 and is_steep[j] and np.sign(slope[j]) == sign:
            j += 1
        run_gaps = j - i  # steep run spans gaps [i, j), samples [i, j]
        height = abs(float(v[j] - v[i]))
        if (
            run_gaps <= max_run
            and height >= MIN_HEIGHT_M
            and before[i] >= tread_min
            and after[j] >= tread_min
        ):
            found.append(
                (
                    (i + j) // 2,
                    Candidate(
                        x=np.nan,
                        y=np.nan,
                        height_m=round(height, 3),
                        width_m=round(run_gaps * h, 3),
                        direction=direction,
                        n_run=run_gaps + 1,
                        tread_before_m=round(float(before[i]) * h, 2),
                        tread_after_m=round(float(after[j]) * h, 2),
                    ),
                )
            )
        i = j
    return found


def cluster(cands: list[Candidate], radius: float) -> list[Candidate]:
    """Greedy by height with a spatial hash: the same wall seen by adjacent profiles is one riser.
    A long wall still yields one cluster per ~radius of its length, which is fine — the question
    is the tallest riser, not the number of walls."""
    kept: list[Candidate] = []
    buckets: dict[tuple[int, int], list[Candidate]] = {}
    for c in sorted(cands, key=lambda c: -c.height_m):
        bx, by = int(c.x // radius), int(c.y // radius)
        near = (
            k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in buckets.get((bx + dx, by + dy), [])
        )
        if any((k.x - c.x) ** 2 + (k.y - c.y) ** 2 <= radius**2 for k in near):
            continue
        kept.append(c)
        buckets.setdefault((bx, by), []).append(c)
    return kept


def measure(cache: Path, basis_path: Path | None, out: Path) -> int:
    dat = np.load(cache)
    z_full = np.asarray(dat["min_z_ground"], dtype=np.float64)
    origin_x, origin_y, cell = float(dat["origin_x"]), float(dat["origin_y"]), float(dat["cell"])

    zminx, zminy, zmaxx, zmaxy = ZONE
    col0 = int((zminx - origin_x) / cell)
    col1 = int((zmaxx - origin_x) / cell)
    row0 = int((origin_y - zmaxy) / cell)
    row1 = int((origin_y - zminy) / cell)
    z = z_full[row0:row1, col0:col1]

    n_cells = z.size
    n_valid = int(np.isfinite(z).sum())
    report: dict[str, object] = {
        "zone": ZONE,
        "zone_cells": n_cells,
        "zone_cells_with_official_ground": n_valid,
        "zone_coverage": round(n_valid / n_cells, 4),
    }

    candidates: list[Candidate] = []
    relief: dict[str, dict[int, float]] = {}
    for name, h, profs in profiles_by_direction(z, cell):
        max_lag = int(np.floor(RELIEF_MAX_LAG_M / h))
        lag_max = dict.fromkeys(range(1, max_lag + 1), 0.0)
        for v, rows, cols in profs:
            vv = np.asarray(v, dtype=np.float64)
            for mid, cand in scan_profile(vv, h, name):
                cand.x = round(origin_x + (col0 + int(cols[mid]) + 0.5) * cell, 2)
                cand.y = round(origin_y - (row0 + int(rows[mid]) + 0.5) * cell, 2)
                candidates.append(cand)
            for lag in lag_max:
                if vv.size > lag:
                    d = np.abs(vv[lag:] - vv[:-lag])
                    if np.isfinite(d).any():
                        lag_max[lag] = max(lag_max[lag], float(np.nanmax(d)))
        relief[name] = {k: round(val, 3) for k, val in lag_max.items()}

    clusters = cluster(candidates, CLUSTER_RADIUS_M)
    report["n_candidates"] = len(candidates)
    report["n_clusters"] = len(clusters)
    if candidates:
        heights = np.array([c.height_m for c in candidates])
        report["height_p50"] = round(float(np.percentile(heights, 50)), 3)
        report["height_p90"] = round(float(np.percentile(heights, 90)), 3)
        report["height_max"] = round(float(heights.max()), 3)
    report["unconditional_relief_max_by_direction_and_lag"] = relief
    top = [asdict(c) for c in clusters[:20]]
    report["top_clusters"] = top

    if basis_path is not None and basis_path.exists():
        import rasterio

        with rasterio.open(basis_path) as src:
            basis = src.read(1)
        for entry in top:
            col = int((entry["x"] - origin_x) / cell)
            row = int((origin_y - entry["y"]) / cell)
            entry["dtm_basis_at_cell"] = int(basis[row, col])

    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "top_clusters"}, indent=2))
    print("top clusters:")
    for entry in top[:10]:
        print(
            f"  ({entry['x']:9.1f}, {entry['y']:9.1f})  h={entry['height_m']:5.2f} m  "
            f"w={entry['width_m']:4.1f} m  {entry['direction']:5s}  "
            f"treads {entry['tread_before_m']:4.1f}/{entry['tread_after_m']:4.1f} m  "
            f"basis={entry.get('dtm_basis_at_cell', '?')}"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--aoi", type=Path, required=True)
    b.add_argument("--laz", type=Path, required=True)
    b.add_argument("--cache", type=Path, required=True)
    m = sub.add_parser("measure")
    m.add_argument("--cache", type=Path, required=True)
    m.add_argument("--basis", type=Path, default=None)
    m.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "build":
        return build(args.aoi, args.laz, args.cache)
    return measure(args.cache, args.basis, args.out)


if __name__ == "__main__":
    raise SystemExit(main())

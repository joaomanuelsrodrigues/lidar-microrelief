"""The §A1 gate: read real DGT LAZ end to end and measure what the site was chosen on.

Everything before this ran against files we wrote ourselves, which proves wiring and not
behaviour. This script is the one place where a claim about reading DGT data is supported.

Three measurements, in the order in which one can invalidate the next:

1. Read a tile and report what it contains. A real tile brings its own LAS version, point
   format, scale/offset and CRS-in-VLR; none of that is exercised by a synthetic file.
2. Measured point count against the catalogue's `pc:count`. The whole pre-download triage
   instrument rests on that field being a point count. If it is not, the triage is built on a
   number that does not mean what it was assumed to mean, and nothing downstream is safe.
3. Criterion 2 (canopy) over the chosen AOI, reported both as an aggregate and as a spatial
   distribution. The aggregate alone cannot answer the doubt that was actually recorded, which
   was that the terraces are open pasture inside an otherwise wooded valley: a high average is
   consistent with the terraces themselves being bare. So the per-block distribution is what the
   verdict is read from.

Usage: python scripts/smoke_task9.py [--laz ~/data/dgt-laz]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from pyproj import Transformer

from microrelief.precheck import expected_void_fraction
from microrelief.read import ASPRS_GROUND, read_laz
from microrelief.tiles import search_tiles

# The AOI chosen in Task 6, EPSG:3763 (ETRS89 / PT-TM06). See SITE.md.
AOI = (-20990.0, 255010.0, -19010.0, 256990.0)
FINE_BLOCK_M = 10.0  # local ground reference
COARSE_BLOCK_M = 100.0  # spatial distribution of the canopy share
CELL_M = 0.5


def height_above_local_ground(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, is_ground: np.ndarray
) -> np.ndarray:
    """Height above the lowest ground return in each 10 m block.

    Blocks are anchored to the AOI, never to the tile: a per-tile anchor puts a different
    reference under points that sit either side of a tile seam.

    The accumulator array starts at +inf, not NaN. `np.minimum(nan, z)` is NaN, so a NaN seed
    poisons every block it touches and every height comes back NaN — a measurement that reports
    zero returns above any height, which reads exactly like a finding about the site rather than
    a defect in the instrument. Blocks that genuinely never see a ground return keep +inf, and
    the subtraction turns them into -inf, which the caller drops as "no reference here".
    """
    ny = int(np.ceil((AOI[3] - AOI[1]) / FINE_BLOCK_M))
    nx = int(np.ceil((AOI[2] - AOI[0]) / FINE_BLOCK_M))
    key = ((x - AOI[0]) // FINE_BLOCK_M).astype(np.int64) * ny + (
        (y - AOI[1]) // FINE_BLOCK_M
    ).astype(np.int64)
    base = np.full(nx * ny, np.inf)
    np.minimum.at(base, key[is_ground], z[is_ground])
    return np.asarray(z - base[key])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--laz", type=Path, default=Path.home() / "data" / "dgt-laz")
    args = ap.parse_args()
    paths = sorted(args.laz.glob("*.laz"))
    if not paths:
        raise SystemExit(f"no .laz files under {args.laz}")

    to_wgs = Transformer.from_crs(3763, 4326, always_xy=True)
    minlon, minlat = to_wgs.transform(AOI[0], AOI[1])
    maxlon, maxlat = to_wgs.transform(AOI[2], AOI[3])
    catalogue = {t.item_id: t for t in search_tiles((minlon, minlat, maxlon, maxlat))}

    print("== 1. read a real tile ==")
    # Explicit now that `read_laz` has no default: this driver is DGT-specific by construction
    # (the AOI above is EPSG:3763), so it declares the CRS it expects rather than inheriting one.
    first = read_laz(paths[0], expect_epsg=3763)
    classes = dict(zip(*np.unique(first.classification, return_counts=True), strict=True))
    print(f"file           {paths[0].name}")
    print(f"points         {first.n_points:,}")
    print(f"bounds         {[round(v, 3) for v in first.bounds]}")
    print(f"crs            {first.crs_epsg}")
    print(f"density        {first.density(1_000_000):.2f} pts/m2")
    print(f"classes        { ({int(k): int(v) for k, v in classes.items()}) }")
    print(f"ground share   {float((first.classification == ASPRS_GROUND).mean()):.3f}")
    print(f"sha256         {first.source_sha256}")

    print("\n== 2. measured count vs catalogue pc:count ==")
    print(f"{'tile':22s}{'catalogue':>14s}{'measured':>14s}{'delta':>8s}  bounds  date")
    n_edges = int(np.ceil((AOI[3] - AOI[1]) / COARSE_BLOCK_M))
    n_cols = int(np.ceil((AOI[2] - AOI[0]) / COARSE_BLOCK_M))
    above2 = np.zeros(n_cols * n_edges, np.int64)
    total = np.zeros(n_cols * n_edges, np.int64)
    n_ground = n_in_aoi = n_with_ref = 0
    hist = np.zeros(7, np.int64)
    edges = np.array([-np.inf, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, np.inf])

    aoi_classes: dict[int, int] = {}
    for p in paths:
        b = read_laz(p, expect_epsg=3763)
        ref = catalogue[p.stem]
        same = [round(v, 3) for v in b.bounds] == [ref.minx, ref.miny, ref.maxx, ref.maxy]
        print(
            f"{p.stem:22s}{ref.point_count:>14,}{b.n_points:>14,}"
            f"{b.n_points - ref.point_count:>8,}  {'ok' if same else 'DIFFERS':7s} "
            f"{ref.flight_date}"
        )

        inside = (b.x >= AOI[0]) & (b.x < AOI[2]) & (b.y >= AOI[1]) & (b.y < AOI[3])
        x, y, z, c = b.x[inside], b.y[inside], b.z[inside], b.classification[inside]
        ground = c == ASPRS_GROUND
        # Printed per tile, not only summed: the palette is not guaranteed uniform across tiles
        # of one sortie, and Task 13 compares our filter against this classification.
        present = sorted(int(k) for k in np.unique(c))
        print(f"{'':22s}classes present in AOI: {present}")
        for k, n in zip(*np.unique(c, return_counts=True), strict=True):
            aoi_classes[int(k)] = aoi_classes.get(int(k), 0) + int(n)
        h = height_above_local_ground(x, y, z, ground)
        ok = np.isfinite(h)
        coarse = ((x - AOI[0]) // COARSE_BLOCK_M).astype(np.int64) * n_edges + (
            (y - AOI[1]) // COARSE_BLOCK_M
        ).astype(np.int64)
        np.add.at(total, coarse[ok], 1)
        np.add.at(above2, coarse[ok][h[ok] > 2.0], 1)
        hist += np.histogram(h[ok], bins=edges)[0]
        n_in_aoi += int(inside.sum())
        n_with_ref += int(ok.sum())
        n_ground += int(ground.sum())

    print("\n== 3. criterion 2 (canopy) over the AOI ==")
    print(f"points in AOI            {n_in_aoi:,}")
    print(f"points with a reference  {n_with_ref:,}  ({n_with_ref / n_in_aoi:.4f})")
    labels = ["<0.5 m", "0.5-1 m", "1-2 m", "2-5 m", "5-10 m", "10-20 m", ">20 m"]
    for label, n in zip(labels, hist, strict=True):
        print(f"  {label:9s}{n:>13,}  {n / n_with_ref:6.4f}")
    print(f"SHARE ABOVE 2 m          {int(hist[3:].sum()) / n_with_ref:.4f}")
    print(f"SHARE ABOVE 5 m          {int(hist[4:].sum()) / n_with_ref:.4f}")

    share = above2[total > 0] / total[total > 0]
    print(f"\n100 m blocks with data   {share.size} of {n_cols * n_edges}")
    print(
        f"  min {share.min():.3f}  p10 {np.percentile(share, 10):.3f}  "
        f"median {np.median(share):.3f}  p90 {np.percentile(share, 90):.3f}  "
        f"max {share.max():.3f}"
    )
    print(f"  blocks effectively bare (<0.05)  {int((share < 0.05).sum())}")
    print(
        f"  blocks under real canopy (>0.50) {int((share > 0.50).sum())}  "
        f"({(share > 0.50).sum() / share.size:.3f} of the AOI)"
    )

    print("\nASPRS classes over the AOI (the producer's own classification):")
    names = {
        1: "unclassified",
        2: "ground",
        3: "low vegetation",
        4: "medium vegetation",
        5: "high vegetation",
        6: "building",
        7: "low point/noise",
        9: "water",
        26: "reserved/other",
    }
    tally = sum(aoi_classes.values())
    for k in sorted(aoi_classes):
        print(
            f"  {k:>3d} {names.get(k, '?'):18s}{aoi_classes[k]:>13,}  {aoi_classes[k] / tally:6.4f}"
        )

    area = (AOI[2] - AOI[0]) * (AOI[3] - AOI[1])
    f_ground = n_ground / n_with_ref
    print(f"\nmeasured ground fraction {f_ground:.4f}  (the triage assumed 0.4)")
    print(f"ground density           {n_ground / area:.2f} pts/m2")
    print(
        f"expected void at {CELL_M} m    {expected_void_fraction(n_ground / area, CELL_M, 1.0):.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

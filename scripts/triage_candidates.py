#!/usr/bin/env python3
"""Score candidate AOIs against the pre-registered criteria, before committing to one.

Criterion 1 (DGT coverage) is the only one this script can answer, because it is the only
one that is a measurement against the live catalogue. Criteria 2-4 are answered in SITE.md
from other sources.

A search that failed is not a candidate that lacks coverage. The two are printed
differently and the exit code separates them: an incomplete table exits non-zero, because a
stopping rule allowed to fire on unmeasured candidates converts a broken instrument into a
fact about the world.

Run: PYTHONPATH=src .venv/bin/python scripts/triage_candidates.py
"""

from __future__ import annotations

import sys

from pyproj import Transformer

from microrelief.precheck import estimate_tiles
from microrelief.tiles import SelectionError, TileRef, search_tiles, select_tiles

# 2 x 2 km boxes over publicly documented terraced landscapes.
#
# The Sistelo box was corrected on 2026-08-04. The original, (-8.375, 41.930, -8.351,
# 41.948), lies about 1-3 km SOUTH of the Sistelo parish boundary and ~2.8 km from the
# village, so criterion 1 was being measured somewhere the criterion-3 evidence does not
# reach: the Portaria names the socalcos of the classified landscape, not of that box.
# The replacement is the AOI itself (see aoi/aoi.geojson), inside the classified parish.
# This moves where a criterion is measured; it does not relax the criterion.
CANDIDATES: dict[str, tuple[float, float, float, float]] = {
    "sistelo-arcos-de-valdevez": (-8.386385, 41.964324, -8.362429, 41.982200),
    "alto-douro-pinhao": (-7.550, 41.180, -7.526, 41.198),
    "coa-valley": (-7.110, 41.070, -7.086, 41.088),
    "serra-da-estrela-manteigas": (-7.545, 40.395, -7.521, 40.413),
}

CELL = 0.5
GROUND_FRACTION = 0.4  # illustrative, not measured -- see precheck.estimate_tiles
PAD = 28


def bounds_in_tile_crs(
    tiles: list[TileRef], bbox: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Project the WGS84 candidate box into the tiles' CRS, so coverage is read in metres."""
    tf = Transformer.from_crs(4326, tiles[0].crs_epsg, always_xy=True)
    minx, miny = tf.transform(bbox[0], bbox[1])
    maxx, maxy = tf.transform(bbox[2], bbox[3])
    return (minx, miny, maxx, maxy)


def report(name: str, bbox: tuple[float, float, float, float]) -> bool:
    """Print one candidate. Returns False when criterion 1 could not be measured at all."""
    try:
        tiles = search_tiles(bbox)
    except Exception as exc:  # noqa: BLE001 - triage reports, it does not decide
        print(f"{name:{PAD}} UNMEASURED  {type(exc).__name__}: {exc}")
        return False
    if not tiles:
        print(f"{name:{PAD}} NO COVERAGE -- criterion 1 fails")
        return True

    dates = sorted({t.flight_date[:10] for t in tiles})
    dens = sorted(t.density for t in tiles)
    bounds = bounds_in_tile_crs(tiles, bbox)
    est = estimate_tiles(tiles, cell=CELL, ground_fraction=GROUND_FRACTION)
    try:
        selection = select_tiles(tiles, bounds)
        coverage = f"covered={selection.covered_fraction:.3f}"
    except SelectionError as exc:
        coverage = f"SELECTION REFUSED ({exc})"

    print(
        f"{name:{PAD}} tiles={len(tiles):3d}  epsg={tiles[0].crs_epsg}  "
        f"dates={','.join(dates)}  rho={dens[0]:.1f}-{dens[-1]:.1f} pts/m2  "
        f"void@f={GROUND_FRACTION}={max(e.void_at_f for e in est):.1%}"
    )
    box = f"({bounds[0]:.0f}, {bounds[1]:.0f}, {bounds[2]:.0f}, {bounds[3]:.0f})"
    size = f"{bounds[2] - bounds[0]:.0f} x {bounds[3] - bounds[1]:.0f} m"
    print(f"{'':{PAD}} box_in_crs={box}  {size}")
    print(f"{'':{PAD}} {coverage}")
    print(f"{'':{PAD}} tile origins={sorted({(int(t.minx), int(t.miny)) for t in tiles})}")
    return True


def main() -> int:
    measured = [report(name, bbox) for name, bbox in CANDIDATES.items()]
    unmeasured = measured.count(False)
    if unmeasured:
        print(
            f"\nINCOMPLETE: {unmeasured} of {len(measured)} candidates were never reached. "
            f"This table is not a verdict on criterion 1 -- a candidate that could not be "
            f"measured is not a candidate that lacks coverage, and scoring it as a failure "
            f"would turn a broken instrument into a finding about the world."
        )
        return 2
    print(f"\nAll {len(measured)} candidates measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

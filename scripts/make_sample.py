"""Cut the shipped sample from one DGT tile.

Usage: python scripts/make_sample.py ~/data/dgt-laz/LO-179557-07-2025.laz examples/sistelo-sample

The window is 150 m × 150 m centred on the tallest verified terrace riser
(docs/riser-measurement.md). laspy's mask indexing deep-copies the header — CRS VLRs included —
and recomputes point count and extents, so the cut file declares exactly what it holds. Nothing
about the returns is altered.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import laspy
import numpy as np

WINDOW = (-20210.0, 256245.0, -20060.0, 256395.0)  # minx, miny, maxx, maxy in EPSG:3763
NAME = "sistelo-terraces-150m.laz"


def main(argv: list[str]) -> int:
    src, out_dir = Path(argv[1]), Path(argv[2])
    las = laspy.read(src)
    epsg = las.header.parse_crs().to_epsg()
    if epsg != 3763:
        print(f"refusing: {src.name} declares EPSG:{epsg}, the window is in EPSG:3763")
        return 2
    x, y = np.asarray(las.x), np.asarray(las.y)
    minx, miny, maxx, maxy = WINDOW
    keep = (x >= minx) & (x < maxx) & (y >= miny) & (y < maxy)
    cut = las[keep]
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / NAME
    cut.write(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with laspy.open(target) as f:
        h = f.header
        print(
            f"points {h.point_count}  bytes {target.stat().st_size}  epsg {h.parse_crs().to_epsg()}"
        )
        print(
            f"x {h.mins[0]:.2f}..{h.maxs[0]:.2f}  y {h.mins[1]:.2f}..{h.maxs[1]:.2f}  "
            f"z {h.mins[2]:.2f}..{h.maxs[2]:.2f}"
        )
    has_ground = bool((np.asarray(laspy.read(target).classification) == 2).any())
    print(f"class 2 present: {has_ground}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

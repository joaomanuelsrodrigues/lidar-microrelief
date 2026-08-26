"""Discriminate the read-instability candidates by backend, with the protocol fixed up front.

Observed 2026-08-05 (`docs/live-smoke.md`): of four reads of the 845 MB Sistelo dataset, two were
clean and byte-identical, one returned a single corrupted coordinate, one failed outright with
`IoError: failed to fill whole buffer`. Source files intact (`sha256sum` stable). Live candidates,
none discriminated: (H1) parallel LAZ decompression — laspy 2.7 defaults to `LazrsParallel`;
(H2) WSL2 memory pressure — `dmesg` showed `drop_caches` with a ~5 GiB working set in flight;
(H3) non-ECC memory.

Protocol, pre-registered before the first run:

- Config A: backend `LazrsParallel`, 4 tiles x 12 reps = 48 reads. Config B: same, single-thread
  `Lazrs`. Both under idle conditions (no other heavy work on the machine). Each read runs in a
  fresh subprocess, mirroring how the real runs read (one process per invocation) and surviving a
  hard crash of the decoder.
- An EVENT is: any exception, a non-zero subprocess exit, or a read whose array hash differs from
  that tile's modal hash. Two hashes per read — the raw packed point records (decompressor output,
  before scaling) and the decoded x/y/z/classification — so a corruption can be placed below or
  above the scale/offset step.
- Decision rule: A >= 2 events and B = 0 -> H1 confirmed; remedy is pinning the single-thread
  backend in `read_laz`. Events in both -> H1 refuted; re-run both configs under induced memory
  pressure to probe H2. Zero events anywhere -> run config C (parallel, under ~24 GiB of induced
  pressure) before concluding anything: the 2026-08-05 events happened under load, and "0
  events idle" must not be read as "stable" (a zero without its conditions is the instrument's
  zero, not the world's). H3 is not directly testable here; it survives only if the data kills
  H1 and H2.
- Every count is reported with its denominator. A config that did not run to completion reports
  how far it got, not a clean-looking subset.

Usage:
    driver:      python scripts/read_stability.py --tiles ~/data/dgt-laz --backend parallel \\
                     --reps 12 --out /tmp/stability_A.jsonl
    single read: python scripts/read_stability.py --one ~/data/dgt-laz/LO-179556-07-2025.laz \\
                     --backend parallel
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

BACKENDS = ("parallel", "single")


def _mem_available_kb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    except OSError:
        return None
    return None


def read_once(tile: Path, backend: str) -> dict[str, object]:
    """One read, in this process. Errors are data, not crashes: the record says what happened."""
    import laspy
    import numpy as np

    laz_backend = (
        laspy.LazBackend.LazrsParallel if backend == "parallel" else laspy.LazBackend.Lazrs
    )
    record: dict[str, object] = {"tile": tile.name, "backend": backend}
    t0 = time.monotonic()
    try:
        las = laspy.read(tile, laz_backend=laz_backend)
    except Exception as exc:
        record.update(
            ok=False,
            error_type=type(exc).__name__,
            error=str(exc),
            duration_s=round(time.monotonic() - t0, 3),
        )
        return record

    raw = hashlib.sha256(las.points.array.tobytes()).hexdigest()
    decoded = hashlib.sha256()
    for arr in (
        np.asarray(las.x, dtype=np.float64),
        np.asarray(las.y, dtype=np.float64),
        np.asarray(las.z, dtype=np.float64),
        np.asarray(las.classification, dtype=np.uint8),
    ):
        decoded.update(arr.tobytes())
    record.update(
        ok=True,
        n_points=int(las.header.point_count),
        sha256_raw_points=raw,
        sha256_decoded_xyzc=decoded.hexdigest(),
        duration_s=round(time.monotonic() - t0, 3),
    )
    return record


def drive(tiles_dir: Path, backend: str, reps: int, out: Path) -> int:
    """reps passes over all tiles, one subprocess per read, appending one JSON line per read."""
    tiles = sorted(tiles_dir.glob("*.laz"))
    if not tiles:
        print(f"no .laz files in {tiles_dir}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    n_done = 0
    with out.open("a") as fh:
        for rep in range(reps):
            for tile in tiles:
                mem_before = _mem_available_kb()
                proc = subprocess.run(
                    [sys.executable, __file__, "--one", str(tile), "--backend", backend],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    row = json.loads(proc.stdout.strip().splitlines()[-1])
                else:
                    # A crash IS an event; record what the process left behind.
                    row = {
                        "tile": tile.name,
                        "backend": backend,
                        "ok": False,
                        "error_type": f"subprocess_exit_{proc.returncode}",
                        "error": proc.stderr.strip()[-500:],
                    }
                row["rep"] = rep
                row["mem_available_kb_before"] = mem_before
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                n_done += 1
    print(f"{n_done} reads appended to {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", type=Path, default=None, help="read this tile once and print JSON")
    ap.add_argument("--backend", choices=BACKENDS, required=True)
    ap.add_argument("--tiles", type=Path, default=None)
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.one is not None:
        print(json.dumps(read_once(args.one, args.backend)))
        return 0
    if args.tiles is None or args.out is None:
        ap.error("driver mode needs --tiles and --out")
    return drive(args.tiles, args.backend, args.reps, args.out)


if __name__ == "__main__":
    raise SystemExit(main())

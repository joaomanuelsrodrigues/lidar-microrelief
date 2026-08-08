# Live smoke record

Every entry is a real command and its real output. A test that mocks the source proves wiring,
not behaviour; this file is where behaviour is claimed.

---

## 2026-08-04 — first real DGT LAZ read end to end (Task 9, the §A1 gate)

Four tiles of the chosen AOI, acquired manually (see `SITE.md`), 845,372,695 bytes total.

**Command:**

```
PYTHONPATH=src .venv/bin/python scripts/smoke_task9.py
```

**Output:**

```
== 1. read a real tile ==
file           LO-179556-07-2025.laz
points         28,339,881
bounds         [-21000.0, 255000.0, -20000.001, 255999.999]
crs            3763
density        28.34 pts/m2
classes        {1: 18897, 2: 6174892, 5: 21836480, 6: 214885, 7: 61243, 9: 30154, 26: 3330}
ground share   0.218
sha256         ebf57dae0d2a7564672866dc664346fee4b51cfc60eade990a2475bc8ebc0534

== 2. measured count vs catalogue pc:count ==
tile                       catalogue      measured   delta  bounds  date
LO-179556-07-2025         28,339,881    28,339,881       0  ok      2026-03-30T00:00:00Z
                      classes present in AOI: [1, 2, 5, 6, 7, 9, 26]
LO-179557-07-2025         27,720,324    27,720,324       0  ok      2026-03-30T00:00:00Z
                      classes present in AOI: [1, 2, 5, 6, 7, 9, 26]
LO-180556-07-2025         25,067,997    25,067,997       0  ok      2026-03-30T00:00:00Z
                      classes present in AOI: [1, 2, 3, 4, 5, 6, 7, 9, 26]
LO-180557-07-2025         28,183,801    28,183,801       0  ok      2026-03-30T00:00:00Z
                      classes present in AOI: [1, 2, 3, 4, 5, 6, 7, 9, 26]

== 3. criterion 2 (canopy) over the AOI ==
points in AOI            106,050,607
points with a reference  105,971,852  (0.9993)
  <0.5 m       3,750,062  0.0354
  0.5-1 m      3,735,433  0.0352
  1-2 m        8,927,515  0.0842
  2-5 m       27,894,801  0.2632
  5-10 m      30,248,829  0.2854
  10-20 m     26,317,116  0.2483
  >20 m        5,098,096  0.0481
SHARE ABOVE 2 m          0.8451
SHARE ABOVE 5 m          0.5819

100 m blocks with data   400 of 400
  min 0.051  p10 0.639  median 0.880  p90 0.951  max 0.980
  blocks effectively bare (<0.05)  0
  blocks under real canopy (>0.50) 381  (0.953 of the AOI)

ASPRS classes over the AOI (the producer's own classification):
    1 unclassified             85,965  0.0008
    2 ground               25,939,422  0.2446
    3 low vegetation        3,968,951  0.0374
    4 medium vegetation     8,325,620  0.0785
    5 high vegetation      66,479,926  0.6269
    6 building                918,494  0.0087
    7 low point/noise         238,191  0.0022
    9 water                    82,490  0.0008
   26 reserved/other           11,548  0.0001

measured ground fraction 0.2448  (the triage assumed 0.4)
ground density           6.62 pts/m2
expected void at 0.5 m    0.1913
```

### What the gate settles

**The reader works against real data, and nothing about it was assumed.** `read_laz` parsed
LAS 1.4 written by TerraScan, resolved EPSG:3763 from the file's own VLR rather than defaulting
to it, and returned bounds matching the catalogue's `proj:bbox` on all four tiles. The sha256 it
reports was independently recomputed with `sha256sum` before the read and agrees.

**`pc:count` is a point count — exactly, not approximately.** Delta 0 on all four tiles. The
whole pre-download triage instrument of Task 5 rests on that field meaning what it was assumed
to mean, and it does. This was the measurement most able to invalidate the work behind it.

**Criterion 2 (canopy) is CONFIRMED, and the spatial form is what confirms it.** The aggregate —
84.51% of returns above 2 m, 58.19% above 5 m — was never sufficient on its own: the doubt
recorded in `SITE.md` was that the *terraces* are open pasture inside an otherwise wooded valley,
and a high average is perfectly consistent with that. So the share is broken out over 400 blocks
of 100 m. **Not one block is bare.** The least wooded block in the entire AOI still returns 5.1%
above 2 m, the median block returns 88%, and 95.3% of the AOI is under real canopy by any
reading. There is nowhere in this AOI where terraces could be sitting under open sky, so the
piece's "see under the vegetation" argument holds here on measurement rather than on expectation.

**The pre-download triage's ground-fraction assumption was optimistic by more than a factor of
two.** `estimate_tiles` describes its `ground_fraction` as illustrative rather than measured, and
the Task 6 triage table quoted the void fraction at `f=0.4`, giving 8.2% for this candidate. The
measured fraction is **0.2448**, so the honest expectation is **19.1%** of cells with no ground
return at 0.5 m. That still clears the `max_void_fraction` bar of 0.35, so the site stands — but
the number now in `CALIBRATIONS.md` is measured rather than illustrative, and any future triage
run should be read knowing the default understates the void.

**The producer's classification palette is not uniform across one sortie.** The two western tiles
carry no class 3 or 4 at all; the two eastern ones do, and between them contribute 11.6% of AOI
returns as low and medium vegetation. Same survey, same day, adjacent tiles. Task 13 compares our
filter against this classification per class, so a class that is present in half the AOI and
absent in the other half is a property of the reference, not of the terrain — and the comparison
has to say so rather than average over it.

### One defect in the instrument, found and named

The first version of the canopy measurement seeded its per-block minimum array with `NaN`.
`np.minimum(nan, z)` is `nan`, so every block was poisoned, every height came back non-finite,
and the script reported **0 returns above 2 m** — which reads exactly like a finding that the
site is bare, and would have reversed criterion 2 on an artefact. It was caught only because the
script also printed the count of points that had a reference at all, and that count was zero.
The array is seeded with `+inf` in the version above, and the count of points with a reference
(0.9993) stays printed beside the result, because it is what distinguishes a measured zero from
an instrument that measured nothing. Same shape as the §A1 lesson of s252 and s255: silence and
absence produce identical-looking output, so the check has to report what it actually saw.

---

## 2026-08-05 — the CLI, and the first end-to-end run over the real AOI (Task 18)

Three verbs over the four Sistelo tiles, 845,372,695 bytes. `select` and `precheck` reach the
catalogue and need no credentials; `run` touches no network at all.

**Commands:**

```
microrelief select   --aoi aoi/aoi.geojson --out outputs/selection.json
microrelief precheck --aoi aoi/aoi.geojson --cell 0.5 --ground-fraction 0.4
microrelief run      --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs/ \
                     --cell 0.5 --selection outputs/selection.json
```

**Output:**

```
4 tiles, coverage 1.0000, 1 sortie(s), 1 stamp(s) -> selection.json

LO-179556-07-2025   28.3 pts/m2  2026-03-30  void(open)=0.084%  void(f=0.4)=5.9%
LO-179557-07-2025   27.7 pts/m2  2026-03-30  void(open)=0.098%  void(f=0.4)=6.3%
LO-180556-07-2025   25.1 pts/m2  2026-03-30  void(open)=0.190%  void(f=0.4)=8.2%
LO-180557-07-2025   28.2 pts/m2  2026-03-30  void(open)=0.087%  void(f=0.4)=6.0%

grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 74.6% | interpolated 25.2% | undetermined 0.2%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.999 | non-ground recall 0.495 | accuracy 0.749 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash e5e8eb9b031f950083a4ad0e0ce5b1098f6b4cbe4a620455815968f2a3f54f58
```

41.0 s wall clock, 4.8 GiB peak resident. Every number the README quotes comes from this block.

### What the run settles

**The internal falsification criterion passes.** `agreement()` names it: ground recall below ~0.70
is a defect in our filter. It is **0.999**. Accuracy **0.749** against a majority-class null of
**0.503** — the filter beats guessing by 24.6 points, and the number to read beside it is
`fp = 3,850,641`: a quarter of measured cells where we say ground and the official classification
has no ground return. That is the expected shape of a minimum-surface filter under canopy, and it
is declared rather than tuned away.

> **Correction (2026-08-06).** The `fp` above is the superseded 0.1.0 iteration's figure — the run
> before the noise-class exclusion, whose record survives in `outputs2/provenance.json` (hash
> `b152a681…`, `fp = 3,850,641`). The final record this entry's command block belongs to
> (`outputs/provenance.json`, 0.2.0, hash `e5e8eb9b…`) has **`fp = 3,889,074`** of
> `n_cells = 15,522,469` — 0.2505 of compared cells, so the sentence's argument stands; its digit
> did not. Corrected beside the original rather than edited over it.

**The catalogue's counts and ours agree exactly** on all four tiles — 28,339,881 / 27,720,324 /
25,067,997 / 28,183,801. The pair of fields is not decoration: `--selection` supplies what the
provider declared, and the record would show a disagreement if there were one.

**11,882 cells that never existed.** `aoi_bounds` reads the AOI's declared `bounds_epsg3763`
rather than re-deriving the box from its own WGS84 image. The ring round-trips up to 3.8 mm off,
`grid_for_bounds` floors and ceils, and the plan's version of this function produced a 3961 x 3962
grid at an origin half a cell away — 11,882 cells outside every tile, publishable only as
`undetermined`, under a different `reproducibility_hash`.

### Three defects the real data found, that no synthetic fixture could

**1. ASPRS class 7 spans both extremes.** Measured here: class 7 runs from **84.2 m to 1752.5 m**
while classified ground tops out at **506.1 m**, and every return above 1000 m in the delivery is
class 7. Kept, it lifted the DSM — the first run produced a CHM of **1524.55 m** — and dropped
`min_z_all` below the terrain, which is worse, because that is the surface the ground filter reads
and the DTM publishes. Excluding classes 7 and 18 moved the CHM maximum to **43.04 m** (p99 20.68 m)
and dropped 248,809 of 109,312,003 returns (0.228%), now published per tile as
`point_count_noise_excluded`. Fixtures carry no noise class, so nothing in the suite could see this.

**2. The reproducibility hash could not see a code change.** The run before the noise fix and the
run after it produced **the same hash** — `b152a681…` — over different bytes. The hash covers
package version, grid, parameters and input digests; the only thing that makes a *code* change
visible is `__version__`, and nothing enforces bumping it. The version moved to 0.2.0 (goldens
regenerated in the same commit, since the version is written into every raster's tags) and the hash
moved to `e5e8eb9b…`. The gap itself is not closed: a run whose code changed without a version bump
would still reuse a hash. It survived s259's 30-mutation exercise because `__version__` is data,
not code.

**3. Replay is not established on real data.** Of four reads of the dataset: two clean and
byte-identical across all six bands, **one that returned a single corrupted coordinate**, and **one
that failed outright** with `IoError: failed to fill whole buffer`. The corrupted read was visible
only as second-order damage — that tile's measured density collapsed toward zero because the
bounding box it divides by exploded, one return crossed the AOI boundary (`n_outside` 3,250,767 vs
3,250,766), and one cell held 32 instead of 33. The other five bands stayed byte-identical, which
is what rules out any larger corruption.

The source is intact: `sha256sum` over the tile is stable across passes, and the files sit on ext4
on the WSL2 virtual disk, not on a Windows mount. `dmesg` shows `mini_init: drop_caches` events on
a host running a ~5 GiB working set. **The root cause is not established** — parallel LAZ
decompression, WSL2 memory pressure and non-ECC memory are all live candidates and none has been
discriminated.

What did change: `read_laz` now takes the tile's declared `proj:bbox` from the selection and
refuses any return outside it. A return cannot lie outside the box the catalogue derived from the
returns, so that is a corrupted read, not terrain. **This does not make replay stable. It makes an
unstable run fail loudly instead of publishing a density divided by an exploded bounding box.**

> **Correction (2026-08-08, frozen-tree judge round 3 — E-006).** "Any return" above overstates
> the guard's scope: the footprint check runs on **retained** returns only — ASPRS noise classes
> 7 and 18 are dropped before it, by design (`read.py`: refusing a tile over a return the
> pipeline already refuses to use would turn the guard into an obstacle; what it exists to catch
> is a corrupted read of the data actually used). A corrupted coordinate on a noise return is
> therefore dropped, not detected. Corrected beside the original rather than edited over it.

> **Follow-up (2026-08-08, later the same day).** As of 0.3.0 the guard checks **all** returns,
> noise classes included, so the original "any return" sentence is now true of the shipped code
> — a corrupted coordinate is a property of the read, not of the return's class. Verified before
> widening: zero noise returns sit outside any declared box on the four real tiles, so the wider
> guard refuses nothing this delivery ships. The correction above stands as the record of what
> 0.2.0 did; the entry below records the change.

---

## 2026-08-08 — hunting the s260 read instability; the riser measurement; the 0.3.0 replay

Three measurements in one session, each pre-registered before its data was touched.

### 1. The read instability, under controlled conditions

The entry above left replay unestablished with three candidates (parallel LAZ decompression,
WSL2 memory pressure, non-ECC memory), none discriminated. The protocol — configs, event
definition (exception, non-zero exit, or an array hash differing from the tile's modal hash),
decision rule — was committed in `scripts/read_stability.py` (`050805e`) **before** the first
full run. Each read runs in a fresh subprocess and hashes both the raw packed point records and
the decoded x/y/z/classification, so a corruption could be placed below or above the scaling
step.

**Command (config A shown; B swaps the backend, C adds the hog, D adds eviction):**

```
.venv/bin/python scripts/read_stability.py --tiles ~/data/dgt-laz --backend parallel \
    --reps 12 --out .../stability_A.jsonl
```

**Results — every count with its denominator:**

| Config | Backend | Conditions | Reads | Events | Hash variants/tile |
|---|---|---|---|---|---|
| A | LazrsParallel | idle (MemAvailable 28.3–28.5 GiB) | 48 (4 tiles × 12) | **0** | 1/1/1/1 |
| B | Lazrs single-thread | idle | 48 | **0** | 1/1/1/1 |
| C | LazrsParallel | 20 GiB active anonymous set (MemAvailable 8.2–8.3 GiB) | 48 | **0** | 1/1/1/1 |
| D | LazrsParallel | 20 GiB set + per-rep page-cache eviction | 48 | **0** | 1/1/1/1 |

Durations: A min 5.6 / median 6.5 / max 7.3 s; B 15.7 / 17.8 / 18.2 (~2.7× slower); C 5.5 /
6.4 / 7.3; D 5.4 / 6.2 / 7.1. All four configs agree on both hashes for every tile.

**Two amendments, declared.** Config D was added after C completed, because C's own durations
(median 6.4 s, indistinguishable from idle) showed the tiles stayed in the page cache — C
measured reads *beside* an active working set, not reads whose pages come from disk, and both
s260 signatures (`IoError` on the read path; one garbage record) point at the I/O path. D
evicts the four files before every rep (`posix_fadvise DONTNEED`), verified by accounting
rather than by the clock: `Cached` in `/proc/meminfo` drops by the tile's ~208 MiB on evict and
returns on re-read (the virtual disk delivers 218 MB fast enough that cold and warm reads look
alike in duration). And the hog held 20 GiB rather than the planned ~24 so the reader stayed
clear of the OOM killer, whose kills would have been events of the wrong kind.

**Conclusion, per the pre-registered rule: NOT REPRODUCED.** 192 controlled reads, zero events,
byte-agreement across backends and conditions. Had the s260 rate (2 events in 16 tile-reads)
been a stationary property of this machine reading these files, 192 clean reads had probability
≈ 0.875¹⁹² ≈ 10⁻¹¹ — whatever fired on 2026-08-05 was state-dependent, not the steady process.
No code remedy is justified by this data: **no backend pin** (96 parallel reads produced
nothing, and single-thread costs 2.7×). The root cause stays open; the candidates the configs
could not exercise are that day's host state (pressure from the Windows side of WSL2, which
cannot be induced from inside), a one-off physical event (non-ECC memory), and an in-process
interaction that subprocess-per-read isolates away — the last one is probed by the double run
in §3, which reads in-process beside the held grid. The bound, not a stability claim, went into
`LIMITATIONS` and the README.

### 2. The tallest real riser — `max_elevation_m` calibrated

Method, zone, instrument parameters and verdict rule pre-registered in
`docs/riser-measurement.md` (`738fc59`) before any relief was examined; full results, the
verification table and figures live there and in `docs/figures/riser/`. Headline: 16,596
candidates over the amphitheatre zone; p50 1.67 m, p90 2.66 m; everything above 4.6 m failed
verification as terrace fabric (built walls, a churchyard wall, a gully edge, steps carried by
1–2 returns); **the tallest verified terrace riser is 2.98 m**, with a flat-tread → one-cell
drop → flat-tread profile and 43 aligned detections. The pre-registered 2.5–3.0 m band fired,
the decision went to the operator, and the ruling raised the cap to **3.5 m** — a cap 2 cm
above a riser is not above it within the 0.2–0.3 m LiDAR error band. At the shipped defaults
the cap is unreached (largest tolerance 1.65 m), so the change is byte-invisible in the
outputs; it lands in 0.3.0 with the version bump.

### 3. The 0.3.0 run, twice

Same command as the 2026-08-05 entry, run twice into separate directories under 0.3.0 (guard
widened to all returns; `max_elevation_m` 3.5; LIMITATIONS updated in the record):

```
.venv/bin/microrelief run --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs/ \
    --cell 0.5 --selection outputs_0.2.0/selection.json
```

(The 2026-08-05 run's directory was renamed to `outputs_0.2.0/` before this run so its record
survives beside the new one; `selection.json` is the file `select` wrote on 2026-08-05,
unchanged and reused — `run` needs no network. The second pass wrote `outputs_pass2/` with the
same flags.)

**Output (identical in both passes):**

```
grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 74.6% | interpolated 25.2% | undetermined 0.2%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.999 | non-ground recall 0.495 | accuracy 0.749 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash c69dd559d915c3f02d00f91bda65759c7cafce48f2a3bfd6c64c2badc0192f33
```

41.3 s wall clock, 4.4 GiB peak resident. **The two passes are byte-identical across all six
bands and the record minus `created_utc`** — the first time replay on real data has been
demonstrated twice in one session, though two clean passes are two clean passes, not a
stability proof; the 2026-08-05 events remain unexplained and declared. Against 0.2.0, the six
bands are **value-identical and byte-different**: the only byte change is the version tag, which
is the designed way a code change reaches the artefacts, and the hash moved
`e5e8eb9b… → c69dd559…` for the two declared reasons (version, and the `max_elevation_m`
parameter now 3.5).

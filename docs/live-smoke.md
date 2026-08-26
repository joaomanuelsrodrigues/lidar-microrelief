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

> **Post-judge note (2026-08-08, round 9).** The round found the shipped record still listing
> `max_elevation_m` as uncalibrated while the README called it site-calibrated — true, and the
> README was the accurate half: the cap now carries the riser measurement. The tuple in `cli.py`
> dropped the entry and the record was **regenerated by a third full run** (a run record is
> never hand-edited): bands byte-identical to both passes above, hash unchanged at `c69dd559…`
> — the uncalibrated list is hash-neutral by design, so this is the record changing its
> self-description, not the run changing. The same round caught the README quoting
> "byte-identical … and the record" without the `created_utc` qualifier this entry carries;
> both fixes were swept for siblings before the confirmation round.

41.3 s wall clock, 4.4 GiB peak resident. **The two passes are byte-identical across all six
bands and the record minus `created_utc`** — the first time replay on real data has been
demonstrated twice in one session, though two clean passes are two clean passes, not a
stability proof; the 2026-08-05 events remain unexplained and declared. Against 0.2.0, the six
bands are **value-identical and byte-different**: the only byte change is the version tag, which
is the designed way a code change reaches the artefacts, and the hash moved
`e5e8eb9b… → c69dd559…` for the two declared reasons (version, and the `max_elevation_m`
parameter now 3.5).

---

## 2026-08-10 — 0.4.0: the core decoupled from its one provider, and the re-run that had to prove nothing moved

Seven tasks (T-E6e) closed five defects the piece's own published standard already condemned:
attribution welded into the record, no check that the CRS is projected and metric, a missing
official ground class as a crash rather than a declared absence, the offline core importing an
HTTP client for one national catalogue, and `TILE_CRS_EPSG = 3763` — a Portugal fact in a general
code path. All of it rides **one** version bump, because `export.py` writes `package_version` and
`reproducibility_hash` into every raster's tags: bumping once, last, keeps the golden regeneration
to a single event and keeps the twelve goldens green through Tasks 1-6 as a free positive control
that the changes preserved behaviour.

### 1. The instrument, before the run

`scripts/compare_runs.py` compares two runs the way this change requires: **band data cell for
cell**, not file hashes — the bump changes all six files' bytes while changing nothing measured.
Three controls first, because a comparison script that always prints "identical" is worse than
none:

```
$ .venv/bin/python scripts/compare_runs.py outputs_0.3.0_run1 $MUT      # one cell mutated
expected 1: 1
  mdt.tif: 1 of 15681600 cells differ
$ .venv/bin/python scripts/compare_runs.py outputs_0.3.0_run1 outputs_pass2
expected 0: 0
$ .venv/bin/python scripts/compare_runs.py --expect-new-limitations outputs_0.3.0_run1 outputs_pass2
expected 1: 1
  provenance.known_limitations is not the old list plus the two declared gaps: expected 8 entries, got 6
```

The mutation was `mdt[1000,1000]: 446.9219970703125 -> 447.9219970703125`, and the instrument
named that cell and only it. The second and third commands are the **same inputs with the flag
flipped**, so between them they show the flag is what decides, not the data.

### 2. Hash-neutrality of the two new limitations, measured rather than argued

The two gaps Task 5 owed were added to `LIMITATIONS` **before** the bump, and the goldens run
in between:

```
$ .venv/bin/pytest tests/test_export.py::test_golden_hashes_are_unchanged -q
goldens before the bump (expect 0): 0
```

Green — `known_limitations` is in the record but not in the hash payload
(`{package_version, grid, parameters, inputs}`) and not in the raster tags. Then the bump, and:

```
golden hashes unchanged: 0   changed: 12   total: 12
```

**All twelve**, which is the confirmation that the bump alone moves every file. Had only some
failed, a band had changed and the behaviour-preservation claim would have been false. Regenerated
from the same `golden_fixtures()` / `pipeline()` path the test uses; the diff is 12 insertions and
12 deletions — hash values only, no key moved.

### 3. The run

```
.venv/bin/microrelief run --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs/ \
    --cell 0.5 --selection outputs_0.2.0/selection.json \
    --attribution "Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, licensed CC BY 4.0. Derived products (ground classification, DTM, DSM, CHM) produced by microrelief; not reviewed or endorsed by DGT."
```

(The literal attribution string was checked byte-for-byte against the provider's `DGT_ATTRIBUTION`
constant before the run, so what is published above is what a reader copying it would get. The
0.3.0 run's directory was renamed to `outputs_0.3.0_shipped/` beforehand; `selection.json` is
still the file `select` wrote on 2026-08-05, unchanged and reused — `run` needs no network. No
`--crs`: the committed AOI declares its own `bounds_epsg`.)

**Output:**

```
grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 74.6% | interpolated 25.2% | undetermined 0.2%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.999 | non-ground recall 0.495 | accuracy 0.749 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash 8e8fee5b271caedd2c006b64a8d6a195b47029240766fdced65af084aaba14a4
```

43.3 s wall clock, 4.4 GiB peak resident. Every line identical to the 0.3.0 run but the hash.
**The read instability did not fire** on this run — one clean read is one clean read, and the
2026-08-05 events stay unexplained and declared.

### 4. The acceptance check, and the baseline it caught

```
$ .venv/bin/python scripts/compare_runs.py --expect-new-limitations outputs_0.3.0_shipped outputs
basis.tif: 15681600 cells compared
chm.tif: 15681600 cells compared
mds.tif: 15681600 cells compared
mdt.tif: 15681600 cells compared
n_all.tif: 15681600 cells compared
n_ground_asprs.tif: 15681600 cells compared
6 raster(s) compared
provenance.created_utc: 2026-08-08T17:56:37.333764+00:00 -> 2026-08-10T20:44:29.521368+00:00
provenance.package_version: 0.3.0 -> 0.4.0
provenance.reproducibility_hash: c69dd559d915c3f02d00f91bda65759c7cafce48f2a3bfd6c64c2badc0192f33 -> 8e8fee5b271caedd2c006b64a8d6a195b47029240766fdced65af084aaba14a4
provenance.known_limitations: 6 -> 8 entries

identical in every band and every record field but the three permitted, and known_limitations gained exactly the two declared gaps
```

**94,089,600 cells compared, zero differ.** Run without the flag, the same comparison exits 1 and
names the two added lines, so the flag is doing work on the acceptance data too, not only on the
control pair.

**And the first attempt exited 1.** The plan named `outputs_0.3.0_run1/` as the baseline; against
it the check reported `provenance.uncalibrated_thresholds changed`. The plan's own rule is that a
difference anywhere else is a signal to investigate, never to accept, and the investigation found
the difference is in the **baseline**, not in this change: `max_elevation_m` left the uncalibrated
tuple in 0.3.0's *own* post-judge fix, and `outputs_0.3.0_run1/` (17:46) predates it, while the
shipped 0.3.0 record — `outputs/` at 17:56, hash `c69dd559…`, the one `viewer/provenance.json`
tracks and the README quoted — carries the corrected six-entry list. Verified against git rather
than chosen for passing: at `26e1323`, the commit this branch forks from, `UNCALIBRATED` already
had six entries and no `max_elevation_m`. The acceptance question is whether Tasks 1-6 changed
behaviour relative to the code the branch forked from, and only one record on disk was produced
by that code.

### 5. What the rename did not touch

`bounds_epsg3763` became the neutral pair `bounds` + `bounds_epsg` in Task 5. Two documents still
carry the old name and **keep it on purpose**: the 2026-08-05 entry above, and `docs/self-check.md`,
whose own header says the from-memory answers are checked against the record with misses *logged
rather than erased*. Both are dated records of what was true when they were written; editing them
to the new name would make them describe a package that did not exist on their date, which is the
same falsification the five judge verdicts citing `tiles.py:NNN` are left alone to avoid. The
plan's closing sweep expected zero matches across tracked files; the honest result is **two, both
dated records, named here**. `CALIBRATIONS.md` was updated instead, because a threshold register's
"where" column is a live pointer into code, not a claim about a past moment.

### 6. The judge rounds (12, 13, 14)

Same configuration as rounds 1-11: `codex exec` 0.144.1, read-only sandbox, `docs/judge/prompt.md`
on stdin, output captured to a file and read head-first.

**Round 12 FAILED** on the rubric's second clause — five questions answered, two README
contradictions reported. Verified against source before either was touched, and they did not
survive equally. One was real: `README.md:124` still said a tile carrying no class 2 "is refused
outright", the behaviour Task 3 changed to a declared absence. The same claim had *already been
corrected* eighty lines above in this session; the two sites word it differently, so a
phrase-level sweep could not see the second. The other was **re-graded rather than accepted**: the
blanket "each band is transparent exactly where it has nothing it can honestly publish" is, read
as the biconditional it is, true of `basis` — transparent nowhere, never nothing to publish — but
the enumeration after it names only three bands and invited exactly the misread a competent reader
made. Rewritten to say outright that basis is never transparent.

Both fixes were then swept for **both** failure modes before the confirmation round — the sibling
the fix missed (searched by concept across every tracked `.md`, not by phrase) and the
over-correction the fix introduced. The only surviving "refused" claims are in dated records: the
2026-08-06 judge verdict r4 and `docs/self-check.md`'s own dated correction, which the addendum
appended today explicitly supersedes.

**Rounds 13 and 14 came back clean** — zero contradictions, zero unanswerable questions. The
stopping rule was **declared before round 14 ran**: close when two consecutive rounds return zero
of both over a tree that did not change between them. The tree was fingerprinted with
`git write-tree` immediately before and after round 14 —
`1e8b839dc8193efb1c2aedba6f6cd23b83df4d5f` both times — so "unchanged" is measured, not asserted.
Two clean rounds buy coverage, not absence: E-006 puts per-round recall near 0.1 on a converged
artefact.

## 2026-08-26 — the shipped sample: 150 m around the tallest riser

A stranger's first run should not start with an 845 MB download, and no machine other than the
author's had ever run this pipeline. Both close with one file: a 150 m × 150 m cut of tile
`LO-179557-07-2025` around the tallest verified riser (−20132.8, 256319.2;
`docs/riser-measurement.md`), tracked in `examples/sistelo-sample/` beside the record and the
per-band digests of the author's run. `tests/test_sample.py` reproduces that record on every CI
run — the suite's only test on real returns, and the repository's first cross-machine replay probe.

### 1. The cut

```
$ .venv/bin/python scripts/make_sample.py ~/data/dgt-laz/LO-179557-07-2025.laz examples/sistelo-sample
points 390450  bytes 3174006  epsg 3763
x -20210.00..-20060.00  y 256245.00..256395.00  z 161.96..386.40
class 2 present: True
sha256 9d65a09170f7085263d933c1d04a08a302db274a41d89b27983500755269202b
wall 3.64s  maxrss 2454728 KB
```

Fewer points than the tile's mean predicts (27.7 pts/m² × 22,500 m² ≈ 623 k): this window runs
17.3 pts/m². The 6 MB cap has 2.8 MB of room. The header's free text, which the neutrality gate
cannot read (`grep -I` skips binaries), was printed with a positive control before the file was
staged: `system_identifier 'AL;'`, `generating_software 'TerraScan'`, VLR descriptions
`'RIEGL Extra Bytes'`, `'TerraScan Extra Bytes'`, `'http://laszip.org'`; the control — a
planted home-directory path and a planted e-mail address, assembled in the probe, not written
here — matched both; no marker in the file.

### 2. The run, twice

`$OUT` is a scratch directory outside the repository; everything else is as typed.

```
$ .venv/bin/microrelief run --aoi examples/sistelo-sample/aoi.geojson --laz examples/sistelo-sample \
    --out "$OUT/sample-run-1" --attribution "$(cat examples/sistelo-sample/attribution.txt)"
grid 300 x 300 cells of 0.5 m (0.0225 km2), 1 tile(s), 1 return(s) outside the AOI
measured 56.2% | interpolated 43.1% | undetermined 0.7%
expected void at f=1: 1.312% (measured density 17.3 pts/m2)
ground recall 0.999 | non-ground recall 0.723 | accuracy 0.837 | majority-class null 0.587
flight dates (none declared) | mixed epochs False
reproducibility_hash 9df5586d283e969fd30718760eb8c7fa7dc8e502d9746c1759dd576c0f147fe1
wall 0.78s  maxrss 171860 KB
exit=0
```

The one return outside the AOI is the single point at exactly y = 256245.000: the cut keeps
`[min, max)` on both axes, the grid runs rows downward from `origin_y = 256395` so its y-interval
is open at the bottom, and that point maps to row 300 of 300. The six returns at exactly
x = −20210.000 land in column 0 and are inside. Of the 390,450 returns, 316,927 (81 %) carry
ASPRS class 5 (high vegetation), 72,380 class 2, 736 class 6, 407 class 7 — the 407 is the
record's `point_count_noise_excluded`.

The second run printed the same six lines (`wall 0.52s  maxrss 172176 KB`, `exit=0`). The
attribution file was checked byte-for-byte against the provider's `DGT_ATTRIBUTION` constant
before the first run (`True`, 213 characters). No `--selection`, so the record declares what it
does not know: `flight_date: null`, `point_count_catalogue: null`, `flight dates (none declared)`.

### 3. Identity, and the frozen record

`jq` is not installed here; the record comparison was Python over both files with `created_utc`
popped. Then the six bands:

```
record identical minus created_utc: True
mdt byte-identical
mds byte-identical
chm byte-identical
basis byte-identical
n_all byte-identical
n_ground_asprs byte-identical
```

Frozen to `examples/sistelo-sample/expected/`: `provenance.json` from run 1, and
`bands.sha256.json` — the SHA-256 of each band's cell array (`src.read(1).tobytes()`), which is
what the test compares, not the file bytes (GeoTIFF tags carry the timestamp-free
`package_version` and hash, but a file-level digest would still be the wrong instrument for
"the same cells").

```
mdt: 8f4ff857e3d2a8bfd8c385a6fbe16530cd5e90a8862bcb33a439518327c69be1
mds: bf28b2a80e476fbddcec88bc6a986ae5b85672c14b66c3897ff97c56b5a907b2
chm: 4bbfa90b0c95821985ca60af47fcd8130b8d11c2f76a8303f43ebd434cb4ebec
basis: f19afc329de43eaa8ae1e28138f954aa39f7d55bdfa6229b0c0d7fadb10c6252
n_all: b6d411761eed0226fc3ceb52cfdf92acf5b85993fcb6efb45bceb649fc50f7a7
n_ground_asprs: dece09c098a8e733984faafc3e9527d0a4697df83b99d3cdb1ebff49ee92a9b9
```

Record: `grid {cell 0.5, crs_epsg 3763, 300 × 300, origin (−20210, 256395)}` · `honesty
{measured 0.5622, interpolated 0.4311, undetermined 0.0067, expected_void 0.0131, density 17.34}`
· `agreement {n_cells 87978, recall_ground 0.9988, recall_nonground 0.7227, accuracy 0.8367,
majority_class_null 0.5872}` · `inputs[0] {point_count_measured 390450, noise_excluded 407}`.

### 4. What the test locks, and what stays warn-class

Five tests: size ≤ cap · CRS + extents inside the window + > 100 k points · class 2 present · the
AOI declares `bounds_epsg` · a `run` over the directory reproduces `grid`, `honesty`, `agreement`,
`parameters`, `reproducibility_hash` and the input's sha256. The per-band digests are compared too,
but a mismatch **warns** rather than fails: the README's "cross-machine replay is unverified" is
still true until CI — the first non-author machine — has run this test once and its log has been
read. On the author's machine the test ran with `-W error::UserWarning` so that a warning here
would have failed it.

### 5. Added after the push — the first machine that is not the author's

Run `32994664328` on `efb5c2d` (GitHub-hosted `ubuntu-latest`, CPython 3.12.3,
`uv sync --extra dev --extra site`), read from the log, not the tick:

```
213 passed, 17 warnings in 3.66s
self-test: private path caught
self-test: e-mail caught
neutrality: scanned 106 tracked files, 0 hits
version-bump guard over HEAD~1..HEAD: 1 file(s) changed under src/, __version__ lines touched: 0
WARN: src/ changed without a __version__ bump. Two different codes would publish
the same reproducibility_hash (F-050). Bump src/microrelief/__init__.py and
pyproject.toml in the same commit as the change.
```

(The WARN is the one declared for the viewer commit below — a rendering helper changed, no band
did; the step is `continue-on-error`, so its tick is a mask and the log is what was read.)

`test_running_the_sample_reproduces_the_expected_record` passed, and the band probe did **not**
warn: the string `differs from the author's machine` occurs 0 times in the log (the two
`test_sample.py` lines in the warnings summary are NumPy's `DeprecationWarning` from
`src.read(1)`, the same 17 warnings as locally). So on this sample — 390,450 returns, a 300 × 300
grid — the record's `grid`, `honesty`, `agreement`, `parameters` and `reproducibility_hash`, the
input's sha256 and all six band arrays reproduced byte-identically on a machine that is not the
author's. One sample, one runner, one run: a first datum, not the full-AOI claim.
"Cross-machine replay is unverified" stays in the README and in the record until the probe is
promoted to an assertion citing this run.

## 2026-08-26 — the viewer moves under `docs/` for Pages, and its PNGs lose no cell

Branch-based GitHub Pages publishes `/` or `/docs`, nothing else, so `viewer/` becomes
`docs/viewer/` (`git mv`; one path in the README test, three in the README; `docs/.nojekyll` so
Pages serves the directory raw). The alternative — an Actions deploy workflow with `pages: write`
and `id-token: write` — is a new deploy handler and a new permission surface; not taken. The four
PNGs weighed 31,715,528 bytes, 17,982,028 of them the CHM.

### 1. The quantiser tried first, and what it did

The plan said `Image.quantize(256, FASTOCTREE)`: truecolour RGBA down to a 256-colour palette.
Measured against the old PNGs before being trusted:

```
mdt: OLD alpha-values [0, 255] opaque-colours 256 holes 29845 | FASTOCTREE opaque-colours 50
mds: OLD alpha-values [0, 255] opaque-colours 256 holes 159131 | FASTOCTREE opaque-colours 52
chm: OLD alpha-values [0, 255] opaque-colours 235 holes 3982774 | FASTOCTREE opaque-colours 27
basis: OLD alpha-values [255] opaque-colours 3 holes 0 | FASTOCTREE opaque-colours 1
  old colours: [(77, 175, 74, 255), (228, 26, 28, 255), (255, 127, 0, 255)]
  new colours: [(77, 175, 74, 254), (228, 26, 28, 255), (254, 127, 0, 254)]
```

The transparent-cell counts matched — the check the plan named — and the basis layer's three
colours did not survive: two came back at alpha 254, one shifted a unit in red. A legend that says
"green = measured" cannot ship a green that is 99.6 % opaque, and the terrain ramps had lost four
fifths of their colours. Dropped.

### 2. The palette is the colour set

The colormaps are 256-entry tables, so a band's opaque colours number at most 256. Sampled at 255
(`PALETTE_LEVELS`), they plus one transparent index fit a PNG palette exactly; `_save_palette`
builds the palette from the image's own colours and refuses an image that does not fit rather than
merging two colours. Four tests, one with a mutation control: with the table at 256 levels
`test_to_rgba_never_needs_more_than_255_opaque_colours` fails (`1 failed, 10 deselected`); at 255
it passes. Re-rendered from `outputs/` (the 0.4.0 run) and compared cell for cell with
`to_rgba`/`basis_rgba` in memory, hole for hole with the old PNGs at HEAD:

```
mdt: P (3960, 3960) | holes old/new 29845/29845 same-mask True | colours old/new 256/255 | lossless vs in-memory: True
mds: P (3960, 3960) | holes old/new 159131/159131 same-mask True | colours old/new 256/255 | lossless vs in-memory: True
chm: P (3960, 3960) | holes old/new 3982774/3982774 same-mask True | colours old/new 235/62 | lossless vs in-memory: True
basis: P (3960, 3960) | holes old/new 0/0 same-mask True | colours old/new 3/3 | lossless vs in-memory: True
  basis colour set old == new: True
```

### 3. The CHM against the cap

At 255 levels the CHM's palette PNG weighed 7,938,879 bytes, over the 5,000,000
`tests/test_viewer_assets.py` caps a page image at. Canopy varies cell to cell, and fewer distinct
colours compress better. Measured on the real band, exact palette each time:

```
levels 255:   7938879 bytes  colours 235
levels 128:   6368771 bytes  colours 121
levels  64:   4960664 bytes  colours  62
levels  32:   3812681 bytes  colours  32
webp lossless 255 levels: 7474512 bytes (reference only)
chm range: 0.0 43.04 m  -> m per level at 255/128/64: 0.169 0.336 0.672
```

The CHM ramp runs at 64 levels (`LAYERS` in `render.py`): 0.67 m per colour step over 0–43 m,
39 KB under the cap. The terrain ramps stay at 255. Fewer levels sampled from the colormap, never
colours merged afterwards — the lossless check in §2 is over the 64-level render. Final:
basis 1,458,725 · mdt 2,536,793 · mds 4,418,810 · chm 4,960,664 = 13,374,992 bytes, from
31,715,528.

### 4. The page, in a browser

`docs/` served on loopback (`python3 -m http.server 8765 --bind 127.0.0.1`): every asset answered
HTTP 200 at its byte size. Then headless Chromium (gstack `browse`) on `/viewer/`:

```
images: base mdt.png complete 3960x3960 | over mds.png complete 3960x3960
wipe 50 -> clip-path inset(0px 50% 0px 0px); wipe 20 -> inset(0px 80% 0px 0px)
left=chm right=basis -> over chm.png, base basis.png, both complete at 3960
attribution: "Source: Direção-Geral do Território (DGT), ... — reproducibility hash 8e8fee5b271c"
console: (no console messages)
network: 6 requests, 6 x HTTP 200
```

## 2026-08-26 — the skill file, driven by an agent host

`skills/microrelief/SKILL.md` was linked into `.claude/skills/` (untracked; removed afterwards)
and a **fresh, headless** Claude Code session (`claude -p`, model `claude-opus-5`, tools limited
to `Read`, `Skill`, `ls`, `cat` and `uv run microrelief …`) was asked, in this repository:

> build a DTM from the sample and tell me how much of it is measured

What the transcript shows, in order (6 turns, 38 s):

1. The host listed `microrelief` among its skills; the agent's first action was `Skill microrelief`
   — discovered, not named in the prompt.
2. It read `attribution.txt` and `aoi.geojson` and stated the input contract before running:
   "AOI carries `bounds_epsg: 3763` (ETRS89/PT-TM06, projected metres), attribution is verbatim
   from the sample."
3. It ran exactly the skill's worked example:

```
uv run microrelief run --aoi examples/sistelo-sample/aoi.geojson --laz examples/sistelo-sample \
    --out outputs/sample --attribution "$(cat examples/sistelo-sample/attribution.txt)"
grid 300 x 300 cells of 0.5 m (0.0225 km2), 1 tile(s), 1 return(s) outside the AOI
measured 56.2%  interpolated 43.1%  undetermined 0.7%
expected void at f=1: 1.312% (measured density 17.3 pts/m2)
ground recall 0.999  non-ground recall 0.723  accuracy 0.837  majority-class null 0.587
```

4. It read `outputs/sample/provenance.json` and reported, in the skill's order: the three basis
   fractions (56.2 / 43.1 / 0.7 %); the null beside them ("expected void is 1.3 % … the
   undetermined + interpolated share is 43.8 % — far above what point density alone predicts");
   agreement with the majority-class null in the same sentence ("accuracy 0.837 against a
   majority-class null of 0.587 … recalls: ground 0.999, non-ground 0.723"); the six
   `known_limitations` verbatim; the six `uncalibrated_thresholds` by name, and `max_elevation_m`
   as the one measured; the record hash `9df5586d283e969f…` and the input's sha256 for
   reproduction.

Nothing was guessed and no flag was invented; the `uv` build lines and the working directory
are omitted here because they name the author's machine. One host, one model, one prompt: the
door opens; how other hosts read the frontmatter is untested.

## 2026-08-26 — the six QGIS styles, loaded and rendered by QGIS itself

No QGIS on this machine, so a conda-forge QGIS **3.44.11** (Python 3.12) was created in a
scratch directory and driven headless (`QT_QPA_PLATFORM=offscreen`): for each band of the
sample's output, `QgsRasterLayer.loadNamedStyle(styles/<band>.qml)`, read back what QGIS parsed,
render the layer at native size through `QgsMapRendererSequentialJob`, and compare pixels against
the GeoTIFF's values with rasterio. Output, verbatim (the pixel lines are the three basis codes):

```
basis: loadNamedStyle ok=True renderer=paletted classes=[(0, '#e41a1c', 'undetermined'), (1, '#4daf4a', 'measured'), (2, '#ff7f00', 'interpolated')]
   code 0 at (14,0): rendered (228, 26, 28) alpha=255 want (228, 26, 28)
   code 1 at (1,0): rendered (77, 175, 74) alpha=255 want (77, 175, 74)
   code 2 at (0,0): rendered (255, 127, 0) alpha=255 want (255, 127, 0)
mdt: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=244.26 max=315.62] lowest cell -> (51, 51, 153), highest cell -> (255, 255, 255), distinct colours in render=1234, nodata alpha=0 (want 0)
mds: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=245.02 max=334.70] lowest cell -> (51, 51, 153), highest cell -> (255, 255, 255), distinct colours in render=1347, nodata alpha=0 (want 0)
chm: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=39.84] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 37), distinct colours in render=527, nodata alpha=0 (want 0)
n_all: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=24.00] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 37), distinct colours in render=25
n_ground_asprs: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=8.00] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 37), distinct colours in render=9
```

Two measurements decided the styles' shape:

- **The basis palette is what the code says.** `paletted`, three classes with the labels and
  colours of `render.BASIS_PALETTE`, and the rendered pixel at a cell of each code is that code's
  RGB exactly. The sample has no NoData cell in `basis` (0.7 % *undetermined* is a published
  state, not an absence), so transparency was checked on the float bands instead: alpha 0 at a
  NoData cell of `mdt`, `mds` and `chm`.
- **`WholeRaster` does not stretch a loaded `.qml`; `UpdatedCanvas` does.** The styles were first
  written with `<extent>WholeRaster</extent>` as the plan said: QGIS loaded them (`ok=True`) and
  rendered `mdt` (244–316 m) in **2** distinct colours — the stored 0–1 range stayed in place and
  every cell clipped to the ramp's top. `classificationMin/Max` read 0/1 before and after the
  render. QGIS recomputes a raster's range on load only for the *updated canvas* origin (the
  whole-raster figures are what the Symbology dialog writes into the style when a person clicks
  through it). With `<extent>UpdatedCanvas</extent>` and nothing else changed, the same `mdt`
  rendered in **1,234** colours, lowest cell the terrain ramp's bottom `(51, 51, 153)`, highest
  white; `mds` 1,347; `chm` 527; `n_all` 25 (one per count 0–24) and `n_ground_asprs` 9 (0–8).
  The generator and the test now say `UpdatedCanvas`, and `docs/recipes.md` says what that means
  for the user: the ramp follows the view.

One QGIS version, one platform, headless: the GUI path (Add Raster Layer → Load Style) is the
same parser and the same renderer, but it was not clicked through here. The Python process
exits with a segmentation fault in `exitQgis()` after printing — a known teardown artefact of
offscreen sessions, not a rendering failure; the PNGs and the lines above are the evidence.

## 2026-08-26 — PDAL reprojection recipe, exercised

No PDAL on this machine either, so conda-forge **PDAL 2.10.2** was installed in the same scratch
environment. The recipe in `docs/recipes.md` was run on the shipped sample: reproject
EPSG:3763 → EPSG:25829 (ETRS89 / UTM 29N), write LAS 1.4 point format 8 with laszip, then
`microrelief run` on the result with an AOI transformed the same way.

```
pdal 2.10.2 (git-version: da2cd8)
pdal pipeline reproject.json
(pdal pipeline readers.las Warning) Found 3 extra byte VLRs. Concatanating all extra byte records into one.
exit=0

pdal info --metadata sample-utm29.laz
srs.horizontal: PROJCS["ETRS89 / UTM zone 29N",GEOGCS["ETRS89",DATUM["European_Terrestrial_Reference_Syste
compressed: True minor_version: 4 dataformat_id: 8 count: 390450
minx,miny,maxx,maxy: 551618.18 4647239.7 551769.58 4647391.1

laspy: epsg 25829, points 390450, version 1.4, point format 8

AOI (four corners through pyproj, then their bounding box):
bounds 25829: [551618.162, 4647239.662, 551769.616, 4647391.116] size: 151.45 x 151.45 m

microrelief run --aoi aoi-utm29.geojson --laz laz-utm29/ --out out-utm29/ --attribution "..."
grid 304 x 304 cells of 0.5 m (0.0231 km2), 1 tile(s), 0 return(s) outside the AOI
measured 55.3% | interpolated 44.0% | undetermined 0.7%
expected void at f=1: 1.469% (measured density 16.9 pts/m2)
ground recall 0.999 | non-ground recall 0.720 | accuracy 0.836 | majority-class null 0.586
flight dates (none declared) | mixed epochs False
reproducibility_hash 91fea28a72637f53123e6f81ae29418ab50ebd3734ad78aa3de03b5782085d6b
exit=0
```

What this shows: PDAL writes a CRS that laspy resolves to the EPSG code `run` requires, the
390,450 returns and their classification survive the round trip, and `run` accepts the file
without a flag. The numbers are close to the EPSG:3763 record and not equal to it — the
reprojected box is 151.45 m on a side rather than 150 because a rotated square's bounding box is
larger, the grid is 304 × 304 instead of 300 × 300, and the extra 2 % of area has no returns, so
the measured density reads 16.9 pts/m² against 17.3 and the measured share 55.3 % against
56.2 %. Same terrain, a different lattice, a different hash: what the recipe says to expect.
PDAL's warning about three extra-byte VLRs (RIEGL and TerraScan extras) is about dimensions
`microrelief` never reads. The `filters.crop` stage of the recipe was not needed here (the
sample is already cut) and was not exercised.

### Addendum — after the pre-merge review (same day)

An adversarial review of the branch (high effort, 17 candidates: 15 confirmed, 2 plausible,
0 refuted) touched the styles and the gate; both were re-exercised.

**Styles.** The generator rounded channels where `render.to_rgba` truncates, which put 5 of the 9
terrain stops one unit off the viewer's colours; it now truncates, and every stop equals the named
colormap's own value (0 of 27 stops differ). The viewer PNG additionally quantises to 255 levels
(64 for the CHM), so a viewer pixel can sit up to 3 (terrain) or 8 (viridis at 64) units per
channel from a stop — measured, and written into the generator rather than claimed away. QGIS
3.44.11 on the regenerated files, same harness as above:

```
basis: loadNamedStyle ok=True renderer=paletted classes=[(0, '#e41a1c', 'undetermined'), (1, '#4daf4a', 'measured'), (2, '#ff7f00', 'interpolated')]
   code 0 at (14,0): rendered (228, 26, 28) alpha=255 want (228, 26, 28)
   code 1 at (1,0): rendered (77, 175, 74) alpha=255 want (77, 175, 74)
   code 2 at (0,0): rendered (255, 127, 0) alpha=255 want (255, 127, 0)
mdt: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=244.26 max=315.62] lowest cell -> (51, 51, 153), highest cell -> (255, 255, 255), distinct colours in render=1228, nodata alpha=0 (want 0)
mds: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=245.02 max=334.70] lowest cell -> (51, 51, 153), highest cell -> (255, 255, 255), distinct colours in render=1347, nodata alpha=0 (want 0)
chm: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=39.84] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 36), distinct colours in render=532, nodata alpha=0 (want 0)
n_all: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=24.00] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 36), distinct colours in render=25
n_ground_asprs: loadNamedStyle ok=True renderer=singlebandpseudocolor before-render min=0 max=1 | after-render min=0.00 max=1.00 raster[min=0.00 max=8.00] lowest cell -> (68, 1, 84), highest cell -> (253, 231, 36), distinct colours in render=9
```

**Gate.** Three defects in `scripts/neutrality.sh`, each with a control that now fails without
the fix: (1) it was cwd-scoped — from `docs/` it printed `scanned 32 tracked files, 0 hits`, exit
0, over a quarter of the tree; it now `cd`s to the repository root, and the test runs it from
`docs/` and requires the full denominator. (2) The denominator counted tracked files, but `grep -I`
reads no binary and nothing from an empty file — 13 of 121 (10 PNG/LAZ, 3 empty `__init__.py`)
were reported as scanned and never read; the summary now says `scanned 108 text files of 121
tracked (13 binary or empty skipped)`. (3) The `.env*` check I had added in the morning read the
working directory with a glob that also matched `.envrc` (direnv), and the version written to fix
that — `ls .env .env.*` — exited non-zero whenever `.env` alone was absent, so a planted
`.env.local` **passed**: the s271 `ls a b` shape, caught by the positive control before commit.
Now: tracked `.env` / `.env.<x>` fail by pattern, a working-tree `.env` / `.env.<x>` fails by a
loop, `.envrc` passes, and the self-test checks the pattern both ways.

```
self-test: private path caught
self-test: e-mail caught
self-test: .env pattern matches .env.local, not .envrc
.env file present in the working tree: .env.local      → exit 1 (planted)
with .envrc                                             → exit 0
neutrality: scanned 108 text files of 121 tracked (13 binary or empty skipped), 0 hits  (root, and from docs/)
```

**Gate, round two.** A second review over the fix found the `.env` checks root-only (a
`sub/.env`, tracked or not, passed), the denominator's test deriving its expectation with the
script's own pipeline (a control agreeing with itself), and a tracked file deleted from the
working tree counted as read. Now: the `.env` pattern matches a path segment at any depth over
`git ls-files`, the working tree is walked with `find` (skipping `.git` and `.venv`), a
tracked-but-missing file refuses the scan before any count (without that, `xargs` returned
**123** and the summary never printed — the same silent-instrument shape as the count itself),
and the test derives the skipped set independently (size 0 or a NUL byte: the same 13 files).
The planted-file controls live in the suite, on a throwaway git repository:

```
clean scratch repo                         → exit 0
+ .envrc                                   → exit 0
+ .env.local (untracked)                   → exit 1  ".env file present in the working tree: ./.env.local"
+ sub/.env (untracked)                     → exit 1  "./sub/.env"
+ sub/.env force-added to the index        → exit 1  "tracked .env file:"
tracked clean.md deleted from the tree     → exit 1  "tracked but missing from the working tree (not scanned): clean.md"
```

**Gate, round three (2026-08-27).** The third review round was cut short by a session limit
(one of eight angles reported: reuse — no correctness finding; the `.env` rule was encoded twice,
regex and `find` globs, and they disagreed on a trailing-dot name; now one pattern drives both).
One question its dead sibling had raised was measured instead of argued: **a private path inside a
file `grep -I` calls binary is invisible by design** — a path planted in a PNG text chunk was not
found (`grep -I` → not found; `grep -a` → found). Over every byte of every tracked file, `grep -a`
found the private-path pattern **0** times in 0.06 s; the e-mail pattern fired **once**, inside a
PNG's compressed bytes (`docs/figures/riser/f01-terrace-2.98m.png:1389`) — a coincidence of
random bytes, so that scan stays on text files. The summary now names both scopes:

```
self-test: private path caught
self-test: private path behind a NUL byte caught
self-test: e-mail caught
self-test: .env pattern matches .env.local and sub/dir/.env, not .envrc
neutrality: scanned 122 tracked files for private paths (all bytes), 109 text files for e-mails (13 binary or empty skipped), 0 hits
```

A planted path inside a binary file in a scratch repository is a test now
(`test_a_private_path_inside_a_binary_file_is_caught`). `LC_ALL=C` is exported by the script so
what counts as binary no longer depends on the machine's locale.

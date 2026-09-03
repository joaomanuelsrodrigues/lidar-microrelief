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

> *Annotation, 2026-08-29:* this script is now `scripts/smoke_dgt_e2e.py`. The command is
> left as it was run, because this is a record of what happened, not instructions to follow.

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

**Gate, round three — the fixes, and what the probes showed first.** The re-run of the third
review found eight more, each measured on a scratch repository; my own probes on the script as
it stood, before touching it:

```
text-only repo                 → summary printed, exit 0
binary-only repo               → exit 123, no summary        (grep -IL under pipefail)
tracked dangling symlink       → "grep: d: No such file or directory", exit 123, no summary
newline-only file, as the only
  text file                    → exit 123, no summary        (no character matches `.`)
```

Now: the population is enumerated once, NUL-separated, into a temp file (a bash variable cannot
hold NULs — the first draft captured them and every path ran into the next); a tracked path that
is not a readable file refuses the scan before any count; skipped files are counted by an explicit
criterion (empty, or a NUL byte anywhere — the test derives the same one independently; a
newline-only file is text); the tracked-`.env` check captures instead of `grep -q` (SIGPIPE 141
under `pipefail` on a large index); the all-bytes scan prints only the match; the walk includes
symlinks and prunes virtualenvs found by their `pyvenv.cfg`. Two of those fixes failed their own
control on the first draft — the NUL count captured a NUL, and an empty virtualenv list became an
empty `-f` pattern that matches every line — and were corrected before commit. After the fix,
this tree:

```
neutrality: scanned 122 tracked files for private paths (all bytes), 109 text files for e-mails (13 binary or empty skipped), 0 hits
```

**Gate, round four (2026-08-27) — the instrument changed.** The fourth review round found sixteen
more, again on the working-tree scan: a `pyvenv.cfg` at the repository root turned the prune
prefix into `./` and the `.env` walk went blind with a green summary; a tracked **symlink was
scanned by its target's bytes** while the blob git publishes is the link text (`ln -s
/home/<user>/… lnk` → `0 hits`, exit 0); a path named `-n` vanished in an `echo` and the missing
file was reported as scanned (`dce2132`'s body says the refusal "fired with an empty list" — it
did not fire; the gate went green); the block parser swallowed a step's sibling keys. Four
versions of "scan the working tree with `grep`" had each closed one hole and opened the next, so
the population moved to the **index, read through git**: `git grep --cached` over the blobs
(`-a` for private paths in every byte, `-I` for e-mails in text blobs — git's own rule, a NUL in
the first 8000 bytes, applied by the same command to the scan and to the count), `git cat-file`
for each symlink's link text, `git ls-files -s` for modes (submodules counted as not scanned),
and `git ls-files -o -i --exclude-standard --directory` for the working-tree `.env` check, where
an ignored directory collapses to one entry and no marker heuristic exists. Nothing reads the
checkout, nothing spawns a shell per file, no `find`. The self-test builds a temporary
repository with one violation of each class and requires each verdict; thirteen scratch-repo
tests in the suite plant the round's cases. Three drafts of this version failed their own
controls before commit — a `-z` NUL delimiter dropped by the capture, `if check` consuming the
failing status (a planted leak printed and exited 0), and a binary-only index making
`git grep -l` exit 1 under `pipefail` — the same three shapes as the night's earlier fixes, on
new lines. Measured on the tree, 0.12 s:

```
self-test: private path behind a NUL byte caught; e-mail caught; symlink target caught; .env.local caught; .venv/ contents ignored; clean repo silent; .env pattern matches .env.local and sub/dir/.env, not .envrc
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails over 109 text (13 binary or empty); 0 hits
```

**Gate, round five (2026-08-27) — the redesign's own holes, and the exit contract made real.** Two
review angles survived a session limit and measured, on the index-based version: an `exit 2`
inside `$(...)` ended only the subshell, so a broken `git grep` (a bogus `grep.patternType`, a
corrupt object) produced a **green summary, exit 0**; `2>&1` folded git's warnings into the hit
list; `git grep -I` obeys `.gitattributes`, so a tracked `*.md -diff` moved a planted e-mail out
of the scanned population (`0 hits`, exit 0); the self-test's `git init` inherited
`GIT_INDEX_FILE` from a pre-commit hook and staged its scratch blobs into the caller's index; the
working-tree `.env` check was red on a sanctioned local `.env`, blind under any ignored directory,
and answered a machine question inside a publication gate. Now: every scan is a statement into a
temporary file and the caller reads its status — 0 clean, 1 hit, **2 instrument failure with no
summary** (the self-test provokes one and requires exactly that); stdout and stderr are kept
apart, a git warning is printed as an instrument note; the text/binary rule (non-empty, no NUL in
the first 8000 bytes) is computed by the script over `git cat-file`, so no attribute can move a
blob — e-mails are searched in every byte and a hit inside a binary blob is **counted, not
judged** (the summary now says `e-mail-shaped bytes in 1 of them not judged`: the PNG coincidence
measured earlier, visible instead of silent); the self-test and the pytest scratch repositories
run under `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` with every `GIT_*` variable unset;
the working-tree `.env` check is gone (the tracked one stays: `.gitignore`'s `.env*` is where a
local one is provisioned to live), and `AGENTS.md` rule 5 says "tracked". The CI-mirror test
parses `ci.yml` with PyYAML (dev extra) after three hand-rolled line readers each missed a form
the next review found. On this tree, 0.7 s:

```
self-test: private path behind a NUL byte caught
self-test: e-mail caught despite .gitattributes
self-test: symlink target caught
self-test: tracked .env at depth caught
self-test: e-mail-shaped bytes in a binary blob counted, not judged
self-test: clean repo silent
self-test: broken instrument exits 2 with no summary
self-test: .env pattern matches .env.local and sub/dir/.env, not .envrc
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 hits
```

**Gate, round six (2026-08-27).** Three confirmed by execution: a hit's path recovered from
`:`-delimited text never matched the binary list when git C-quoted it (`é/blob.bin`) or when it
held `:<digit>` — a binary blob judged as text, and the verdict flipped with the user's
`core.quotePath`; `git ls-files`' status was discarded in a process substitution, and
`GIT_INDEX_FILE=/nonexistent` printed a green summary over **zero** blobs; the git-warning test
could not fail because nothing made git speak. Now: `git grep -z` records (`path\0line\0match`)
read field by field, so no path is ever quoted or split; the index is read as a statement and an
empty or unopenable one is exit 2 with no summary; classification is two git processes
(`cat-file --batch-check` for sizes, `grep -P '\x00' -l` for NUL-bearing blobs; the rule is
"non-empty, no NUL anywhere", the same one the tests derive, which also count the e-mail-shaped
binary blobs instead of typing the number); `--no-recurse-submodules` pinned beside
`--no-column --no-color`; `GIT_TRACE=1` makes the warning control speak. 0.24 s on the tree:

```
self-test: … e-mail-shaped bytes in two binary blobs (one under a non-ASCII path) counted, not judged
self-test: clean repo silent
self-test: broken instrument exits 2 with no summary
self-test: empty population exits 2 with no summary
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 hits
```

**Gate, round seven (2026-08-27).** Three confirmed by execution, all in the joins: a per-path
`grep -zqxF` read a path holding a newline as a pattern *list*, so a real e-mail in such a file
matched neither the text nor the binary list and vanished with a green summary; the binary-blob
count was a count of matches (`2 of them` for one blob with two runs) while the test counts
blobs; the NUL scan lacked `--no-color`, so `color.grep=always` wrapped every name in ANSI
escapes, no binary blob matched, and the tree's one PNG became a false red. Now: every join is
an exact-key lookup in a bash associative array (a path is any bytes but NUL; no process per
path), the count is of distinct blobs, every `git grep` shares one pinned option list, sizes are
validated (`<sha> missing` from `cat-file --batch-check` is exit 2, not a size of zero), each
git call's stderr is echoed as a note, and the tracked-`.env` test is bash's own `=~` over the
record's path. 0.11 s on the tree; the self-test plants a newline path and a two-run blob:

```
self-test: e-mail in a path holding a newline caught
self-test: e-mail-shaped bytes in three binary blobs (one under a non-ASCII path, one with two runs) counted as blobs, not judged
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 hits
```

**Gate, round eight (2026-08-27).** Ten findings, seven of them correctness by measurement or mutation, one conventions by mutation (three guards without a test that fails when they are deleted: the sizes-count guard, the unlisted-path guard, and the `note_err` calls), two cleanups: the self-test's `( check )
|| true` swallowed `fail_instrument`'s exit inside a subshell, so under a broken `git grep` the
empty verdict file — the pass condition — printed "clean repo silent" (the subshell existed only
because `check` never reset its state); `[[ =~ ]]` is string-anchored where `.gitignore`'s
`.env*` is not, so a force-added `.env` name carrying a newline byte passed; my `expect` helper
was `grep -F` with a two-line expectation — a pattern list, the round-7 defect in the control
written for it; unmerged index entries were counted but never visited by `git grep --cached`;
the per-symlink `cat-file` was the one git call whose stderr was dropped; three guards had no
test that fails when they are deleted. Now: one `run_git` wrapper owns status, output and the
note for every git call; `check` resets its state and runs in-process (the self-test under a
broken instrument exits 2 and never prints "clean repo silent"); the `.env` name test is one
function applied to every line of a path, shared by production and self-test, with newline
cases; unmerged entries are exit 2; the planted binary set is an array and its count is
compared to the array's length; a `git` shim in the suite drops a size line and appends an
unlisted record, and `GIT_TRACE=1` with a symlink planted requires a note for every kind of git
call, so all three guards have tests that fail without them. 0.16 s on the tree:

```
self-test: e-mail-shaped bytes in binary blobs counted as blobs, not judged
self-test: clean repo silent
self-test: broken instrument exits 2 with no summary
self-test: empty population exits 2 with no summary
self-test: .env name test (the gate's own) matches .env.local, sub/dir/.env and names carrying a newline, not .envrc
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 hits
```


**Gate, round nine (2026-08-27).** Ten reported (13 confirmed, 4 plausible, 3 refuted of 20
distinct); the three that matter for a flip, all executed: the `.env` regex was **narrower than
the repository's own `.env*` ignore rule** — `.env-prod`, `.env_local`, `.environment`,
`.env `, `.env/secret` are ignored by git and passed the gate while its header claimed parity;
the self-test ran `check` under `|| true`, i.e. with errexit off, a different failure regime from
production, where a bare failing command exited **1 — the hit code — with nothing printed**
(by mutation); the self-test's "trailing newline" name was `$(printf 'sub/.env\n')`, which is
byte-identical to `sub/.env` because command substitution strips the newline. Now: the secrets
rule is git's own evaluation of the tracked `.gitignore` (`git ls-files -c -i
--exclude-per-directory=.gitignore` — exactly the force-added set, NUL-delimited, no regex; 0 on
this tree), after a precondition that `.gitignore` excludes `.env` and `.env.local` at all (a
repository without the rule is exit 2); `set -E` + an ERR trap make any unguarded failure exit 2
with the line, in production and in the self-test alike, which now runs `check` bare; the planted
name is `$'sub/.env\n'` and it is caught; a symlink target is rendered through `tr`, not `$(cat)`
(a NUL would have been dropped with a bash warning); the unmerged list names a path once, `%q`;
`rev-parse` goes through `run_git` like every other call; `scan_pattern` is back; the shim uses
`sed '$d'`. 0.12 s on the tree:

```
self-test: tracked file the repository's .gitignore excludes caught: sub/.env
self-test: tracked file the repository's .gitignore excludes caught: .env-prod
self-test: tracked file the repository's .gitignore excludes caught: .env/secret
self-test: tracked file the repository's .gitignore excludes caught: $'sub/.env\n'
self-test: a .gitignore without .env* is an instrument failure, exit 2 with no summary
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 tracked files the .gitignore excludes; 0 hits
```


**Gate, round ten (2026-08-27) — the last under the declared bound.** Ten confirmed (six
executed, four by mutation), all in the round-nine rule: the precondition (`git check-ignore`)
read every exclude source while the scan read only `.gitignore`, so a machine's global `.env*`
satisfied one and not the other; both read the **working-tree** `.gitignore`, so an unstaged
edit or an untracked nested file flipped the verdict; a failing member of an `&&` list escapes
the ERR trap, so a failed `mkdir` would have run the self-test inside the caller's repository;
the newline-name control was substring containment satisfied by a neighbouring record; the
symlink-target rendering and the unmerged dedup had no failing test (the dedup assertion written
in round nine had never been applied — the edit missed its formatter-wrapped target); the record
said `sed '$d'` while the shim still said `head -n -1` (same cause). Now: one source for
precondition and scan — the **staged** root `.gitignore` (`git show :.gitignore`, then
`ls-files -c -i --exclude-from=<that copy>`), the literal line `.env*` required, negations
honoured by design, nested files not consulted, checked before any scan prints; the ignored list
is `%q`-rendered, one line per path; the self-test's setup is one guarded statement per line with
a `$PWD` check; tests plant a symlink whose target holds a NUL, an unstaged rule, a global-excludes
rule, a `!` negation, and require a note for all eight kinds of git call; the shim really uses
`sed '$d'`. 0.14 s on the tree:

```
self-test: tracked file the staged .gitignore excludes caught: $'sub/.env\n'
self-test: a staged .gitignore without .env* is an instrument failure, exit 2 with no summary
self-test: the rule counts only in the staged .gitignore, not the working-tree file
neutrality: 122 tracked (122 regular, 0 symlink, 0 submodule not scanned); private paths over all bytes of 122; e-mails judged in 109 text (13 binary or empty, e-mail-shaped bytes in 1 of them not judged); 0 tracked files the staged .gitignore excludes; 0 hits
```
## 2026-08-30 — 0.4.1: two declared limitations, one silent success closed, and the re-run that had to prove nothing moved

Four pre-flip fixes from the s291 readiness audit (F3–F6), and the acceptance run that shows none
of them touched a measurement.

### 1. The silent success (F6)

`cli.py` had no `if __name__ == "__main__":` guard, so the documented module form did nothing and
said nothing:

```
$ .venv/bin/python -m microrelief.cli run --help
$ echo "exit=$?  bytes=$(.venv/bin/python -m microrelief.cli run --help | wc -c)"
exit=0  bytes=0
```

Exit 0, zero bytes on stdout and stderr — indistinguishable in any exit-code check from a real
run. The console script spoke normally on the same arguments, which is what made the module form
the *only* broken door and kept a 252-test suite green over it. Closed by the guard, and asserted
by an **artefact**: `tests/test_packaging.py::test_the_module_entry_point_actually_runs_the_cli`
runs the shipped sample through `python -m` and requires `provenance.json` to exist and to carry
`__version__`. Written first, and failing before the fix with
`rc=0, stdout='', stderr=''` in its own message.

### 2. Two limitations declared (F4, F5)

Neither is new behaviour; both were true and unwritten.

- **F5** — the reproducibility hash does not cover `--attribution`. Two runs differing only in
  that string share a hash.
- **F4** — the only resource ceiling is a cell count (200,000,000), and the per-cell arrays cost
  60 B/cell measured (40 B in the accumulator's five float64/int64 arrays, 20 B in `CellStats`'s
  five float32/int32 ones), so the ceiling is ~12 GB before the ground filter, the two distance
  transforms and the surfaces. `grid_for_bounds`'s refusal now states the byte cost; it still
  does not bound it, and `--cell 0.1` over 1 km² still passes the guard.

`known_limitations` goes 8 → 10, the README's *What this does not support* 9 → 11.

### 3. A private reporting channel (F3)

`SECURITY.md`, naming GitHub private vulnerability reporting as the only channel, and stating the
threat model that actually exists: a LAS/LAZ file is untrusted input parsed by `laspy` before any
of this package's refusals run, and `select`/`precheck` make one outbound request each while
`run` makes none.

### 4. The version bump, and why

`package_version` is inside the reproducibility hash and is the only way a code change reaches
it. 0.4.0 had never left this machine, but `docs/viewer/provenance.json` and the records quoted
above ship *inside* the repository — so leaving the version alone would have published two
different codes under one hash. 0.4.0 → 0.4.1 in `__init__.py`, `pyproject.toml`, `CITATION.cff`
and the skill's frontmatter.

### 5. The sample re-run

```
$ .venv/bin/microrelief run --aoi examples/sistelo-sample/aoi.geojson \
    --laz examples/sistelo-sample --out <tmp> \
    --attribution "$(cat examples/sistelo-sample/attribution.txt)"
grid 300 x 300 cells of 0.5 m (0.0225 km2), 1 tile(s), 1 return(s) outside the AOI
measured 56.2% | interpolated 43.1% | undetermined 0.7%
expected void at f=1: 1.312% (measured density 17.3 pts/m2)
ground recall 0.999 | non-ground recall 0.723 | accuracy 0.837 | majority-class null 0.587
flight dates (none declared) | mixed epochs False
reproducibility_hash 4060d5341498556dbd48e18eb34fb118f5f4ee62a979ccc94372208d5ec70e0b
```

Every line but the hash is identical to 0.4.0's. **The control that says the bump changed
metadata and not data**: the six bands' *pixel* digests (`expected/bands.sha256.json`, which
hashes `src.read(1)`, not the file) are **6 of 6 unchanged**, while all 12 golden fixture hashes —
which hash whole TIFF *files*, tags included — changed. Metadata-wide, pixel-nowhere, which is
what a version bump is supposed to be.

The noise share on this sample is **0.104%** (407 excluded against 390,450 kept), against
**0.228%** over the full AOI — the two populations the README labels separately.

### 6. The full-AOI re-run and the acceptance check

```
$ /usr/bin/time -f "%e s wall, %M kB peak RSS" .venv/bin/microrelief run \
    --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs_0.4.1b/ --cell 0.5 \
    --selection outputs_0.2.0/selection.json --attribution "Source: Direção-Geral do Território (DGT), ..."
grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 74.6% | interpolated 25.2% | undetermined 0.2%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.999 | non-ground recall 0.495 | accuracy 0.749 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash 7b78c489df896702d812fd8401ad31b4f6ca604aaee8699b06d1dec0ff853711
28.51 s wall, 4613272 kB peak RSS
```

Same selection file as every run since 2026-08-05, reused unchanged — `run` needs no network.

```
$ .venv/bin/python scripts/compare_runs.py --expect-new-limitations outputs outputs_0.4.1b
...
6 raster(s) compared
provenance.created_utc: 2026-08-10T20:44:29.521368+00:00 -> 2026-08-30T09:57:40.796776+00:00
provenance.package_version: 0.4.0 -> 0.4.1
provenance.reproducibility_hash: 8e8fee5b271c... -> 7b78c489df89...
provenance.known_limitations: 8 -> 10 entries

identical in every band and every record field but the three permitted, and known_limitations
gained exactly the two declared gaps
```

**Run in three arms, because a pass means nothing without the failures beside it:**

| arm | exit | what it proves |
|---|---|---|
| flag, then `outputs outputs_0.4.1b` | **0** | the acceptance |
| no flag | 1 | the limitation assertion is live, not dormant |
| flag, with the pair **reversed** | 1 | the release is read from the record and is load-bearing |

The reversed arm is what replaced naming a release on the command line: with the pair the other
way round the new run is the 0.4.0 record, so the instrument expects 0.4.0's additions on top of
0.4.1's list and refuses -- `expected 12 entries, got 8`. All three re-run 2026-08-31 against the
same two directories.

The instrument itself moved: it no longer hardcodes 0.4.0's pair. Each release keeps its own
written-out pair rather than importing `cli.LIMITATIONS` — importing would make the instrument
agree with whatever the code says — and **which pair to expect is read from the NEW run's own
`package_version`**, so `--expect-new-limitations` stays a bare `store_true` flag and both
acceptance commands recorded above replay unchanged.

> **Corrected s293, and the correction is the finding.** The first version of this change made
> the flag take an optional value (`nargs="?"` with `choices=`). That is broken in exactly the
> position both records use it — **before** the two positionals — because argparse offers the
> next positional as the option's value: `compare_runs.py --expect-new-limitations
> outputs_0.3.0_shipped outputs` died at **exit 2**, `invalid choice: 'outputs_0.3.0_shipped'`.
> The sentence claiming it "replays unchanged" was published here, in the module comment and in
> the flag's own help text **without ever being run** — the three arms I did run all passed the
> value explicitly, which is the one form the records never use. Dropping `choices` was not
> enough either (measured: still exit 2, "the following arguments are required"); the fix is to
> take the release from the record. `tests/test_compare_runs.py` now exercises the flag in the
> recorded position, and a mutation restoring `nargs="?"` turns it red.

> **Corrected 2026-08-31 (s295), and the correction is the same finding a third time.** The fix
> above reverted the flag to a bare `store_true` -- and the command block, the three-arm table
> and the success line **directly above this note** were left in the pre-fix shape: a release
> name written where the flag takes no value. Measured: that argv exits **2**,
> `unrecognized arguments`. So the note explaining the defect sat one line below a live instance
> of it, and two of the three arms in the table could not run at all -- the third had become
> impossible by construction, since the release now comes from the record and no command line
> can ask for another one. The success line was hand-edited too: the program prints *the two
> declared gaps*, not the wording published here.
>
> Fixing the three sites would have left the class open, so the instrument changed instead:
> `compare_runs.build_parser()` is now exposed, and `tests/test_compare_runs.py` parses **every**
> command any tracked document records (5 found, 1 rejected before this fix) and refuses a
> release name after the flag anywhere in prose or a table (3 sites found). Both sweeps carry a
> must-fire and a must-not-fire arm, and every planted string is assembled at run time -- written
> out whole it would make the guard fire on its own source. The commands above were then re-run
> and are transcribed from that run, which is what this file was supposed to mean all along.

### 7. What a review pass found afterwards, and what the local gates had not

Two of the six findings were the kind only a different instrument sees.

**`uv.lock` was never regenerated for 0.4.1**, so `uv lock --check` reported drift and CI's
**first** step — `uv sync --locked` — would have refused, making every later gate unreachable.
Every gate above had been run locally *without* that step, so the whole set was green over a
build CI cannot produce. `AGENTS.md` states this exact failure mode, and
`test_the_human_facing_version_copies_agree_with_the_package` enumerated the version's copies as
`CITATION.cff` + `SKILL.md` — not the one CI actually gates on. `uv.lock` is now in that
enumeration, and a mutation setting it back to 0.4.0 turns the test red.

**`CITATION.cff` claimed 0.4.1 was released on `2026-08-11`** — not even 0.4.0's tag date
(`2026-08-27`). The version test compared only the version string. Now `2026-08-30`.

Also from the same pass, all measured and fixed: `CALIBRATIONS.md`'s `max_cells` row still
justified the ceiling as "one float64 array … ~1.6 GB" while this very release published 60 B/cell
(ten arrays, ~12 GB) everywhere else; the 60 B/cell figure and the ceiling literal shipped in three
unlocked copies with **no test tying them together** — now measured from the objects themselves in
`tests/test_accumulate.py`, with three mutations each turning exactly one assertion red; and the
`__main__` guard closed `python -m microrelief.cli`, a spelling no document uses, while `python -m
microrelief` — the form a reader without the console script reaches for — still failed for want of
a `__main__.py`. Both module forms are now parametrised in the same test and documented in the
README.

`__main__.py` also arrived unclassified into `tests/test_layering.py`'s partition, which failed
on it immediately. It belongs with the composition root, not core: it holds no logic and imports
`cli.main`, so calling it core would put a module that imports the composition root inside the
layer defined by not knowing about it. That contract is the reason the classification happened at
all rather than the file simply landing.

**And the review's own prescribed fix did not work.** It diagnosed the argparse mechanism
correctly and said to drop `choices`; running that still exited 2, because `nargs="?"` alone eats
the positional. Only executing it showed that.

**And the instrument earned its keep on the first run:** the two new limitations were first
inserted in the middle of `LIMITATIONS`, and the 0.4.1 arm failed with *"expected 10 entries, got
10"* — same count, wrong order. The contract is *the old list plus exactly these, in order*, and
a check that had merely counted, or merely permitted the field, would have passed.

## 2026-08-31 — 0.4.2: the sibling of a silent success, and the transcript that had never been run

A review of 0.4.1 found eight things. Two mattered: one of them was **in the record of 0.4.1
itself**, and one was **in 0.4.1's own fix for a silent success**.

### 1. The transcript that could not have produced its own output (§6 above)

The recorded acceptance command named a release on a flag that takes no value. Measured:
`unrecognized arguments`, **exit 2**. Two of the three control arms were unrunnable for the same
reason, the third had become impossible by construction, and the quoted success line was a
wording the program does not print. The correction and its dated note live in §6, where the
defect was; this section records the instrument change, because fixing three sites would have
left the class open — it had already recurred once (s293 → s295).

`compare_runs.build_parser()` is now exposed, and `tests/test_compare_runs.py` judges the
documents with it:

| sweep | population | found before the fix |
|---|---|---|
| every `$ …compare_runs.py …` line, fed to the real parser | tracked `.md` | **5 commands, 1 rejected** |
| a release name after the flag, in prose or a table | tracked `.md` | **3 sites** |

Both carry a must-fire and a must-not-fire arm, the population comes from `git ls-files` rather
than a glob, and every planted string is assembled at run time — written out whole it would make
the sweep fire on its own source. The first sweep also over-fired on its first run, on a recorded
command carrying a trailing shell comment: `shlex.split(..., comments=True)` is the fix, and it is
the reason a guard ships with the arm that must stay quiet as well as the one that must fire.

### 2. `__main__.py` ran the CLI on import (the sibling of F6)

0.4.1 closed a silent success — `python -m microrelief.cli` exiting 0 having done nothing — and
its own review then added `__main__.py` so the documented form worked too. That file called
`main()` at module level, so `import microrelief.__main__` **ended the interpreter** with
argparse's usage and exit 2: `pkgutil.walk_packages`, a doctest or coverage sweep over `src/`,
an autodoc build. The fix for a failure that was too quiet had published one that is too loud.

The guard is three lines. The test asserts the **sentinel printed after the import**, not the
return code — an exit code says the process ended, a sentinel says it survived, which is the
property an importer actually needs.

### 3. Three more, all measured before accepting

`compare_runs.py`'s unknown-release branch emitted **two contradicting problem lines** — *"no
expected limitations are recorded here"* beside *"known_limitations is not the old list plus the
two declared gaps"* — sending a reader after a limitations bug that does not exist. A refusal
makes one claim. `CALIBRATIONS.md`'s corrected `max_cells` row said the run holds "**ten** such
arrays" of the 1.6 GB float64 kind: ten × 1.6 GB is 16 GB, against the ~12 GB and the 7.5× in the
same cell. Only five of the ten are 8-byte. And `tests/test_compare_runs.py` left
`sys.modules["compare_runs"]` registered for the rest of the session; it is a context manager now.

### 4. The version bump, and the run that shows nothing moved

`src/` changed, so `package_version` had to move — it is inside the reproducibility hash and is
the only way a code change reaches the artefacts, and both records ship inside the repository.
0.4.1 → 0.4.2 in `__init__.py`, `pyproject.toml`, `uv.lock`, `CITATION.cff` and the skill's
frontmatter.

```
$ .venv/bin/microrelief run --aoi examples/sistelo-sample/aoi.geojson \
    --laz examples/sistelo-sample --out <tmp> \
    --attribution "$(cat examples/sistelo-sample/attribution.txt)"
grid 300 x 300 cells of 0.5 m (0.0225 km2), 1 tile(s), 1 return(s) outside the AOI
measured 56.2% | interpolated 43.1% | undetermined 0.7%
expected void at f=1: 1.312% (measured density 17.3 pts/m2)
ground recall 0.999 | non-ground recall 0.723 | accuracy 0.837 | majority-class null 0.587
flight dates (none declared) | mixed epochs False
reproducibility_hash 7cbed28290450fee83ba7acc00ae9c24997b412b12c600cfd00e5eefd5e9347f
```

```
$ /usr/bin/time -f "%e s wall, %M kB peak RSS" .venv/bin/microrelief run \
    --aoi aoi/aoi.geojson --laz ~/data/dgt-laz --out outputs_0.4.2/ --cell 0.5 \
    --selection outputs_0.2.0/selection.json --attribution "Source: Direção-Geral do Território (DGT), ..."
grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 74.6% | interpolated 25.2% | undetermined 0.2%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.999 | non-ground recall 0.495 | accuracy 0.749 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash 257c8dac78264df2295d8afff6bb99a8705b9cb670bc7532cb8616a3a033b477
30.62 s wall, 4612952 kB peak RSS
```

Every line but the hash is identical to 0.4.1's, in both runs.

**The acceptance is the bare form**, because 0.4.2 declares no new limitation — the list must be
*unchanged*, which is what the flag's absence asserts:

```
$ .venv/bin/python scripts/compare_runs.py outputs_0.4.1b outputs_0.4.2
...
6 raster(s) compared
provenance.created_utc: 2026-08-30T09:57:40.796776+00:00 -> 2026-08-31T13:48:53.527950+00:00
provenance.package_version: 0.4.1 -> 0.4.2
provenance.reproducibility_hash: 7b78c489df89... -> 257c8dac7826...
provenance.known_limitations: 10 -> 10 entries

identical in every band and every record field but the three permitted, and known_limitations unchanged
```

| arm | exit | what it proves |
|---|---|---|
| bare, `outputs_0.4.1b outputs_0.4.2` | **0** | the acceptance |
| with the flag | 1 | *"the new run declares version '0.4.2', for which no expected limitations are recorded here"* — one problem line, not two, which is §3's fix in the real instrument rather than in a unit test |
| bare, 0.4.0's record against this one | 1 | the limitation assertion is live: 8 entries against 10 |

**The control that says the bump changed metadata and not data**: the sample's six *pixel*
digests (`expected/bands.sha256.json`, which hashes `src.read(1)`, not the file) are **6 of 6
unchanged**, while all **12 of 12** golden fixture hashes — whole TIFF files, tags included —
changed. Metadata-wide, pixel-nowhere. The goldens were regenerated by importing
`tests/test_export.py`'s own `golden_fixtures`, `pipeline` and `export`, so the fixture was
rebuilt with the objects the test hashes rather than a parallel reimplementation of them.

Gates, each exit code read separately: `uv sync --locked` 0 · ruff check 0 · ruff format 0 ·
mypy 0 · pytest **265 passed** · neutrality self-test 0 (14 controls fire) · neutrality 126/126
tracked, 0 hits.

### 5. The pre-flip `/cso`, and the one thing it found that the gates could not

Run against this tree rather than an earlier one, because the three prior clean audits
(2026-08-26, 08-27, 08-30) all predate it — `SECURITY.md` did not exist at the last one, and a
clean verdict is not evidence about bytes that were not there. Every layer carried a denominator
and a control that had to fire: **427 unique blobs over 13 refs / 99 commits, 0 credential hits**
(control matched 248/427) · **38 third-party packages against OSV, 0 vulnerabilities** (controls
returned 10/18/43 through the identical pipeline) · CI on `pull_request`, `contents: read`, both
actions SHA-pinned, no `${{ }}` inside any `run:` · **one outbound call in the whole package**,
fixed host, explicit timeout, and the catalogue `href` recorded and never followed · no
`eval`/`exec`/`pickle`/`shell=True`, sha256 only, the single `subprocess` an argv list with a
timeout · the six agent-instructing files read whole, with their byte counts, 0 hits.

**What it found is not a vulnerability, and it is worth more than one:** `skills/microrelief/SKILL.md`
and `examples/sistelo-sample/README.md` were still publishing 0.4.1's sample hash, and
`SKILL.md` claimed `tests/test_sample.py` locked it. Nothing did — the README's lock asserts the
hash appears **in the README**, so the suite stayed green at 265 with both stale copies in the
tree. The sweep that updated the hashes had been scoped to one file: one file is one witness,
which is the class 0.4.1 had already named for the 60 B/cell figure.

The fix is the lock, not the two edits. `tests/case_study/test_readme_claims.py` now derives its
population from `git ls-files` — every tracked `.md` carrying a token presented as a record hash —
and asserts a **partition**: a live claim must carry a current hash, or the file is a dated record
with its reason written down (`docs/live-smoke.md`, `docs/self-check.md` — a superseded hash there
is the point, and editing it would falsify the record). A second test fails if an exemption stops
publishing a hash, so the list cannot rot into a hole; a third plants a stale token and a current
one and requires the check to fire on the first and stay quiet on the second.

**Open, and not code:** `SECURITY.md` states "Dependabot alerts are enabled on this repository."
Measured: `GET /repos/.../vulnerability-alerts` returns 404, `"Vulnerability alerts are
disabled."` — a state, not an auth failure (the same client reads the repo metadata fine). The
private reporting channel the document names as its **only** one is a public-repository feature,
so it cannot be verified while this repo is private. Both belong to the flip sitting: enable them
and re-verify by API, or change the sentence — the policy must not describe a posture the
repository does not have.

---

## 2026-08-31 — the second AOI: Valongo / Paredes, six tiles, 675 MB

Pre-registered at `181d95d` before the run (`docs/second-aoi-preregistration.md`); verdict and
analysis in `docs/second-aoi-gate-result.md`. **Verdict: FAIL** — the DTM publishes buildings as
terrain. Recorded here because the commands and their outputs are what the verdict rests on.

**Acquisition — automated this time, and the reason the earlier entry could not be.** `SITE.md`
records the direct grant refused: `POST /token` with `grant_type=password` answers 401
`unauthorized_client`, and that remains true. The *browser* flow is a different endpoint and it
does authenticate this account: the OIDC authorization-code exchange at
`/realms/dgterritorio/.../auth` yields a portal session, and with that session a download href
returns 206. Both controls fired — a junk password and a non-existent user are each refused with
*"Nome de utilizador ou palavra-passe inválida"* — so the accepted login is evidence and not a
server that says yes to everything.

**The href's 64-hex segment is a short-lived token, not a stable identifier.** An href minted 30
minutes earlier answered `403 {"status":403,"message":"Forbidden Access - Expired token or file
not found"}`; a fresh one from the same search answered `206` with `LASF` in the first four bytes.
So each href is minted and spent in one pass. Acceptance stayed the artefact — every file's byte
count against the catalogue's `file:size`, and the `LASF` magic:

    LO-160470-07-2025: 123,901,792 bytes (declared 123,901,792) magic=b'LASF' OK
    LO-160471-07-2025: 106,466,721 bytes (declared 106,466,721) magic=b'LASF' OK
    LO-161470-07-2025: 124,866,796 bytes (declared 124,866,796) magic=b'LASF' OK
    LO-161471-07-2025:  95,203,665 bytes (declared  95,203,665) magic=b'LASF' OK
    LO-162470-07-2025: 120,315,748 bytes (declared 120,315,748) magic=b'LASF' OK
    LO-162471-07-2025: 104,665,870 bytes (declared 104,665,870) magic=b'LASF' OK
    accepted 6/6, 675,420,592 bytes

**select and precheck:**

```
$ microrelief select --aoi aoi/valongo.geojson --out selection.json
6 tiles, coverage 1.0000, 1 sortie(s), 1 stamp(s) -> selection.json

$ microrelief precheck --aoi aoi/valongo.geojson
LO-160470-07-2025   21.4 pts/m2  2025-12-08  void(open)=0.477%  void(f=0.4)=11.8%
LO-160471-07-2025   17.7 pts/m2  2025-12-08  void(open)=1.201%  void(f=0.4)=17.1%
LO-161470-07-2025   20.9 pts/m2  2025-12-08  void(open)=0.534%  void(f=0.4)=12.3%
LO-161471-07-2025   16.0 pts/m2  2025-12-08  void(open)=1.844%  void(f=0.4)=20.2%
LO-162470-07-2025   20.8 pts/m2  2025-12-08  void(open)=0.551%  void(f=0.4)=12.5%
LO-162471-07-2025   17.1 pts/m2  2025-12-08  void(open)=1.386%  void(f=0.4)=18.1%
```

**A refusal, correct, from pointing `--laz` at a directory holding tiles outside the selection:**

```
LO-179556-07-2025 is not in the selection (LO-160470-07-2025, ...); refusing to publish
catalogue facts for some tiles and none for others
exit=2
```

**The run, twice, at identical parameters — byte-identical both times:**

```
grid 3960 x 5960 cells of 0.5 m (5.9004 km2), 6 tile(s), 1472090 return(s) outside the AOI
measured 87.3% | interpolated 12.6% | undetermined 0.1%
expected void at f=1: 0.854% (measured density 19.1 pts/m2)
ground recall 1.000 | non-ground recall 0.262 | accuracy 0.700 | majority-class null 0.594
flight dates 2025-12-08T00:00:00Z | mixed epochs False
reproducibility_hash ee05b4e174a92a10567f058c07463f9a0188f360d756a57a0b9b900161b1e5bf
```

run 1: wall 34.29 s, peak RSS 3,205,920 KB · run 2: wall 32.74 s, peak RSS 3,206,016 KB.
Both `reproducibility_hash` identical, `grid`/`honesty`/`agreement` identical, 6 of 6 raster file
digests matching. **The declared read instability did not reproduce** on a grid 1.5x Sistelo's.

**What the run found.** Over cells holding official class-6 (building) returns, CHM median
**0.06 m**, 79.8% below 0.5 m — buildings published as terrain, with `agreement` reporting ground
recall 1.000 and nothing in `known_limitations` naming it. Controls in the same tile: class 5
vegetation median 5.87 m (8.9% flat), class 2 ground median 0.05 m. The same measurement on
Sistelo's own outputs gives 0.17 m and 66.5% flat, over 32,937 building cells against 575,771
here — **the defect is already in the published piece**, hidden by a site with almost nothing
built in it. Diagnostic at `--max-window-m 40`: flat-building share 79.8% → 61.8%, non-ground
recall 0.262 → 0.540, undetermined 0.1% → 7.5%. Load-bearing, and not fixed by any value tested.

**The CRS read this AOI could not have been reached without** is 0.4.3's fix, exercised here
against the live catalogue: before it, this AOI's own delivery was refused with *"Supply an AOI in
EPSG:9001"*, which is false and cannot be followed.

## 2026-08-31 — T-E6r: what excuses a building, and what SMRF does instead

Predicates pre-registered at `57a3c1c` before the run; analysis, controls and the ruling in
`docs/ground-filter-diagnosis.md`. Recorded here because the README quotes these numbers and this
file is where a README number is allowed to come from.

**The population.** Cells holding official ASPRS class-6 returns, no class-2 return in the cell,
and at least two cells inside the class-6 footprint — an unambiguous roof interior, where the
minimum surface cannot be the ground by class. The delivery's classification defines the
population being audited; it decides no cell in either filter.

**What the shipped filter claims over a roof**, from the `basis` band of the Valongo run and of
the published Sistelo run (`outputs_0.4.2`):

    Valongo, default parameters
      roof interior       3,524,239 cells   measured 89.7%  interpolated 10.2%  undetermined  0.1%
      control: canopy     2,493,967 cells   measured 33.9%  interpolated 65.5%  undetermined  0.7%
      control: ground    12,062,527 cells   measured 100.0% interpolated  0.0%  undetermined  0.0%

    Sistelo, the SHIPPED run 0.4.2
      roof interior          86,759 cells   measured 77.2%  interpolated 22.3%  undetermined  0.5%
      control: ground     4,126,962 cells   measured  99.9% interpolated  0.1%  undetermined  0.0%

3.16 million falsely-measured roof cells at Valongo, **13.7%** of that AOI; 0.43% of the published
Sistelo AOI. Neither knob separates a roof from terrain: best single height threshold **0.712**
balanced accuracy over 2,062 components, best single width threshold **0.528**.

**PDAL, installed without root and exercised against the same tiles.** conda-forge via micromamba;
the version is read from the binary, not remembered:

```
$ ./bin/micromamba create -y -p ./env -c conda-forge pdal
$ ./env/bin/pdal --version
pdal 2.10.2 (git-version: e8618b)
$ ./env/bin/pdal --drivers | grep smrf
filters.smrf                 Simple Morphological Filter (Pingel et al., 2013)
```

The pipeline, out of the box but for the noise exclusion this tool already does:

```json
[{"type":"readers.las","filename":"<tile>.laz"},
 {"type":"filters.smrf","ignore":"Classification[7:7]"},
 {"type":"writers.las","filename":"<out>.laz","compression":"true","forward":"all"}]
```

**Control before the comparison**, because a filter that silently did not run would look like an
excellent one. On LO-162471, SMRF moves 2,014,732 returns into ground that the delivery calls
non-ground and 90,837 the other way, so the output is its verdict and not the delivery's labels
read back. Its `returns` default is `[last, only]`; the points it passes through untouched are
7,345 class-2 against 100,326,647 judged (0.007%) and are excluded.

**The comparison**, cell counted as ground if it holds at least one ground return — the rule
`agreement()` already uses:

    population                     cells        ours (measured)   SMRF (ground)
    roof interior              3,524,239                 89.7%           16.1%
    control: canopy            2,493,967                 33.9%           19.5%
    control: plain ground     12,062,527                100.0%           99.4%

Falsely-measured roof cells 3,160,305 -> 566,299. **And it does not eat the terraces:** in the
documented 150 m window around the tallest verified riser, SMRF keeps ground in 91.8% of the cells
this filter calls ground and 86.5% of those on a step above 2.5 m in 3.5 m; where both call a cell
ground the surfaces agree to +0.000 m median over 46,449 cells.

> **Declared gap, and it is the first task of the build that follows.** The PDAL commands above
> replay from this file. The per-cell measurement that produced the tables does **not**: it ran
> from a script that is not in this tree, so these numbers are recorded with their method described
> rather than with a command a reader can run. That instrument is the acceptance check the SMRF
> implementation will be measured against, so it lands in `scripts/` with that work rather than
> being reconstructed later from prose.

---

## 2026-09-03 — the in-repo SMRF, measured cell by cell against PDAL's

`src/microrelief/smrf.py` is SMRF (Pingel et al. 2013) re-implemented here; PDAL 2.10.2 is the
reference it is validated against, not a runtime dependency. The acceptance predicates were fixed
and committed in `4fdc82b` **before** any of this ran — `docs/smrf-build-preregistration.md`.
Nothing below is wired into the pipeline: the CLI default is still the old filter.

### The reference cache, rebuilt with three additions

```
$ python scripts/compare_ground_filters.py reference \
    --tiles ~/data/dgt-laz-valongo --smrf <work> --aoi aoi/valongo.geojson \
    --cell 0.5 --pipeline <work>/smrf-LO-162471.json --out <work>/valongo-reference-v2.npz
"controls": {
    "into_ground": 15892932,
    "out_of_ground": 322530,
    "passed_through_class2": 7345,
    "judged": 100323464
  }
wrote <work>/valongo-reference-v2.npz (287.8 MB)
```

Byte-for-byte the same controls and the same six tile sha256s as the 2026-09-02 build, so the
additions (`min_z_judged`, `min_z_reference_ground`, per-tile bounds) changed no measurement. The
recorded pipeline hash `8055f03add32c1b0` was matched back to its file (`smrf-LO-162471.json`) by
`sha256sum`, which is what says this is the same environment and not a similar one.

### The old filter on the new cache — the 2026-09-02 table, re-derived

reference filter: PDAL filters.smrf
controls: {"into_ground": 15892932, "out_of_ground": 322530, "passed_through_class2": 7345, "judged": 100323464}

population                                                           cells  ours meas.  ref ground ours interp
--------------------------------------------------------------------------------------------------------------
A: any class-6 return                                            4,738,087       88.9%       24.6%       10.9%
B: class-6, no class-2                                           4,270,425       87.7%       16.4%       12.1%
C': B eroded by roof-margin (OUR reading, not the recorded size)   2,223,855       95.7%       19.3%        4.2%
control: canopy (class 5, no class 2, no class 6)                2,493,967       33.9%       19.5%       65.5%
control: plain ground (class 2, no class 5, no class 6)         12,062,527      100.0%       99.4%        0.0%

falsely-measured roof cells, ours:      2,127,452
falsely-measured roof cells, reference: 429,336

Every published figure of `docs/reference-instrument-result.md` reproduces exactly: rows A and B,
both controls, and their shares. Row C is still absent, for the reason recorded there.

### The in-repo SMRF, same cache, PDAL's own defaults

```
reference filter:  PDAL filters.smrf
our surface:       min_z_all
our SMRF params:   SmrfParams(cell=1.0, slope=0.15, scalar=1.25, threshold=0.5, window=None, cut=0.0)  (window_m = 18.0)
controls:          {"into_ground": 15892932, "out_of_ground": 322530, "passed_through_class2": 7345, "judged": 100323464}

population                                                           cells  ours ground  ref ground
---------------------------------------------------------------------------------------------------
A: any class-6 return                                            4,738,087        24.6%       24.6%
B: class-6, no class-2                                           4,270,425        16.4%       16.4%
C': B eroded by roof-margin (OUR reading, not the recorded size)   2,223,855        19.3%       19.3%
control: canopy (class 5, no class 2, no class 6)                2,493,967        19.5%       19.5%
control: plain ground (class 2, no class 5, no class 6)         12,062,527        99.4%       99.4%

cells compared (measured):         23,058,525
  both ground:                     16,720,892
  ours only:                           42,055
  reference only:                      35,900
  neither:                          6,259,678
  agreement:                            99.66%
  Cohen's kappa:                        0.991

excluding 20 m either side of a tile edge (reported, not a gate):
  cells compared:                  21,607,897
  agreement:                            99.73%
  Cohen's kappa:                        0.993

the reference's ground verdict came from a point above the cell minimum:
  more than 0.05 m above:               0.02%
  more than 0.25 m above:               0.01%
  more than 1.00 m above:               0.00%

pre-registered predicates (docs/smrf-build-preregistration.md):
  P1 plain ground called ground: 99.410 >= 97.0 -> PASS
  P2 row B called ground: 16.426 <= 30.0 -> PASS
  P3 agreement: 99.662 >= 90.0 -> PASS
  P3 kappa: 0.991 >= 0.6 -> PASS

VERDICT: PASS
```

### Must-fire control: the same comparison, with the parameters wrong

A table where our filter matches the reference on every population to the first decimal is a
result or a tautology, and the difference is whether it can fail. Run with a one-metre window, a
1.5 slope tolerance and a five-metre threshold:

```
--smrf-window 1.0      B: 88.0% ground (ref 16.4%)   agreement 83.30%   kappa 0.482   VERDICT: FAIL
--smrf-slope 1.5       B: 86.3% ground (ref 16.4%)   agreement 82.54%   kappa 0.452   VERDICT: FAIL
--smrf-threshold 5.0   B: 52.2% ground (ref 16.4%)   agreement 86.86%   kappa 0.611   VERDICT: FAIL
```

The comparison can fail, and a badly parameterised SMRF degrades into exactly the failure mode of
the filter shipping today: it publishes roofs as ground.

### Declared side-measurement: the input rule is not the residual

```
our surface:       min_z_judged
  agreement:                            99.68%
  Cohen's kappa:                        0.992
  agreement:                            99.75%
  Cohen's kappa:                        0.994
  P1 plain ground called ground: 99.408 >= 97.0 -> PASS
  P2 row B called ground: 16.411 <= 30.0 -> PASS
  P3 agreement: 99.684 >= 90.0 -> PASS
  P3 kappa: 0.992 >= 0.6 -> PASS
VERDICT: PASS
```

Handing the filter the minimum over the returns the reference itself reads (last/only, class 7
excluded) instead of the pipeline's minimum over all returns moves agreement from 99.66% to
99.68%. So the 0.34% of cells the two filters disagree about are not an artefact of the input.

### Derived, by command rather than by hand

```
$ python -c "b, measured = 4_270_425, 23_058_525; print(...)"
row B is 4,270,425 of 23,058,525 measured cells = 18.5%
```

## 2026-09-03 — P4: what the in-repo SMRF costs on the terraces

The predicate deferred out of the build pre-registration because Valongo has terraces only
incidentally. Population, surface and step operation fixed in
`docs/p4-terrace-preregistration.md` at `7429761`, **before** any of this ran; result and the
figures that did not reproduce in `docs/p4-terrace-result.md`.

PDAL 2.10.2 was reinstalled for this — the environment behind the 2026-08-31 diagnosis died with
a session scratchpad, which is why that document's numbers have no artefact.

```
$ pdal --version
pdal 2.10.2 (git-version: e8618b)

$ pdal --drivers | grep -i smrf
filters.smrf                 Simple Morphological Filter (Pingel et al., 2013)

$ pdal pipeline docs/p4-reference-pipeline.json \
    --readers.las.filename=<tile-dir>/LO-179557-07-2025.laz \
    --writers.las.filename=<ref-dir>/LO-179557-smrf.laz
(pdal pipeline readers.las Warning) Found 3 extra byte VLRs. Concatanating all extra byte records into one.
# 27,720,324 points in, 27,720,324 out

$ python scripts/compare_ground_filters.py reference --tiles <tile-dir> --smrf <ref-dir> \
    --aoi examples/sistelo-sample/aoi.geojson --out <cache>.npz \
    --pipeline docs/p4-reference-pipeline.json
  "reference_pipeline_sha256_16": "8e328b1ba0a2d949",
  "controls": {
    "into_ground": 3217933,
    "out_of_ground": 42068,
    "passed_through_class2": 60221,
    "judged": 16887698
  }
wrote <cache>.npz (1.2 MB)
```

The control first: SMRF moves 3,217,933 returns into ground and 42,068 out of it, so the output is
its own verdict and not the delivery's labels read back.

```
$ python scripts/compare_ground_filters.py terraces --reference <cache>.npz
population                                               cells   SMRF ground   PDAL ground
------------------------------------------------------------------------------------------
P4a: our measured ground                                50,596         91.1%         91.8%
P4b: ... on a step > 1.5 m                              27,637         95.4%         95.7%
P4b: ... on a step > 2 m                                16,482         95.4%         95.5%
P4b: ... on a step > 2.5 m  (GATE)                       7,625         95.1%         95.1%

reported, with nothing riding on it:
  P4b at > 2.5 m requiring >= 10 finite cells: 7,426 cells, SMRF 95.4%, PDAL 95.4%
  where both our filter and PDAL call a cell ground: 46,427 cells, median difference +0.000 m, 0.03% differ by more than 0.5 m

pre-registered predicates (docs/p4-terrace-preregistration.md):
  P4a our measured ground kept: 91.078 >= 85.0 -> PASS
  P4b kept on a step > 2.5 m: 95.082 >= 80.0 -> PASS

VERDICT: PASS
$ echo $?
0
```

**The control that says the gate can fail**, run before the verdict was read. Same command, a
parameterisation chosen to cut terraces:

```
$ python scripts/compare_ground_filters.py terraces --reference <cache>.npz \
    --smrf-slope 0.01 --smrf-threshold 0.05
[abridged: the header block, the > 1.5 m and > 2 m sweep rows and the "reported, with nothing
 riding on it" block are omitted. Every other transcript in this file is verbatim.]
P4a: our measured ground                                50,596         58.6%         91.8%
P4b: ... on a step > 2.5 m  (GATE)                       7,625         60.2%         95.1%
  P4a our measured ground kept: 58.601 >= 85.0 -> FAIL
  P4b kept on a step > 2.5 m: 60.197 >= 80.0 -> FAIL

VERDICT: FAIL
$ echo $?
1
```

PDAL's 91.8% on the base population reproduces the 2026-08-31 figure to the precision it states,
and the both-ground control lands 22 cells from its 46,449. **Its 86.5% on the steep population
does not reproduce** — 95.1% here — which places the whole disagreement inside the one phrase that
record left undefined. Detail and consequence in `docs/p4-terrace-result.md`.

---

## 2026-09-03 — SMRF becomes the ground filter (0.5.0): both products re-run

The filter built and measured in 0.4.4's aftermath is now the one the pipeline runs. The
progressive morphological filter stays in the tree as the comparison arm and nothing else.

**What the release is accepted on.** Not `compare_runs.py old new`: every band changes on
purpose, so the band-identity spine has no verdict to give across this boundary. The acceptance
is **self-replay** — each product run twice, required byte-identical — plus the declared
limitation transformation checked across the version boundary, plus a table of what moved.

### The sample, against a target fixed before the wiring existed

`docs/smrf-default-preregistration.md` fixed the eleven figures the wired CLI had to produce,
measured by a script that calls the library directly and never touches the CLI. The control
that makes it worth anything: the same script reproduced the *current* filter's published
record exactly, down to `fp = 14327`.

```
$ .venv/bin/microrelief run --aoi examples/sistelo-sample/aoi.geojson \
    --laz examples/sistelo-sample --out <tmp>/sample-a --cell 0.5 \
    --attribution "$(cat examples/sistelo-sample/attribution.txt)"
grid 300 x 300 cells of 0.5 m (0.0225 km2), 1 tile(s), 1 return(s) outside the AOI
measured 51.6% | interpolated 42.3% | undetermined 6.1%
expected void at f=1: 1.312% (measured density 17.3 pts/m2)
ground recall 0.977 | non-ground recall 0.788 | accuracy 0.866 | majority-class null 0.587
flight dates (none declared) | mixed epochs False
reproducibility_hash 096b82c54327ef0ba05506457bcae975ae21402360ca3e04c31cea9ad0807ada
```

Eleven of eleven matched, the four confusion counts exactly (`tp 35470 fp 10934 fn 844
tn 40730`, `n_cells 87978`). The hash above is the pre-bump run — the version moved afterwards,
which is what carries it to `2da06987808e983b611144b5ddce217be2eb7f513b9ab9e8268ff51dd98e32dd`.

The filter itself was accepted earlier the same day: re-implemented from PDAL 2.10.2's
`filters/SMRFilter.cpp`, it agrees with that build on **99.662%** of cells at κ 0.991 — **over the
six-tile Valongo AOI, 23,058,525 measured cells**, not over the sample
(`docs/smrf-build-result.md`, and the `P3 agreement: 99.662 >= 90.0 -> PASS` line in this file's
2026-09-03 SMRF-build entry). What is wired here is that implementation, not PDAL's.

The population matters and naming it wrong made two published sentences refute each other. On the
90,000-cell sample, 0.338% disagreement is at most ~297 cells, which cannot open a 0.9-point
accuracy gap — yet the README shows this build at 0.866 against PDAL's 0.857 in the 2026-08-27
table. Those are different populations, and the figure above is Valongo's.

### Self-replay, both products

```
$ .venv/bin/python scripts/compare_runs.py <tmp>/sample-b <tmp>/sample-c
n_ground_asprs.tif: 90000 cells compared
6 raster(s) compared
provenance.created_utc: 2026-09-03T14:37:25.658887+00:00 -> 2026-09-03T14:37:26.202591+00:00
provenance.package_version: 0.5.0 -> 0.5.0
provenance.reproducibility_hash: 2da06987808e... -> 2da06987808e...
provenance.known_limitations: 13 -> 13 entries

identical in every band and every record field but the three permitted, and unchanged
```

```
$ /usr/bin/time -f "%e s wall, %M kB peak RSS" .venv/bin/microrelief run \
    --aoi aoi/aoi.geojson --laz ~/data/dgt-laz-sistelo --out outputs_0.5.0/ --cell 0.5 \
    --selection outputs_0.2.0/selection.json --attribution "Source: Direção-Geral do Território (DGT), ..."
grid 3960 x 3960 cells of 0.5 m (3.9204 km2), 4 tile(s), 3250766 return(s) outside the AOI
measured 69.7% | interpolated 28.2% | undetermined 2.1%
expected void at f=1: 0.117% (measured density 27.0 pts/m2)
ground recall 0.993 | non-ground recall 0.588 | accuracy 0.792 | majority-class null 0.503
flight dates 2026-03-30T00:00:00Z | mixed epochs False
reproducibility_hash 09b79da9fff731caeebbb4b37b8c5508eb10ed0399940382212c48ba810518c2
34.64 s wall, 4618688 kB peak RSS

$ .venv/bin/python scripts/compare_runs.py outputs_0.5.0 outputs_0.5.0_replay
identical in every band and every record field but the three permitted, and unchanged
```

**SMRF's cost, measured rather than assumed:** 34.64 s against 0.4.2's 30.62 s, and
4,618,688 kB peak RSS against 4,612,952 kB — about four seconds and no extra memory, on a run
holding two extra k-d tree fills over the full grid.

**`--laz ~/data/dgt-laz` no longer reproduces the recorded command.** That directory has since
gained the six Valongo tiles, and the selection guard refused, correctly and by name:
`LO-160470-07-2025 is not in the selection (...); refusing to publish catalogue facts for some
tiles and none for others`. The four Sistelo tiles were symlinked into
`~/data/dgt-laz-sistelo`. The refusal is the mechanism working; the old command line is left in
its own entry above, because that is a record of what ran.

### What gated the release

SMRF was accepted against the terraces before being wired, on bounds pre-registered before the
run: it keeps **91.078%** of the cells the old filter called measured ground (bound 85.0) and
**95.082%** of those standing on a step above 2.5 m (bound 80.0), with the must-fail control at
58.601% / 60.197% returning FAIL at exit 1. Full record, including the ramp confound measured and
declared, in `docs/p4-terrace-result.md`.

### The declared limitation transformation, across the version boundary

The `old` side has to be a real product, six bands and all: `--record-only` skips the pixel
comparison and nothing else, so a directory holding no rasters is still refused. The shipped
`expected/` directory carries digests rather than GeoTIFFs, so the 0.4.4 product was rebuilt from
the code that made it — `git worktree add <tmp>/wt-0.4.4 9bb2e29`, then the run below through
`PYTHONPATH=<tmp>/wt-0.4.4/src`. It reproduced the published 0.4.4 record exactly, hash
`f67b2f033d23` and accuracy 0.837 against a 0.587 null, which is what makes it the right `old`.

```
$ .venv/bin/python scripts/compare_runs.py --record-only --expect-new-limitations <tmp>/sample-0.4.4 <tmp>/sample-d
bands not compared (6 present): --record-only
provenance.agreement: changed (not asserted under --record-only)
provenance.honesty: changed (not asserted under --record-only)
provenance.parameters: changed (not asserted under --record-only)
provenance.uncalibrated_thresholds: changed (not asserted under --record-only)
provenance.package_version: 0.4.4 -> 0.5.0
provenance.known_limitations: 11 -> 13 entries

the bands were not compared; every record field that moved is named above, and
known_limitations is exactly the old list under 0.5.0's declared transformation (1 replaced, 2 added)
```

The same command against `outputs_0.4.2` **fails**, and the failure is the finding below: the
last full-run record was never regenerated at 0.4.4, so the list it carries is 0.4.2's ten and
the line 0.5.0 replaces is not in it.

### Found by the new guard: the published viewer record was a release behind

`docs/viewer/provenance.json` — the record a reader of the published piece actually opens — sat
at **0.4.2 with ten limitations, the buildings line absent**. 0.4.4 declared that limitation,
bumped the version and regenerated the *sample*; the full product was never re-run, so the most
important disclosure of that release never reached the artefact a reader sees. The suite was
green throughout: the sample had a test locking its record, and the viewer's record had only the
hash partition guard, which asks whether every *document* quotes a current hash and never
whether the *records* themselves are current.

Two guards now close it (`tests/case_study/test_readme_claims.py`): every published record must
declare the package's current version, and must carry the exact limitation list the code
declares. Both were red on the tree before this release re-rendered the viewer.

### What moved

| the full product (3960 x 3960) | 0.4.2 (PMF) | 0.5.0 (SMRF) |
|---|---|---|
| measured | 74.6022% | 69.7423% |
| interpolated | 25.2074% | 28.1972% |
| undetermined | 0.1903% | 2.0605% |
| ground recall | 0.9993 | 0.9932 |
| non-ground recall | 0.4954 | 0.5881 |
| accuracy | 0.7491 | 0.7921 |
| majority-class null | 0.5035 | 0.5035 |
| fp (ours ground, official none) | 3,889,074 | 3,174,486 |

| the shipped sample (300 x 300) | 0.4.4 (PMF) | 0.5.0 (SMRF) |
|---|---|---|
| measured | 56.2189% | 51.5600% |
| interpolated | 43.1067% | 42.3411% |
| undetermined | 0.6744% | 6.0989% |
| ground recall | 0.9988 | 0.9768 |
| non-ground recall | 0.7227 | 0.7884 |
| accuracy | 0.8367 | 0.8661 |
| majority-class null | 0.5872 | 0.5872 |
| fp | 14,327 | 10,934 |

Read the two tables together and the shape is one trade: the filter answers over fewer cells and
is right more often about the ones it answers over. `undetermined` rises because a cell it cannot
call ground now publishes as nothing rather than as terrain — nine-fold on the sample, ten-fold on
the full product. Against the delivery's own ground class, non-ground recall rises 9.3 points on
the full product and `fp` falls by 714,588 cells: those are roofs and canopy the old filter called
ground. Ground recall falls 0.6 points, which is the same trade read from the other side.

### What the pre-merge review changed, 2026-09-03

`/code-review high` on the branch, after the release commit was written. **Eight findings, 8/8
reproduced before anything was changed.** Four were mine, and two of those are the kind that
survive a green suite because they are about the instruments rather than the code:

- **The 99.662% agreement figure was published "over the sample"; it was measured over the
  six-tile Valongo AOI, 23,058,525 measured cells.** Introduced an hour earlier, in the sentence
  added to satisfy the README percentage lock. It also made two published sentences refute each
  other: on 87,978 shared cells, 0.338% disagreement is ~297 cells and cannot open the 0.9-point
  accuracy gap the README shows between this build and PDAL's. Both sites now name Valongo.
- **`--record-only` skipped the band-set comparison and the nothing-scanned guard**, not just the
  pixel loop. Measured: two directories holding **zero** rasters returned exit 0 with the full
  success verdict — and this was the only acceptance path across the version boundary. The file's
  own comment ("silence-by-nothing-scanned and silence-by-clean-comparison must not look alike")
  was the rule that got moved under the flag. Both checks are back outside it, with controls.
- **The record-currency control asserted a dict it had written itself.** Its only live assertion
  was `__version__ != "0.0.0"`; deleting the check it claimed to control left it green. It now
  calls the same function the check calls, and the firing arm requires *every* record to be named.
- **The new `known_limitations` line understated the snap by up to 9×.** It said "one cell per
  axis", true only at `--cell 0.5`; measured, `0.25` adds 3, `0.2` adds 4 and `0.1` adds 9, and
  `0.2` is a value the agent skill advertises. The record now states the rule
  (`(1 m / --cell) - 1`) and the worked examples moved to the README and the skill, because the
  evidence lock reads a decimal in a limitation as a measurement owing a dated source — which is
  the right reading for a measurement and the wrong home for an arithmetic example.

The other four: an AOI with no measured cells refused with `the surface still has holes ... a
caller skipped the fill`, an internal contract message blaming the caller, where the retired
filter said `no measured cells`; `--cell 0` raised a bare `ZeroDivisionError` because
`block_factor` now runs before `grid_for_bounds`, which owned the positivity check;
`compare_ground_filters.py`'s `reference` command was the one other driver of the filter over a
`grid_for_bounds` grid and the snap did not reach it; and `CITATION.cff` had the new version
against 0.4.4's release date.

**The fix for the last of those contained the same class it was fixing:** the first version
passed `block_factor(args.cell, args.smrf)`, and `args.smrf` is the reference-output *directory*,
not `SmrfParams` — an `AttributeError` in the one command the suite never ran. Caught by reading
the argument's declaration, not by a test, which is why that command now has one.

Correcting the limitation text did **not** move `reproducibility_hash`: the hash payload is
`{package_version, grid, parameters, inputs}` and a disclosure sits outside it by design. Verified
rather than assumed — both products re-run, all six band arrays byte-identical, and only
`created_utc` and `known_limitations` differing in either record.

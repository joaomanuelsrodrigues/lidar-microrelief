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

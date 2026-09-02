# Replicating the table that carried the SMRF ruling

**2026-09-02.** Verdict rule fixed before the run in `docs/reference-instrument-preregistration.md`
(commit `106106a`); the instrument is `scripts/compare_ground_filters.py`.

## Verdict: the controls PASS, the table FAILS on one population, the ruling stands

| | recorded | measured here | |
|---|---|---|---|
| **C1** environment | `pdal 2.10.2 (git-version: e8618b)` | identical, read from the binary | **PASS** |
| **C2** into ground, LO-162471 | 2,014,732 | **2,014,732** | **PASS** |
| **C2** out of ground, LO-162471 | 90,837 | **90,837** | **PASS** |
| **C3** judged points outside the mask | 0 | **0** | **PASS** |
| **C3** passed-through class-2 | 7,345 | **7,345** | **PASS** |
| C3 judged total | 100,326,647 | 100,323,464 | **explained exactly** |

The judged total differs by **3,183**, and that is the count of last-or-only returns in the ignored
class 7, summed over the six tiles — measured, not inferred. The record counted the ignored class
as judged; this instrument does not. Nothing else moves with it.

## The table

| population | recorded cells | here | recorded ours | here | recorded ref | here |
|---|---:|---:|---:|---:|---:|---:|
| A: any class-6 return | 4,738,087 | **4,738,087** | — | 88.9% | — | 24.6% |
| B: class-6, no class-2 | 4,270,425 | **4,270,425** | — | 87.7% | — | 16.4% |
| C: roof interior | 3,524,239 | **not reproducible** | 89.7% | — | 16.1% | — |
| control: canopy | 2,493,967 | **2,493,967** | 33.9% | **33.9%** | 19.5% | **19.5%** |
| control: plain ground | 12,062,527 | **12,062,527** | 100.0% | **100.0%** | 99.4% | **99.4%** |

The canopy control also reproduces its published interpolated share exactly (**65.5%**), and plain
ground its **0.0%**.

**FAIL, by the pre-registered rule, on row C.** "B, >= 2 cells inside the edge" names a
morphological erosion that the record never defines operationally, and none of eight readings of
it reaches 3,524,239 from a row B that reproduces exactly:

| reading | cells |
|---|---:|
| taxicab distance >= 2 (single cross erosion) | 3,487,782 |
| chessboard >= 2 / EDT >= 2 (3x3 erosion) | 3,164,586 |
| EDT > 2 / cross erosion x2 | 2,753,600 |
| EDT >= 2.5 | 2,405,397 |
| chessboard >= 3 (5x5 erosion) | 2,223,855 |

The closest is 1.0% short; the reading whose *words* match best ("2 cells inside the edge" =
5x5 erosion) is 37% short. So the population the entire "On buildings" comparison was reported
over is not re-derivable from the method as described — the second time this has happened in this
arc, after the C1 control of `docs/ground-filter-diagnosis.md`, and this time on the headline row
rather than a single-tile row.

## What this does and does not change

**The ruling is untouched, and now rests on populations that re-derive.** SMRF's advantage over
this filter on buildings is 64.3 points on row A, 71.3 on row B, 76.4 on our reading of row C —
against **0.6 points** on plain ground, which reproduces exactly. The recorded "73.6 points on
roofs for 0.6 on ground" is confirmed in substance on populations anyone can rebuild from a
command. Implementing SMRF remains the right call for the reason it was made.

**What changes is what may be quoted.** The figures 3,524,239 / 89.7% / 16.1% / 3,160,305 /
566,299 are not reproducible as published and should not be re-quoted without the erosion being
defined. Rows A and B, both controls, and the shares above are.

## The instrument

Two steps, because they cost three orders of magnitude apart. Both replay from this file.

```
$ ./env/bin/pdal --version
pdal 2.10.2 (git-version: e8618b)

# one PDAL run per tile, out of the box but for the recorded noise exclusion
$ ./env/bin/pdal pipeline smrf-<tile>.json          # 12 s/tile

# reduce delivery + reference tiles to per-cell arrays on the AOI grid  (~3 min, 171 MB)
$ python scripts/compare_ground_filters.py reference \
    --tiles ~/data/dgt-laz-valongo --smrf <dir> --aoi aoi/valongo.geojson \
    --cell 0.5 --out <dir>/valongo-reference.npz

# the table, from the cache  (seconds -- so it can be an inner loop)
$ python scripts/compare_ground_filters.py compare --reference <dir>/valongo-reference.npz
```

Point-order correspondence between a delivery tile and its reference output is **checked, not
assumed** (`check_correspondence`): a silent reorder would keep every count plausible and make
every one of them about the wrong points. It held on all six tiles.

The judged mask is derived from return numbers rather than from class, because PDAL's
`only_ground` is false and `returns` defaults to `[last, only]`: judged points come back as class
1 or 2 while unjudged ones keep their delivery class, so a passed-through class-2 point is
indistinguishable from a judged ground point by class alone. C2 and C3 are what say the derivation
is right.

## Declared, so it is not discovered later

- **`mypy` does not check this script.** The repo's config is `files = ["src"]`; the run reports
  18 files, which is exactly the count of `src/**/*.py`, and `scripts/` holds 8 more. The
  instrument's annotations are unverified by the gate that verifies the package's.
- **Our reader and the reference filter disagree about noise.** `read_laz` excludes ASPRS 7 and
  18; the recorded PDAL pipeline ignores only class 7, so class-18 points are judged by SMRF and
  invisible to us. Negligible here, named because it is a real asymmetry in the comparison.
- **The first draft of this instrument carried three of six filter defaults wrong**, typed from
  memory of the record rather than copied from it (24.0/0.2/3.0 against the shipped 4.0/0.3/2.0).
  Nothing would have failed; the table would have described a filter nobody runs. The two sets of
  literals are now locked to each other, with a control that fails if either moves.
- **The reference cache is not committed** (171 MB), so a clean clone cannot replay the table
  without PDAL. The commands above are what a reader rebuilds it from.

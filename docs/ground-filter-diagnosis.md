# Why the ground filter publishes buildings as terrain

T-E6r, step 1. The second-AOI gate (`docs/second-aoi-gate-result.md`) established **that** the DTM
publishes buildings as terrain. This establishes **what excuses them**, because the repair depends
on it: a wrong mechanism buys a changed default, and a changed default was already measured not to
work.

Everything below the horizontal rule was written and committed **before** the run that fills it in.

---

## A correction to the gate result, found on the way in

The gate result says the diagnostic re-run at `--max-window-m 40` uses *"windows to 16.5 m"* and
explains the surviving buildings as *"wider than 16.5 m"*. Measured by the package's own
`windows_for(40.0, 0.5)`:

    (1.5, 2.5, 4.5, 8.5, 16.5, 32.5)

The largest window is **32.5 m**, not 16.5 m — `_radii` doubles to 32 cells, which is 65 cells
across. The verdict does not move (61.8% of building cells still flat at `w40` is a measurement,
not an inference), but the sentence that explains it is wrong by a factor of two, and it is the
sentence this task was about to build a design on. Dated correction goes in that file.

## What the filter actually does to a roof, measured on synthetic geometry

A square plateau of a given width and height on a flat plane, run through `classify_ground`. The
number is the fraction of the plateau's own cells still called ground — 1.00 means the whole roof
is published as terrain.

| width \ height | d 2 m | d 3 m | d 4 m | d 6 m | w40 2 m | w40 3 m | w40 4 m | w40 6 m |
|---|---|---|---|---|---|---|---|---|
| 3 m | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 8 m | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| 15 m | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| 30 m | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| 50 m | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

`d` = shipped default (windows to 4.5 m); `w40` = `--max-window-m 40` (windows to 32.5 m).

Two separate excuses, and **at the shipped default only one of them is ever reached**:

- **At the default, height never enters.** A 12 m tower 8 m wide is published as terrain exactly
  like a 2 m shed. An opening cannot push down a plateau wider than its window, so nothing wider
  than ~5 m is even a candidate. This is the published defect, and it is a *window* defect.
- **Widening the window makes height the discriminator, and height does not separate.** At `w40`
  a building is caught only if it is also taller than the tolerance at its own scale -- 2.85 m at
  the 8.5 m window, and **3.5 m** at 16.5 m and 32.5 m, where `max_elevation_m` caps it. A
  one-storey roof is ~3 m. The tallest *verified* terrace riser at Sistelo is **2.98 m**
  (`docs/riser-measurement.md`), and that measurement is why the cap is 3.5. The cap cannot go
  below a one-storey building without going below a riser.
- **Removing the cap makes it worse, not better** (measured, third block of the probe): at
  `max_elevation_m = 99` the 15 m building needs 6 m of height to be caught instead of 4 m,
  because the tolerance is then free to grow to 0.3 x 16.5 + 0.3 = 5.25 m. The cap is currently
  *helping* catch buildings; it is not what excuses them at 8 m width.
- **Nothing catches the 50 m building** at any cap, because 50 m > 32.5 m.

So the design question is not "which value of `max_elevation_m`". Height is a property a roof and
a riser share, and the filter has no other property to look at.

## The prediction this makes about real buildings, stated before the run

On the Valongo AOI's `w40` outputs, over connected components of official ASPRS class-6 (building)
cells, with **survival** = the share of a component's cells whose CHM is below 0.5 m (the gate
result's own metric), **width** = twice the largest inscribed radius of the component (the largest
window it can hide from, by Euclidean distance transform), and **height** = median z of the
component's class-6 returns minus the median z of class-2 ground returns in a 10 m ring around it
(independent of our filter -- the official classification is never an input to it):

**P1.** Survivors are concentrated in two disjoint places: `width > 32.5 m` at any height, and
`height <= 3.5 m` at any width above ~5 m. **Refuted if** more than 20% of surviving building cells
sit in the box `5 m < width <= 32.5 m` **and** `height > 4.0 m`, which the mechanism says the filter
catches.

**P2.** Height alone is a poor separator: taking the best single height threshold over all
components, the balanced accuracy of "survives" against it is **below 0.75**. **Refuted if** some
height threshold separates survivors from caught at 0.75 or better -- in which case a cap change is
back on the table and this whole framing is wrong.

**P3.** Width alone is a good separator at the default: at shipped parameters, essentially every
building above the window scale survives. **Refuted if** the surviving share at default parameters
is below 90% for components with `width > 5 m`.

P1 and P3 can both be satisfied by a degenerate answer -- "almost everything survives" -- so P2 is
the one that carries the design, and P2 is the one that can come back and say the cap is enough.

A component whose ring holds fewer than 30 class-2 ground returns has no defensible height and is
counted in a declared *unmeasurable* row rather than dropped silently.

---

# What the run said, 2026-08-31

Six Valongo tiles read with the package's own `read_laz` onto the run's own grid
(`origin -39990/170990`, 3960 x 5960 cells of 0.5 m), against the `w40` and default outputs of the
gate session. 3,216 class-6 components, 4,738,087 class-6 cells; a height is measurable for 2,959
of them (92.0% of components, 100.0% of cells).

## The controls first

**C2 (must-fire) fired.** Class-5 high vegetation, through the identical instrument at the default
parameters: median CHM **6.34 m**, 6.0% below 0.5 m, against class-6's median **0.08 m** and 79.5%.
The instrument tells a canopy from a roof, so the rest of the numbers mean something.

**C1 (must-match) did NOT reproduce, and it is recorded as a failure rather than rounded off.** No
tile gives the gate result's 575,771 class-6 cells, on either population tried:

| tile | class-6 cells, AOI-clipped | unclipped |
|---|---:|---:|
| LO-160470 | 1,049,905 | 1,070,919 |
| LO-160471 | 764,572 | 779,603 |
| LO-161470 | 610,964 | 614,647 |
| LO-161471 | 648,937 | 653,095 |
| LO-162470 | 1,122,821 | 1,139,704 |
| LO-162471 | **540,893** | **558,442** |

The closest candidate is 3.1% below the recorded figure. The *finding* replicates at AOI scale
(79.5% of class-6 cells below 0.5 m against the recorded 79.8%; median 0.08 m against 0.06 m), so
the verdict is untouched — but the single-tile row in `docs/second-aoi-gate-result.md` is not
re-derivable from the method as it is described there, and that is now said out loud.

## P1 and P3 are refuted: the synthetic mechanism does not describe real buildings

**P3 REFUTED.** At the shipped default, components wider than 5 m keep **80.0%** of their CHM-valid
cells below 0.5 m, not the 90% the plateau probe implies (81.6% at >8 m, 84.4% at >15 m).

**P1 REFUTED.** Of the 1,115,056 building cells still flat at `w40`, **52.7%** sit in the box the
mechanism said gets caught (5 m < width <= 32.5 m and height > 4.0 m) — the bar was 20%. Only 18.7%
are in the too-wide bucket and 15.4% in the too-short one.

The probe was right about the arithmetic and wrong about the geometry. A real roof is not a flat
plateau on a flat plane: it sits in a block with courtyards and neighbours, it is pitched, and the
0.5 m cells along its edge hold ground returns too. Predicting real buildings from square plateaus
was a hypothesis, it was written down before the run, and the run refused it.

## P2 holds, and it is the one that carries the design

**P2 HOLDS.** Over 2,062 components with at least 50 CHM-valid cells and a measurable height (836
survive at `w40`, 1,226 are caught), the best single height threshold is 5.40 m and reaches a
balanced accuracy of **0.712** — below the 0.75 bar. For contrast the best single *width* threshold
(16.0 m) reaches **0.528**, which is barely above the coin.

So neither property this filter could key on separates a roof from the terrain it stands on. The
part of the T-E6r hypothesis that survives is the part that mattered: a one-storey roof and the
2.98 m terrace riser the cap exists to preserve are the same height, and the filter has nothing
else to look at.

## The gate result's `w40` improvement is substantially a denominator artefact

Cells holding class-6 returns, with the CHM-valid count carried beside every share:

| population | cells | CHM-valid, default | share < 0.5 m | CHM-valid, w40 | share < 0.5 m |
|---|---:|---:|---:|---:|---:|
| A: any class-6 return | 4,738,087 | 4,214,090 | 79.5% | 1,831,895 | 60.9% |
| B: class-6 and no class-2 | 4,270,425 | 3,746,514 | 89.4% | 1,364,851 | 81.5% |
| C: B, >= 2 cells inside the edge | 3,524,239 | 3,160,305 | **91.6%** | 1,104,883 | **87.1%** |

Row A is the gate result's population and reproduces its numbers. But **57% of building cells lose
their CHM entirely at `w40`**, so the recorded 79.8% and 61.8% are computed over populations that
differ by more than a factor of two. On the population that cannot be argued with — row C, roof
interior, where no ground return shares the cell — widening the window moves the defect **91.6% to
87.1%** while destroying two thirds of the coverage over buildings. It does not remove buildings.
It converts a minority of them from wrong to absent.

## The defect, stated as a claim rather than a symptom

The README says *"the claim is the `basis` band and the record"*. So the question is not what the
CHM looks like over a roof; it is what the product **says** about those cells. `BASIS_MEASURED` is
the strongest claim it makes: our filter called this ground and it holds returns.

| population | cells | measured | interpolated | undetermined |
|---|---:|---:|---:|---:|
| **roof interior** (Valongo, default) | 3,524,239 | **89.7%** | 10.2% | 0.1% |
| control: canopy with no ground return | 2,493,967 | 33.9% | 65.5% | 0.7% |
| control: plain ground | 12,062,527 | 100.0% | 0.0% | 0.0% |
| roof interior (Valongo, `w40`) | 3,524,239 | 31.4% | 32.5% | 36.2% |

The two controls bracket it: plain ground is claimed measured 100.0% of the time and is, canopy is
mostly declared invented, and the roof interior reads like plain ground. **3.16 million cells —
13.7% of this AOI — carry the product's strongest claim over a roof.**

The same instrument on the **shipped** Sistelo run (0.4.2), which is the piece about to be
published:

| population | cells | share of AOI | measured | interpolated | undetermined |
|---|---:|---:|---:|---:|---:|
| roof interior | 86,759 | 0.55% | **77.2%** | 22.3% | 0.5% |
| control: plain ground | 4,126,962 | 26.32% | 99.9% | 0.1% | 0.0% |

About 67,000 cells, 0.43% of the published AOI. Real, nameable, and two orders of magnitude smaller
than Valongo — which is the whole reason a site chosen for what it shows could hide it.

## What this rules out

- **Not `max_elevation_m`.** Height does not separate (0.712), and lowering the cap below a
  one-storey roof goes below the verified 2.98 m riser. Raising it makes buildings *harder* to
  catch, measured on the probe above.
- **Not `max_window_m`.** Width separates worse than height (0.528), and the one setting tested
  buys 4.5 points on the honest population at the cost of two thirds of the coverage.
- **Not the official classification as an input.** It is what `agreement()` compares against; using
  it to decide cells would make the comparison a tautology and remove the one honest result the
  piece has. It is used above only to *define the population being audited*, which is the role it
  already has.

---

# Would SMRF do better? Measured, 2026-08-31

The operator's ruling was to measure before choosing. PDAL 2.10.2 from conda-forge, `filters.smrf`
**out of the box** (only `ignore: Classification[7:7]`, matching the noise exclusion this pipeline
already does), on the same six Valongo tiles and the same grid.

**Controls first, because a filter that did not run would look like a very good one.**
SMRF genuinely reclassifies: on LO-162471 it moves 2,014,732 returns into ground that DGT calls
non-ground and 90,837 the other way, so the output is its verdict and not the delivery's labels
read back. Its `returns` default is `[last, only]` and it passes the rest through with their
original class — those are excluded, and they are negligible (7,345 class-2 points against
100,326,647 judged, 0.007%).

## On buildings

Cell counted as ground if it holds at least one ground return — the same rule `agreement()` already
uses for the official classification. Populations defined exactly as above, from the delivery's
classification, which decides no cell in either filter.

| population | cells | **ours** published as measured | **SMRF** would be ground |
|---|---:|---:|---:|
| **roof interior** (class 6, no class 2) | 3,524,239 | **89.7%** | **16.1%** |
| control: canopy, no ground return | 2,493,967 | 33.9% | 19.5% |
| control: plain ground | 12,062,527 | 100.0% | **99.4%** |

Falsely-measured roof cells fall from **3,160,305 to 566,299** — 5.6x — and the plain-ground
control costs 0.6 points. That is not a trade between ground coverage and building rejection; it is
73.6 points on roofs for 0.6 on ground.

## On terraces — the symmetric risk, and the one that could have killed it

Our filter over-preserves. A filter that over-cuts would destroy the artefact instead, and a
recommendation that skipped this measurement would rest on exactly what it most needed. The
documented 150 m window around the **tallest verified riser (2.98 m)**, tile LO-179557:

- of the cells our filter calls measured ground, SMRF has ground in **91.8%**;
- restricted to cells sitting on a real vertical step in 3.5 m: **90.7%** at > 1.5 m,
  **89.3%** at > 2.0 m, **86.5%** at > 2.5 m — the steeper the cell, the more SMRF drops, but it
  keeps the large majority of them;
- where both call a cell ground, the surfaces are the same to within measurement noise (46,449
  cells, median difference **+0.000 m**, 0.03% differing by more than 0.5 m) — which is the
  consistency control on my own construction of the SMRF surface.

**SMRF does not eat the terraces.** It costs about one in eight of the steepest cells, which become
interpolated or undetermined rather than measured — a real cost, named rather than discovered
later.

*Not comparable, and left out deliberately:* a local-relief comparison between the two surfaces
runs over different denominators (our published DTM is filled, the SMRF surface here is only the
cells holding ground returns), so the "cells above 2 m of local relief" counts are not a like
comparison and no conclusion is drawn from them.

---

# The ruling, 2026-08-31

**SMRF is implemented in this repository, in Python, citing Pingel et al. (2013); PDAL stays a
development-only dependency, as the reference the implementation is validated against.**

The decision was made after the measurement, not before it, and the measurement is what moved it:
the option this session opened with — keep the filter and add a bespoke refusal guard — is
dominated once a published algorithm is measured to fix the defect 5.6x without eating the
terraces. Choosing a re-implementation over a runtime dependency rests on one assumption, stated so
it can be attacked: that an install a reader can run without conda is worth roughly two sessions of
build. If that stops being true, the runtime dependency is strictly cheaper.

What this buys beyond the fix: the README's weakest sentence today is *"SMRF beats this
implementation by 2.0 accuracy points"*. A re-implementation validated cell-for-cell against
PDAL's own SMRF replaces it with a measured agreement — a stronger artefact than either the
current filter or a shelled-out call.

**Not to be done, each ruled out by measurement above:** tuning `max_elevation_m` or
`max_window_m`; using the delivery's classification as an input to the filter; and adopting SMRF
without publishing what it costs at the steepest cells.

**Still open, and it is true today regardless of which filter ships:** the published Sistelo record
claims `BASIS_MEASURED` over 77.2% of 86,759 roof cells, and none of its ten `known_limitations`
names it.

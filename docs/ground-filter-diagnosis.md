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

# The sharp-step population — what would count as passing, fixed before the first run

**Written and committed before the sharp-step population was computed once on real data.** The
result goes in `docs/sharp-step-result.md`, whichever way it lands.

## Why this document exists

`docs/p4-terrace-result.md` recorded, after its verdict was in, that `step_magnitude` is a range
in a window and therefore cannot tell a terrace riser from a smooth slope steep enough to span the
same range. It measured the size of that confound — 1.2% of the gate population near-planar,
92.1% retention on the wall-like cells against an 80.0% bound — and declared that a better
population, "range plus a curvature or planarity term", was "available as a **new dated
pre-registration**, not an edit to this one".

This is that document. **P4's population remains the population of record for P4.** Nothing here
edits `docs/p4-terrace-preregistration.md` or `docs/p4-terrace-result.md`, and no result here
changes P4's verdict.

## What this population cannot be called, and why it is `sharp-step`

The obvious name for it is *riser-only*, and the name is unavailable. A riser of 2.6 m spread
across the `max_riser_width = 3.0 m` that `docs/riser-measurement.md` admits is **exactly planar**
inside a 3.5 m window. Measured, by `scripts/calibrate_sharp_step.py`:

    riser width   0.5 m   1.0 m   1.5 m   2.0 m   2.5 m   3.0 m
    residual      0.455   0.455   0.270   0.208   0.083   0.000

So there is no threshold that keeps every riser the site's own instrument permits and rejects
every ramp. Any threshold above zero excludes the widest permitted risers; the last width that
survives `R = 0.30 m` on a 0.5 m grid is 1.0 m. The population is therefore named for what it is:
steps that are **sharp** in a 3.5 m window.

This is a limitation of the **instrument**, not a defect of the threshold, and it is the reason
this document does not claim to have built a riser detector. A riser-shaped term — window
bimodality, or the tread-and-riser profile detector `scripts/measure_risers.py` already runs —
is what a later document would need. It is not attempted here.

## The surface the step is measured on, and why it is not ours

`min_z_ground_asprs` — the per-cell minimum of the delivery's own ASPRS class-2 returns. The
reason is `docs/p4-terrace-preregistration.md`'s, unchanged: `max_elevation_m` is the parameter
that decides whether a riser survives our filter, so a surface shaped by our filter would select
the population by the very thing being audited.

## The operation, both terms

Given a cell `c` on the 0.5 m grid:

**The range term** (unchanged from P4, `step_magnitude`):

- take the 7 × 7 cell window centred on `c` — 3.5 m across;
- over the cells of that window where `min_z_ground_asprs` is finite, `step(c) = max − min`;
- `step(c)` is **undefined**, and `c` is excluded, where the window holds fewer than **2** finite
  cells, or where `c` lies within 3 cells of the grid border.

**The planarity term** (`plane_residual`):

- fit a least-squares plane to the observed cells of the same 7 × 7 window, in metres;
- `residual(c)` is the RMS departure of those cells from that plane;
- `residual(c)` is **undefined**, and `c` is excluded, where the window holds fewer than **4**
  finite cells. A plane has three parameters; three points fit it exactly and have no residual.

The two undefined cases differ — a range needs two points, a plane four — so a cell can be a
candidate on the range term and carry no residual at all. **Such a cell is excluded.** A window we
could not measure is not evidence of a step, and sparsity does not get to choose the population.

## The threshold, and what it is anchored to

`R = 0.30 m`.

**The window it has to fit in**, from `scripts/calibrate_sharp_step.py`, all synthetic:

- **the step floor** — the smallest residual a clean 2.5 m step can give, minimised over sub-cell
  boundary offsets: **0.4374 m**. Evaluated at the gate height because the candidate rule is
  strict above 2.5 m, which makes it the infimum over candidate steps;
- **the noise ceiling** — the median residual of a planar ramp at 35° holding no step, under
  Gaussian noise: **0.097 m** at σ = 0.10, **0.195 m** at σ = 0.20, **0.289 m** at σ = 0.30;
- **the ramp control** — planar surfaces at 25°, 35°, 45° and 60°, axis-aligned and diagonal, all
  read **0.000 m**. A non-zero reading anywhere there would mean the statistic itself is wrong.

**The anchor.** 0.30 m is the top of the 0.2–0.3 m LiDAR measurement-error band this repository
already uses: `elevation_threshold_m` is set at its edge and `smrf_threshold` is judged as sitting
above it (`CALIBRATIONS.md`, rows `smrf_threshold` and `elevation_threshold_m`).

**The anchor's weakness, stated plainly.** That band is a convention traced to Zhang et al. 2003.
It is **not** a measured property of the DGT delivery, which publishes no vertical accuracy
anywhere in this tree. So the derivation below is a bound argued from a borrowed constant, and a
measured accuracy figure for this delivery would supersede it.

**And the window is narrower than the anchor makes it look.** At the top of the assumed band the
usable range runs 0.289 → 0.437 m, and `R = 0.30` sits at its lower edge: 0.137 m of clearance
below the quietest real step, and **0.011 m** above what pure noise at σ = 0.30 m manufactures at
the median. `R` is conservative for retaining steps and thin against noise at the worst end of the
band. That is the honest reading, and it is stated here rather than after the run.

**A coincidence, declared.** `residual >= 0.30 m` is also a row in `docs/p4-terrace-result.md`'s
band table. The derivation above is prior to and independent of that table — it is geometry and an
error band, not a fit to the P4 result — but a reader deserves to know the number is not new.

## Instrument parameters

These shape what the instrument can see, so they are declared here. **They are not production
thresholds; nothing in `src/` reads them.**

| Parameter | Value | Why |
|---|---|---|
| `window_cells` | 7 (3.5 m at 0.5 m cells) | P4's window, unchanged, so the two legs are comparable |
| `min_finite` | 2 | A range needs two points. P4's value |
| `step_threshold_m` | 2.5 m, strict | P4's gate height. Strict, so a surface whose range is exactly 2.5 m is not a candidate |
| `residual_min_m` (`R`) | 0.30 m | Derived above: above the noise curve, below the step floor, anchored to the 0.2–0.3 m band |
| plane minimum cells | 4 | Three points fit a plane exactly and have no residual |

## The populations

**Zone Z**, from `docs/riser-measurement.md` verbatim: the square 800 m × 800 m centred on
(−20000, 256000), i.e. x ∈ [−20400, −19600], y ∈ [255600, 256400], EPSG:3763.

- **`S1`** — Zone Z cells where `step` is defined and `step > 2.5 m`. This is the P4-shaped
  population, evaluated over Zone Z.
- **`S2`** — the cells of `S1` where `residual` is defined and `residual >= 0.30 m`. This is the
  sharp-step population.

**The two legs are nested, not independent, and this is declared before the run.** The P4 window
is `examples/sistelo-sample/aoi.geojson`, bounds x ∈ [−20210, −20060], y ∈ [256245, 256395]
(EPSG:3763) — entirely inside Zone Z. Zone Z is about 28 times its area, so most of Zone Z is new
ground, but the P4 window's cells are counted in `S1` and `S2` as well.

## The predicates

All three gate. **G1's n is 5, and that is small** — five locations is not a sample, it is a
must-fire list, and it can only refute, never confirm.

**G1 — must-fire, real, blind.** Every one of the five real steps below must be in `S2`, at its
own cell or within 2.0 m of it. Coordinates from `docs/figures/riser/report.json` (`top_clusters`,
the tracked artefact behind `docs/riser-measurement.md`); the terrace riser from
`docs/riser-measurement.md`.

| # | x | y | H | What it is |
|---|---|---|---|---|
| terrace | −20132.8 | 256319.2 | 2.98 m | The tallest **verified terrace riser** |
| rank 4 | −19899.25 | 255961.75 | 5.26 m | Built — road/retaining-wall line |
| rank 8 | −19916.75 | 256173.75 | 4.78 m | Built — churchyard wall |
| rank 10 | −20007.75 | 255932.25 | 4.72 m | Gully/lane edge |
| rank 11 | −19905.25 | 255974.25 | 4.64 m | Built — road/retaining-wall line |

**Ranks 1, 2, 3, 5, 6, 7, 9 and 12 are excluded, and the reason is given:**
`docs/riser-measurement.md` labels them *unsupported* (1, 2, 3, 5, 12 — one or two returns carry
the step) or *built/unsupported* (6, 7, 9). A must-fire list may not contain a step whose own
source document says the evidence for it is one or two returns.

A built wall and a gully edge **are real steps** and belong in a sharp-step population. Excluding
them would make this a terrace-versus-wall detector, which is a different and harder instrument
than the one being pre-registered.

**G2 — must-not-fire, synthetic.** For planar ramps at 31°, 35°, 40°, 45°, 50° and 60°,
axis-aligned and diagonal: `S1` must be **non-empty** and `S2` must be **empty**. **Both halves
gate.** The first is not decoration: without it, an instrument that selects nothing passes the
second one perfectly.

**G3 — separation, blind.** The residual at each of G1's five locations must exceed the **median**
residual over `S1`. This one can fail, and it is the predicate with real information in it: it
asks whether the five known steps are more step-like than the typical cell the range term selects.

## Reported beside the predicates, with nothing riding on them

- `|S1|`, `|S2|`, and the count removed;
- the decomposition of what was removed: near-planar (`residual < 0.10 m`) and intermediate
  (`0.10 <= residual < 0.30 m`);
- the residual percentiles over `S1`;
- SMRF's retention on `S1` and on `S2`.

## The building caveat, stated before the run

Zone Z holds the village core, the church and built walls. SMRF exists to cut buildings. So a
**lower** SMRF retention on `S2` than on `S1` would be SMRF working, not failing — `S2` is
enriched in exactly the sharp built edges SMRF is supposed to remove.

**This is why no retention bound gates in this document.** Any number that would be read as
"SMRF did well" or "SMRF did badly" is reported, not gated.

The P4 window's retention is a separate, **explicitly non-blind** leg: its answer is already
published in `docs/p4-terrace-result.md`'s band table — 95.1% over the gate population and 94.2%
at `residual >= 0.30 m` — so it can confirm the implementation reproduces a known figure, and it
can do nothing else. It is not evidence about this population.

## On failure

The result is recorded in `docs/sharp-step-result.md` and the work stops. **`R` is not moved
toward a bound afterwards.** Any later change to the threshold, the predicates or the populations
is a new dated entry, never an edit to this one.

## The commands

    python scripts/calibrate_sharp_step.py
    python scripts/measure_sharp_step.py --reference <zone-z-cache>.npz

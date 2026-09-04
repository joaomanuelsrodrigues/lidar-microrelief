# The sharp-step population over Zone Z — the result

**2026-09-04. PASS.** All three predicates of `docs/sharp-step-preregistration.md` hold. That
document was committed before this ran once on real data, and nothing in it has been edited since.

    G1  must-fire, 5 of 5 supported real steps in S2
    G2  must-not-fire, 10 of 12 planar ramps reached S1 and 0 entered S2
    G3  separation, 5 of 5 residuals above the S1 median

## What was measured

Zone Z, 1600 × 1600 cells at 0.5 m, from the four Sistelo tiles named in
`docs/riser-measurement.md`. **1,291,705** cells carry an official-ground return.

    S1   step > 2.5 m                        307,381
    S2   and residual >= 0.30 m              173,784
    removed                                  133,597   (43.5%)

**Forty-three per cent of the P4-shaped population is not a sharp step.** What was removed, of
`S1`'s 307,381 cells:

    near-planar    residual <  0.10 m          7,044
    intermediate   0.10 <= r < 0.30 m        123,415
    no residual    under 4 observed cells       3,138

The three partition the removed cells exactly. Only the first two are drawn from the 304,243
whose residual could be computed; the third is the rest of `S1`, so it does not share that
denominator.

Residual percentiles over `S1`:

    p10  0.141 m     p25  0.201 m     p50  0.349 m     p75  0.544 m     p90  0.695 m

The near-planar share over Zone Z is **2.3%** of the computable cells, against the **1.2%**
`docs/p4-terrace-result.md` measured on the 150 m window. Those two are not independent — the P4
window lies inside Zone Z — and no claim is made about the difference.

The bulk of what `R` removes is not the ramp-like tail. It is the **intermediate** band, 123,415
cells reading between 0.10 and 0.30 m: neither planar nor sharp. Whether those are wide risers,
degraded walls, noise, or ordinary broken ground is **not measured here**, and the width curve in
the pre-registration says the instrument cannot separate the first of those from a plane.

## The predicates

**G1 — must-fire, real, blind. PASS, 5 of 5.** Each of the five supported real steps is in `S2`,
at its own cell or within 2.0 m.

| Step | cell (row, col) | residual |
|---|---|---|
| terrace riser 2.98 m | (161, 534) | 0.783 m |
| built wall (rank 4) | (876, 1001) | 1.696 m |
| churchyard wall (rank 8) | (452, 966) | 1.050 m |
| gully/lane edge (rank 10) | (935, 784) | 1.205 m |
| built wall (rank 11) | (851, 989) | 1.107 m |

**n = 5, and that is small.** Five locations is a must-fire list, not a sample: it can refute the
instrument and it cannot confirm it. The pre-registration says so, before the result was known.

**G2 — must-not-fire, synthetic. PASS.** Of twelve planar ramps holding no step — 31°, 35°, 40°,
45°, 50° and 60°, axis-aligned and diagonal — **10 reached `S1`** and **0 entered `S2`**. Both
halves are required, and the first is the one that matters: an instrument that selected nothing
would satisfy the second perfectly.

**G3 — separation, blind. PASS, 5 of 5.** The `S1` median residual is **0.349 m**. Every one of
the five locations reads well above it, the lowest being the terrace riser at 0.783 m — 2.2× the
median. This is the predicate that carried real information: it could have failed, and it asks
whether the known steps are more step-like than the typical cell the range term selects.

## Reported, gating nothing

SMRF's retention: **`S1` 78.8%**, **`S2` 83.7%**.

**This is not the direction the pre-registration anticipated.** That document's building caveat
exists to stop a *lower* retention on `S2` being read as SMRF failing — Zone Z holds the village
core and the church, `S2` is enriched in sharp built edges, and SMRF exists to cut buildings.
The measurement went the other way: `S2` is retained **more**, by 4.9 points.

No mechanism for that was measured, and none is offered here. What can be said is that the caveat
did its job in the only way that matters — it made the number un-gateable in advance, so the
result is reported whichever way it landed. A wrong anticipation about a figure nothing rides on
is a wrong anticipation, not a failed predicate.

## Which figures were foreseeable, and which were not

- `S1` and `S2` over Zone Z, the residual distribution, and the 43.5% removed are **new**. Zone Z
  is about 28 times the P4 window's area and has never been measured this way.
- **The P4-window leg is not blind** and is not run here. Its answer is already bracketed by
  `docs/p4-terrace-result.md`'s band table — 95.1% retention over the gate population and 94.2% at
  `residual >= 0.30 m` — so it could only confirm that an implementation reproduces a published
  number. It is dropped, and named as dropped: PDAL 2.10.2 is not installed on this machine and
  the reference `.npz` it needs died with a scratchpad. The branch is complete without it.

## What this does not establish

- **It is a sharp-step population, not a riser population.** A riser spread across the 3.0 m
  `docs/riser-measurement.md` admits is exactly planar in a 3.5 m window and is not in `S2`. The
  width curve in the pre-registration gives the whole of it.
- **G1 cannot confirm.** Four of its five members are a churchyard wall, two stretches of
  retaining-wall line and a gully edge. They are real steps, which is why they belong; they are
  not terraces, and this instrument does not claim to tell the two apart.
- **`R = 0.30 m` is anchored to a borrowed constant.** The 0.2–0.3 m band is a convention traced
  to Zhang et al. 2003, not a measured property of the DGT delivery. At the top of that band the
  threshold clears the noise curve by 0.011 m.
- Nothing here changes P4's verdict, and `R` has not moved.

## The commands

    PYTHONPATH=src .venv/bin/python scripts/measure_risers.py build \
        --aoi aoi/aoi.geojson --laz ~/data/dgt-laz-sistelo \
        --cache ~/data/microrelief-cache/zone-z-surface.npz
    PYTHONPATH=src .venv/bin/python scripts/measure_sharp_step.py \
        --reference ~/data/microrelief-cache/zone-z-surface.npz

The build added, in order, `LO-179556`, `LO-179557`, `LO-180556` and `LO-180557` of `07-2025`, and
produced a 3960 × 3960 grid. `docs/riser-measurement.md`'s own run read `~/data/dgt-laz`, which
today holds those four plus six Valongo tiles; the AOI clips them, but that the two directories
agree was **not measured**, and `build` prints no `n_outside`, so this run cannot report one.

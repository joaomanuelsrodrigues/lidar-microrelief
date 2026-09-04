# The sharp-step population over Zone Z — the result

**2026-09-04. PASS.** All three predicates of `docs/sharp-step-preregistration.md` hold. That
document was committed before this ran once on real data, and nothing in it has been edited since.

    G1  must-fire, 5 of 5 supported real steps in S2
    G2  must-not-fire, 10 of the 10 ramps geometry permits reached S1, 0 entered S2
    G3  separation, 5 of 5 residuals above the S1 median

**Five corrections to the pre-registration are recorded below**, all found by an adversarial
review of the code after the run. That document is dated and is not edited; this is where its
errors are named. None of them moves `R`, and none changes the verdict.

## What was measured

Zone Z, 1600 × 1600 cells at 0.5 m, from the four Sistelo tiles named in
`docs/riser-measurement.md`. **1,291,705** cells carry an official-ground return.

    S1   step > 2.5 m                        307,381
    S2   and residual >= 0.30 m              173,784
    removed                                  133,597   (43.5%)

**Forty-three per cent of `S1` is not a sharp step.** What was removed, of `S1`'s 307,381 cells:

    near-planar    residual <  0.10 m          7,044
    intermediate   0.10 <= r < 0.30 m        123,415
    no residual    under 4 observed cells       3,138

The three partition the removed cells exactly. Only the first two are drawn from the 304,243
whose residual could be computed; the third is the rest of `S1`, so it does not share that
denominator — and the two are not the same claim: **42.4%** of `S1` departs from a plane by less
than 0.30 m, while the other 1.1 points were removed as *unmeasurable*, not as planar.

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
45°, 50° and 60°, axis-aligned and diagonal — **10 of the 10 that geometry permits reached `S1`**
and **0 entered `S2`**. Both halves are required, and the first is the one that matters: an
instrument that selected nothing would satisfy the second perfectly.

**Correction 1, and it is the serious one.** The pre-registration says `S1` "must be **non-empty**"
for those ramps. Read per ramp, that is **unsatisfiable by geometry**: a 7-cell window separates
cells by 3.0 m along an axis, so an axis-aligned ramp needs 39.8° to span 2.5 m, and 31° and 35°
axis-aligned cannot — a number `scripts/measure_ramp_confound.py` already printed before this
branch began. The first implementation hid that behind `reached_s1 >= 8`, a constant that appears
in no document and was written *after* the pre-registration was committed. The rule is now derived
from geometry — every permitted ramp must fire, and `permitted == 0` fails — so a regression that
kills one of the ten is caught, which `>= 8` silently accepted. The measured outcome is the same
under either reading.

**G3 — separation, blind. PASS, 5 of 5.** The `S1` median residual is **0.349 m**. Every one of
the five locations reads well above it, the lowest being the terrace riser at 0.783 m — 2.2× the
median. This is the predicate that carried real information: it could have failed, and it asks
whether the known steps are more step-like than the typical cell the range term selects.

## Reported, gating nothing

SMRF's retention, over four populations:

    S1                       307,381    SMRF 78.8%
    S2                       173,784    SMRF 83.7%
    S1 & measured basis      251,030    SMRF 94.5%
    S2 & measured basis      152,049    SMRF 93.7%

**Correction 2: the surprise in the first two lines was an artefact of the population.** Without
the basis term, `S2` is retained 4.9 points *more* than `S1` — the opposite of what the
pre-registration's building caveat anticipates, since `S2` is enriched in the sharp built edges
SMRF exists to cut. Adding P4's measured-basis term reverses it: 94.5% against 93.7%, `S2`
**lower**, which is the anticipated direction. The first reading was the omission of the basis
term speaking, not SMRF.

The caveat did its job in the only way that matters: it made the number un-gateable in advance, so
whichever way it landed it is reported rather than explained away.

## Which figures were foreseeable, and which were not

- `S1` and `S2` over Zone Z, the residual distribution, and the 43.5% removed are **new**. Zone Z
  is about 28 times the P4 window's area and has never been measured this way.
- **The P4-window leg is not blind**, and it was run. Its own section is below.

## The P4-window leg — explicitly not blind

Run on the 150 m window of `examples/sistelo-sample/aoi.geojson`, against PDAL **2.10.2
(git-version: e8618b)** — the version `docs/p4-terrace-result.md` names. The plan expected this
leg to be undoable; it was not, and it turned out to carry the most useful finding on the branch.

**The implementation reproduces both published rows exactly**, printed by the instrument itself:

    S1                         9,525    SMRF 76.7%    PDAL 76.7%
    S2                         5,652    SMRF 83.1%    PDAL 83.0%
    S1 & measured basis        7,625    SMRF 95.1%    PDAL 95.1%
    S2 & measured basis        4,954    SMRF 94.2%    PDAL 94.1%

`docs/p4-terrace-result.md` publishes 7,625 / 95.1% / 95.1% for the gate population and
4,954 / 94.2% / 94.1% for its `residual >= 0.30 m` row. Six figures, all returned.

**Correction 3: the pre-registered `S1` is not P4's population**, and calling it "the P4-shaped
population" in that document oversells the correspondence. P4's gate is
`measured & defined & step > 2.5 m`; `S1` is `defined & step > 2.5 m`. The 1,900-cell difference
is that term alone, and it is worth **18.4 points** of retention on this window.

The decomposition is computed by `scripts/measure_sharp_step.py` and not by a probe. An earlier
version of this section carried figures from an ad-hoc run with no artefact on the branch — the
failure this repository has now recorded four times, and the reason `scripts/measure_ramp_confound.py`
exists at all.

**G1 and G3 are not evaluable on this window.** Four of the five verified steps lie outside a
150 m frame. The instrument reports them as `n/a — outside this cache's extent` and declares G1
NOT EVALUABLE, because a question the cache cannot answer is not a failed predicate. Only the
terrace riser is in frame, and it passes both: in `S2` at (151, 154), residual 0.783 m against an
`S1` median of 0.356 m.

## What this does not establish

- **It is a sharp-step population, not a riser population.** A riser spread across the 3.0 m
  `docs/riser-measurement.md` admits *can be* exactly planar in a 3.5 m window and is not in `S2`.

  **Correction 4: the width curve in the pre-registration is computed at one sub-cell alignment**,
  while the step floor printed beside it sweeps eleven — two curves in one table under different
  assumptions, and the claims drawn from it inherited the difference. Swept over the same offsets:

        width    centred      min      max     at R = 0.30
        0.5 m      0.455    0.455    0.620     in at every offset
        1.0 m      0.455    0.389    0.484     in at every offset
        1.5 m      0.270    0.270    0.341     depends on the offset
        2.0 m      0.208    0.190    0.273     OUT at every offset
        2.5 m      0.083    0.083    0.173     OUT at every offset
        3.0 m      0.000    0.000    0.109     OUT at every offset

  So "a 3.0 m riser is **exactly** planar" and "the last width that survives is 1.0 m" are
  properties of the centred alignment, not of the width. The defensible statement is the table:
  **up to 1.0 m wide a riser is in at every alignment, 1.5 m straddles `R`, and 2.0 m and wider
  are out at every alignment.** The naming argument survives — there is still no threshold that
  keeps every permitted riser — and it survives on a wider, measured basis than the one written.

- **Correction 5, small:** the pre-registration calls 0.4374 m "the infimum over candidate steps".
  Candidate steps include wide risers, which the table above shows reading 0.083 and 0.000. It is
  the infimum over *sharp* steps at the gate height, which is the distinction that section exists
  to draw.
- **G1 cannot confirm.** Four of its five members are a churchyard wall, two stretches of
  retaining-wall line and a gully edge. They are real steps, which is why they belong; they are
  not terraces, and this instrument does not claim to tell the two apart.
- **`R = 0.30 m` is anchored to a borrowed constant.** The 0.2–0.3 m band is a convention traced
  to Zhang et al. 2003, not a measured property of the DGT delivery. At the top of that band the
  threshold clears the noise curve by 0.011 m.
- **The Zone Z retention is not comparable to the published band table**, for the reason the P4
  leg measures above. Nothing on this branch compares them.
- Nothing here changes P4's verdict, and `R` has not moved.

## The commands

    PYTHONPATH=src .venv/bin/python scripts/measure_risers.py build \
        --aoi aoi/aoi.geojson --laz ~/data/dgt-laz-sistelo \
        --cache ~/data/microrelief-cache/zone-z-surface.npz
    PYTHONPATH=src .venv/bin/python scripts/measure_sharp_step.py \
        --reference ~/data/microrelief-cache/zone-z-surface.npz

and, for the non-blind leg:

    ~/bin/micromamba create -y -p ~/micromamba/envs/pdal -c conda-forge pdal=2.10.2
    ~/micromamba/envs/pdal/bin/pdal pipeline docs/p4-reference-pipeline.json \
        --readers.las.filename=$HOME/data/dgt-laz-sistelo/LO-179557-07-2025.laz \
        --writers.las.filename=$HOME/data/microrelief-cache/LO-179557-smrf.laz
    PYTHONPATH=src .venv/bin/python scripts/compare_ground_filters.py reference \
        --tiles ~/data/dgt-laz-p4 --smrf ~/data/microrelief-cache \
        --aoi examples/sistelo-sample/aoi.geojson \
        --out ~/data/microrelief-cache/p4-reference.npz --pipeline docs/p4-reference-pipeline.json
    PYTHONPATH=src .venv/bin/python scripts/measure_sharp_step.py \
        --reference ~/data/microrelief-cache/p4-reference.npz

`--tiles` names a directory holding only `LO-179557`, the tile the 150 m window is cut from:
`reference` requires an SMRF output for every tile it is given, and only that one was produced.

The build added, in order, `LO-179556`, `LO-179557`, `LO-180556` and `LO-180557` of `07-2025`, and
produced a 3960 × 3960 grid. `docs/riser-measurement.md`'s own run read `~/data/dgt-laz`, which
today holds those four plus six Valongo tiles; the AOI clips them, but that the two directories
agree was **not measured**, and `build` prints no `n_outside`, so this run cannot report one.

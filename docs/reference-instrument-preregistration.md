# Pre-registering what counts as replication, before the instrument is built

**2026-09-02.** The ruling of 2026-08-31 (`docs/ground-filter-diagnosis.md`) rests on a table: our
filter publishes `MEASURED` over 89.7% of roof-interior cells where SMRF would find ground in
16.1%, at a cost of 0.6 points on plain ground, while keeping 86.5% of the cells on a step above
2.5 m. That table decided which algorithm this repository implements.

**It has no surviving artefact.** The script that produced it was never in this tree — the gap is
declared in `docs/live-smoke.md` — and the two things it ran against are gone with the session
scratchpad that held them: the PDAL environment and the SMRF-classified tiles. What survives is
the source data (six Valongo tiles, sha256-checkable) and prose describing a method.

So building the instrument is not bookkeeping. It is the first independent test of the numbers
that carried the ruling, and it can fail. This file fixes what failure means, before any of it
runs, so that a disagreement cannot be absorbed afterwards into a story that still sounds right.

## What is being replicated

The three-population table of `docs/ground-filter-diagnosis.md` §"On buildings", and the terrace
figures of §"On terraces", recomputed from the six tiles in `aoi/valongo.geojson` on the same grid
the pipeline uses.

Populations are defined from the delivery's ASPRS classification, which decides no cell in either
filter — it names the population being audited, the role it already has in `agreement()`:

| population | recorded cells | ours, measured | SMRF, ground |
|---|---:|---:|---:|
| roof interior (class 6, no class 2) | 3,524,239 | 89.7% | 16.1% |
| control: canopy (class 5, no ground return) | 2,493,967 | 33.9% | 19.5% |
| control: plain ground | 12,062,527 | 100.0% | 99.4% |

Derived figure, recorded: falsely-measured roof cells **3,160,305 → 566,299**.

## The controls, which run before the comparison and can stop it

**C1 — the reference environment.** `pdal --version` must read `2.10.2 (git-version: e8618b)`,
taken from the binary. *Verified before this file was committed: it matches the recorded string
exactly, so a version drift is excluded as an explanation for any difference below.*

**C2 — SMRF genuinely reclassifies.** On tile LO-162471, SMRF must move **2,014,732** returns into
ground that the delivery calls non-ground, and **90,837** the other way. This is the recorded
control, and here it does double duty: it is also the test of my reconstruction of *which points
SMRF judged*. PDAL's `returns` default is `[last, only]` and `only_ground` is false, so judged
points come back as class 1 or 2 and unjudged points keep their delivery class — which makes a
passed-through class-2 point indistinguishable from a judged ground point by class alone. The
judged mask is therefore derived from return numbers, and C2 is what says the derivation is right.

**C3 — the judged mask has both arms.** Every point whose output class differs from its delivery
class must fall inside the mask (no judged point outside it), and the count of passed-through
class-2 points must be **7,345** against **100,326,647** judged. A mask that admits everything
passes the first arm trivially; the second arm is what makes it a discriminator.

## The verdict rule

**PASS** — all three population sizes reproduce **exactly**, and all six percentages reproduce to
within **±0.1 point** (the precision at which they were published). Cell counts are deterministic
given the same tiles, grid and population rules; there is no sampling here, so an exact match is
the honest bar and a tolerance on them would only hide a defect.

**FAIL** — any population size differs, or any percentage differs by more than 0.1 point. A FAIL
is a finding about the evidence base of the ruling, not only about this script. It is recorded
with both numbers side by side, and the ruling is re-read against the corrected table before any
line of SMRF is written.

**INCONCLUSIVE** — C2 or C3 does not reproduce. Then the reference is not being built the way the recorded table
was built, and the comparison is not measuring what it claims to; no verdict is drawn on the table
from a reference that failed its own control.

Distinguishing the three matters more than which one lands: "0 differences" produced by an
instrument that never ran the comparison would look exactly like a PASS, which is why C2 and C3
are separate, numeric, and must speak.

## What this pre-registration does not cover

The terrace figures (91.8% / 90.7% / 89.3% / 86.5%, and the +0.000 m median agreement over 46,449
cells) depend on the 150 m window around the tallest verified riser and on our filter's own ground
decision. They are replicated on the same PASS/FAIL rule, but they are reported separately: they
were the measurement that could have killed the ruling, so they are not folded into a single
aggregate verdict with the building numbers.

Nothing here says the SMRF re-implementation is correct. This instrument is the acceptance check
that implementation will be measured against; the pre-registration for *that* comparison is a
separate document, written before that build runs.

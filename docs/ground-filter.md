# The ground filter

Every published cell is re-derived from the raw returns rather than inherited from the delivery's
own classification. This page says which filter does that, why it is the one running, and how it
scores beside the alternatives. The headline figures for the shipped run are in the README; the
dated records that produced them are linked from each section.

## What runs today

The Simple Morphological Filter (Pingel et al., 2013), over the per-cell minimum surface, in this
package's own implementation. It is written from PDAL 2.10.2's `filters/SMRFilter.cpp` read line by
line, because that build is what it is validated against cell for cell. Where the source and the
paper disagree, `smrf.py`'s own header names the disagreement rather than silently picking a side.

The build was accepted against PDAL's, cell by cell over a six-tile area, at a Cohen's kappa of
0.991, and against the terraces before it was wired in
([`smrf-build-result.md`](smrf-build-result.md), [`p4-terrace-result.md`](p4-terrace-result.md)).
Both runs were fixed by a pre-registration committed before the measurement existed.

## The parameters are pinned, not settable

They are PDAL's defaults: `cell = 1.0 m`, `slope = 0.15`, `scalar = 1.25`, `threshold = 0.5 m`
and `window = 18.0 m`. That last one is the default `18 * cell` written as the distance it
actually is: the window is a length, not a count of cells, and the two readings agree at the
default and part company anywhere else, which is why `smrf.py` says so in its own header.

That set is the one configuration the validation covers, and any other value is a code path no
reference run has exercised. It is the same reason the module refuses `cut > 0` rather than
quietly ignoring it. The record still declares all five, so a reader
can see what ran, and `CALIBRATIONS.md` gives each one a calibration target.

Two consequences reach the interface. The publishing grid cell has to divide the 1 m analysis cell,
so `--cell` takes 1 over a whole number of metres and refuses anything else, naming what would
work. And the grid is grown outward to whole 1 m blocks, which can add cells beyond the area you
asked for; the README lists that among the limitations, because a cell added there publishes what
was measured in it rather than undetermined.

## How this filter was chosen

Measured on 2026-08-27, on the shipped 150 m sample, per cell, over cells holding at least one
return, against the delivery's own ASPRS class 2. All three ran out of the box; none was tuned.

| ground filter | accuracy | recall ground | recall non-ground | false positives |
|---|---|---|---|---|
| the filter shipping at the time (own PMF variant) | 0.837 | 0.999 | 0.723 | 14,327 |
| PDAL `filters.pmf`, defaults | 0.827 | 0.660 | 0.945 | 2,865 |
| PDAL `filters.smrf`, defaults | 0.857 | 0.955 | 0.789 | 10,923 |

The in-repo SMRF that replaced the first row scores 0.866 accuracy on that same sample, with ground
recall 0.977, non-ground recall 0.788 and 10,934 false positives. Those are today's figures for
this implementation, not the table's row for PDAL's build.

The table also shows that the operating point was a choice rather than a rounding difference. PDAL's
PMF is the same algorithm as the retired filter and scores 0.660 ground recall against its 0.999:
the declared tolerance variant that filter used was systematically more permissive toward ground,
and paid for it in non-ground recall and false positives. Keeping the row here costs nothing, and
pretending otherwise costs everything.

What decided the swap was not the accuracy column. It was what the two filters do to buildings: on
a built area, the retired filter published 87.7% of the roof cells holding no ground return at all
as measured terrain, where this one calls 16.4% of them ground
([`reference-instrument-result.md`](reference-instrument-result.md),
[`ground-filter-diagnosis.md`](ground-filter-diagnosis.md)). The README's limitations section
carries both figures.

## What it replaced, and what that cost

Until 0.4.4 the filter was a progressive morphological one (Zhang et al., 2003), whose
`max_elevation_m` capped every tolerance. That parameter decided whether a terrace riser survived,
and it was set from the tallest riser verified at the calibration site, 2.98 m: 16,596 candidates,
the top twelve checked one by one, everything taller turning out to be built walls, a gully edge, or
steps carried by one or two returns ([`riser-measurement.md`](riser-measurement.md)).

SMRF has no such cap. Terrace survival therefore stopped being a guarantee by construction and
became a measurement, which is why the swap was gated on one before being wired, and why the
limitation list says so in those words. The old filter is still in the tree as the comparison arm,
its settings pinned at the values 0.4.4 shipped, and `CALIBRATIONS.md` keeps its rows.

## Reading the denominators

The comparison table above is the shipped 150 m sample, restricted to cells with at least one
return, where the majority-class null is 0.587. The README's results table reports the full Sistelo
area, which is a different population with its own null of 0.503. The two sets of numbers are not
comparable to each other, and neither is comparable to the six-tile agreement figure, which is a
third population again.

Caveats that apply to all of them: one site, out-of-the-box parameters, and a reference that is
DGT's own classification, which is a product rather than ground truth.

## What the official classification does and does not do here

It is the reference the run is quantified against, and never an input to the filter. The comparison
exists to state the difference, not to beat the provider.

Two other official labels are inputs, upstream of the filter. Classes 7 and 18 are removed before
the minimum surface the filter reads is formed. And a tile carrying no class 2 at all is read
normally but recorded as carrying no official ground, which makes `agreement` absent for the whole
product.

On the full area the filter says ground where the official classification has no ground return in
3,174,486 cells, which is 0.2045 of the compared cells. That is the expected shape of a
minimum-surface filter under canopy, declared rather than tuned away.

"""The Simple Morphological Filter (SMRF), in this repository rather than shelled out.

Pingel, T.J., Clarke, K.C. and McBride, W.A. (2013), "An improved simple morphological filter for
the terrain classification of airborne LIDAR data", *ISPRS Journal of Photogrammetry and Remote
Sensing* 77, 21-30, https://doi.org/10.1016/j.isprsjprs.2012.12.002.

Why it is here at all: the filter this package shipped until now publishes buildings as terrain --
it claims `BASIS_MEASURED`, the strongest thing it says about a cell, over 87.7% of the roof cells
of a built AOI where SMRF claims 16.4%, at a cost of 0.6 points on plain ground
(`docs/ground-filter-diagnosis.md`, re-derived in `docs/reference-instrument-result.md`).

Why re-implemented rather than depended on: an install a reader can run without conda. That is a
stated assumption, not a fact -- if it stops holding, a runtime dependency on PDAL is strictly
cheaper and this module should go.

**The definition followed here is PDAL 2.10.2's `filters/SMRFilter.cpp`, read, not remembered**,
because that is the artefact this implementation is validated against cell-for-cell. Where the
paper's prose and that code differ, the code wins and the difference is named:

- `window` is a distance in **metres** and defaults to `18 * cell`; the radius search runs to
  `ceil(window / cell)` cells.
- the structuring element is a **diamond** (L1 ball) -- the source's own comment says "disk".
- border cells take the extremum over their **in-bounds** neighbours only.
- each iteration compares the opening to the **previous** opening, not to the original surface.
- the low-outlier mask is this same filter on the negated surface with `slope=5.0` and a
  one-cell window.
- the membership test is nearest-neighbour, not the splined interpolation the paper prefers.

What is deliberately *not* here: net cutting (`cut > 0`), and `returns`/`classbits` variants. The
reference runs use PDAL's defaults, so those branches would be unvalidated code; `cut` is refused
rather than ignored.

This module is grid arithmetic only. The final membership test is applied to each fine cell's
minimum return rather than to each point, because this package reduces points to per-cell
statistics in a single streaming pass and never holds a tile's points (`accumulate.py`). That is
one declared difference from the reference, whose size is measured rather than assumed -- see
`docs/smrf-build-result.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

FloatGrid = NDArray[np.float64]
BoolGrid = NDArray[np.bool_]

LOW_OUTLIER_SLOPE = 5.0
"""`createLowMask`: the minimum surface is inverted and filtered with a 500% slope tolerance.

Not calibrated here and not ours to calibrate: it is a published constant of the algorithm this
module re-implements, and changing it would make the comparison against the reference meaningless.
"""

KNN_NEIGHBOURS = 8
"""`knnfill` averages the eight nearest non-void cell centres. Also the algorithm's, not ours."""


class SmrfError(ValueError):
    """The filter refuses to run on what it was given, rather than guessing."""


@dataclass(frozen=True)
class SmrfParams:
    """PDAL's option names and defaults, kept verbatim so a reader can compare the two directly."""

    cell: float = 1.0
    slope: float = 0.15
    scalar: float = 1.25
    threshold: float = 0.5
    window: float | None = None
    cut: float = 0.0

    @property
    def window_m(self) -> float:
        """`prepared()` sets the window to `18 * cell` when it was not given -- in metres.

        Exposed as a property because the default is the one place where the metres/cells
        distinction is invisible: at any cell size, `18 * cell` metres is 18 cells, so a reading
        of `window` as a count of cells agrees with this one exactly at the default and disagrees
        at every explicit value.
        """
        return 18.0 * self.cell if self.window is None else self.window


def max_radius_for(window: float, cell: float) -> int:
    """ "The maximum window radius is supplied as a distance metric [...] but is internally
    converted to a pixel equivalent by dividing it by the cell size and rounding the result
    toward positive infinity" (Pingel et al. 2013, quoted in the PDAL source)."""
    return int(math.ceil(window / cell))


def _require_no_holes(z: FloatGrid) -> None:
    if bool(np.isnan(z).any()):
        raise SmrfError(
            "the surface still has holes: every stage of this filter opens a filled surface, "
            "so a NaN here means a caller skipped the fill"
        )


def _step(z: FloatGrid, extremum: np.ufunc) -> FloatGrid:
    """One pass of the 5-point stencil, taking the extremum over in-bounds neighbours only.

    Reading from `z` throughout (never from the partially written output) is what makes this a
    single simultaneous pass rather than a sequential sweep, which would propagate a value across
    the whole grid in one iteration.
    """
    out = z.copy()
    extremum(out[1:, :], z[:-1, :], out=out[1:, :])
    extremum(out[:-1, :], z[1:, :], out=out[:-1, :])
    extremum(out[:, 1:], z[:, :-1], out=out[:, 1:])
    extremum(out[:, :-1], z[:, 1:], out=out[:, :-1])
    return out


def erode_diamond(z: FloatGrid, iterations: int) -> FloatGrid:
    """Greyscale erosion by the L1 ball of radius `iterations`."""
    _require_no_holes(z)
    out = np.asarray(z, dtype=np.float64)
    for _ in range(iterations):
        out = _step(out, np.minimum)
    return out


def dilate_diamond(z: FloatGrid, iterations: int) -> FloatGrid:
    """Greyscale dilation by the L1 ball of radius `iterations`."""
    _require_no_holes(z)
    out = np.asarray(z, dtype=np.float64)
    for _ in range(iterations):
        out = _step(out, np.maximum)
    return out


def progressive_filter(z: FloatGrid, cell: float, slope: float, window: float) -> BoolGrid:
    """Open the surface with a growing window; flag what each step pushes down too far.

    The erosion is carried between iterations (eroded by one more cell each time) while the
    dilation is applied at the full radius to a fresh copy -- so the opening at radius k is the
    opening of the original surface, and the loop is only an economy. What is *not* an economy is
    the comparison: each opening is differenced against the previous opening, so a staircase whose
    individual steps stay under tolerance is never flagged, while the same staircase compared back
    to the original surface would be.
    """
    _require_no_holes(z)
    surface = np.asarray(z, dtype=np.float64)
    erosion = surface
    previous = surface
    flagged = np.zeros(surface.shape, dtype=bool)

    for radius in range(1, max_radius_for(window, cell) + 1):
        erosion = erode_diamond(erosion, 1)
        opening = dilate_diamond(erosion, radius)
        flagged |= np.abs(previous - opening) > slope * cell * radius
        previous = opening

    return flagged


def low_mask(z: FloatGrid, cell: float) -> BoolGrid:
    """Cells holding a low outlier: the same filter on the inverted surface, one radius, 500%.

    These matter more than their number suggests: a single spurious return below the terrain is
    the minimum of its cell, and the minimum surface is what everything downstream reads.
    """
    return progressive_filter(-np.asarray(z, dtype=np.float64), cell, LOW_OUTLIER_SLOPE, cell)


def knn_fill(z: FloatGrid, k: int = KNN_NEIGHBOURS) -> FloatGrid:
    """Fill voids with the mean of the `k` nearest cells that hold a value.

    Distances are computed in cell indices rather than in metres: the two differ by one uniform
    scale factor on both axes, so the neighbour *ordering* is identical and only exact ties could
    resolve differently.

    An entirely empty surface is returned untouched, as PDAL returns early on one. There is
    nothing to interpolate from, and inventing a value is the single thing this package refuses
    to do.
    """
    out = np.array(z, dtype=np.float64, copy=True)
    void = np.isnan(out)
    if not void.any():
        return out
    valid = ~void
    if not valid.any():
        return out

    valid_rc = np.argwhere(valid).astype(np.float64)
    void_rc = np.argwhere(void).astype(np.float64)
    tree = cKDTree(valid_rc)
    _, indices = tree.query(void_rc, k=min(k, int(valid.sum())), workers=-1)
    neighbours = np.atleast_2d(indices.T).T  # k == 1 comes back one-dimensional
    out[void] = out[valid][neighbours].mean(axis=1)
    return out


def _gradient(a: FloatGrid, axis: int) -> FloatGrid:
    """MATLAB's `gradient` convention -- central differences inside, one-sided at the edges.

    `np.gradient` is that convention exactly. It refuses an axis shorter than two samples, where
    a difference is undefined; the gradient there is zero, which is also the only value that
    leaves the threshold at its floor rather than inventing a slope.
    """
    if a.shape[axis] < 2:
        return np.zeros_like(a)
    return np.asarray(np.gradient(a, axis=axis), dtype=np.float64)


def provisional_dem(z_min: FloatGrid, params: SmrfParams) -> tuple[FloatGrid, FloatGrid]:
    """The provisional DEM and the per-cell tolerance the membership test is measured against.

    Both fills of the source are here: the minimum surface is filled before it is opened, and the
    result is filled again after the object and low-outlier cells are cut out of it.

    The tolerance is `threshold + scalar * |grad(ZIpro / cell)|` -- a fixed part and a part that
    opens up on steep ground, "because small horizontal and vertical displacements yield larger
    errors on steep slopes" (Pingel et al. 2013).
    """
    if params.cut > 0.0:
        raise SmrfError(
            "cut > 0 asks for net cutting, which this implementation does not have; the runs it "
            "is validated against use PDAL's default cut = 0, so the branch would be unvalidated"
        )

    filled = knn_fill(np.asarray(z_min, dtype=np.float64))
    _require_no_holes(filled)

    objects = progressive_filter(filled, params.cell, params.slope, params.window_m)
    low = low_mask(filled, params.cell)

    cut_out = filled.copy()
    cut_out[objects | low] = np.nan
    dem = knn_fill(cut_out)

    scaled = dem / params.cell
    gx = _gradient(scaled, axis=1)
    gy = _gradient(scaled, axis=0)
    gradient = knn_fill(np.hypot(gx, gy))
    return dem, params.threshold + params.scalar * gradient


def classify_cells(z: FloatGrid, dem: FloatGrid, thresh: FloatGrid) -> BoolGrid:
    """Ground where the surface sits within the tolerance of the provisional DEM.

    A cell with no measurement is not ground -- it is not anything. NaN compares false here, which
    gives the right answer for the wrong reason, so it is written out rather than relied upon.
    """
    measured = ~np.isnan(z)
    within = np.abs(np.asarray(dem, dtype=np.float64) - np.asarray(z, dtype=np.float64)) <= thresh
    return np.asarray(within & measured & ~np.isnan(dem), dtype=bool)


def block_min(z: FloatGrid, factor: int) -> FloatGrid:
    """The minimum over `factor` x `factor` blocks, with empty blocks staying empty.

    Seeded with `+inf` rather than reduced with `nanmin`: an all-NaN block is a real case here
    (water, shadow), and `nanmin` answers it with a warning and a NaN that is indistinguishable
    from a bug.
    """
    rows, cols = z.shape
    seeded = np.where(np.isnan(z), np.inf, z)
    blocks = seeded.reshape(rows // factor, factor, cols // factor, factor)
    out: FloatGrid = blocks.min(axis=(1, 3))
    out[np.isinf(out)] = np.nan
    return out


def classify_ground_smrf(min_z: FloatGrid, cell: float, params: SmrfParams) -> BoolGrid:
    """Classify each cell of this package's grid as ground or object.

    The algorithm runs on its own coarser grid (`params.cell`, PDAL's default 1 m) built by taking
    the minimum over blocks of the package's cells -- exact, because the minimum of minima is the
    minimum. The membership test then runs back at the package's resolution, comparing each cell's
    own minimum against the provisional DEM of the block that contains it. That is the nearest
    neighbour interpolation the reference uses, evaluated per cell instead of per point.
    """
    z = np.asarray(min_z, dtype=np.float64)
    ratio = params.cell / cell
    factor = int(round(ratio))
    if factor < 1 or abs(ratio - factor) > 1e-9:
        raise SmrfError(
            f"the SMRF cell ({params.cell} m) must be a whole multiple of the grid cell "
            f"({cell} m); block minima are exact only when the blocks tile the grid"
        )
    if z.shape[0] % factor or z.shape[1] % factor:
        raise SmrfError(
            f"a grid of {z.shape[0]}x{z.shape[1]} cells is not divisible into whole "
            f"{factor}x{factor} blocks"
        )

    coarse = block_min(z, factor) if factor > 1 else z
    dem, thresh = provisional_dem(coarse, params)
    if factor > 1:
        dem = np.repeat(np.repeat(dem, factor, axis=0), factor, axis=1)
        thresh = np.repeat(np.repeat(thresh, factor, axis=0), factor, axis=1)
    return classify_cells(z, dem, thresh)

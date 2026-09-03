"""SMRF, tested against what PDAL 2.10.2 actually does.

Every test here names the wrong implementation it rejects. That is deliberate: this module exists
to be validated cell-for-cell against `filters.smrf`, and a test that passes for both the right
and a plausible wrong reading of the algorithm buys nothing. The reference read while writing
these is `filters/SMRFilter.cpp` and `pdal/private/MathUtils.{cpp,hpp}` at tag 2.10.2 -- not the
paper's prose, which differs from the code in at least one respect the tests below pin down (the
structuring element is a diamond, where the source comment says disk).
"""

import numpy as np
import pytest

from microrelief.smrf import (
    SmrfError,
    SmrfParams,
    block_factor,
    block_min,
    classify_cells,
    classify_ground_smrf,
    dilate_diamond,
    erode_diamond,
    knn_fill,
    low_mask,
    max_radius_for,
    progressive_filter,
    provisional_dem,
)


def brute_diamond(a: np.ndarray, radius: int, op) -> np.ndarray:
    """The L1 ball, written out. An independent oracle, not a restatement of the implementation.

    PDAL iterates a 5-point stencil `radius` times, taking the extremum over the *in-bounds*
    neighbours only. Iterating a connected element that contains the origin is the Minkowski sum,
    and clipping at the border just restricts the ball to the grid -- so this direct form is what
    that loop must equal.
    """
    rows, cols = a.shape
    out = np.empty_like(a)
    for i in range(rows):
        for j in range(cols):
            vals = [
                a[ii, jj]
                for ii in range(rows)
                for jj in range(cols)
                if abs(ii - i) + abs(jj - j) <= radius
            ]
            out[i, j] = op(vals)
    return out


# --- morphology -------------------------------------------------------------------------------


def test_diamond_erosion_and_dilation_equal_the_l1_ball() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(size=(9, 11))
    for radius in (1, 2, 3):
        np.testing.assert_allclose(erode_diamond(a, radius), brute_diamond(a, radius, min))
        np.testing.assert_allclose(dilate_diamond(a, radius), brute_diamond(a, radius, max))


def test_the_border_takes_the_extremum_of_its_in_bounds_neighbours_only() -> None:
    """Rejects zero-padding and +/-inf padding, which are the two natural ways to get this wrong.

    Both are silent: an inf-padded erosion is identical everywhere except the outermost ring,
    which is where a tile's cells meet the next tile's.
    """
    a = np.array([[1.0, 2.0, 3.0]])
    eroded = erode_diamond(a, 1)
    assert eroded[0, 0] == 1.0  # min(1, 2) -- not min(0, 1, 2) and not min(inf, 1, 2)
    dilated = dilate_diamond(a, 1)
    assert dilated[0, 0] == 2.0
    assert dilated[0, 2] == 3.0


def test_morphology_refuses_a_surface_with_holes() -> None:
    """Every call site fills before it opens, so NaN here means a caller skipped a stage.

    PDAL's comparison loop would silently turn an all-NaN neighbourhood into the largest
    representable double; refusing is the honest form of that, and this assertion is what makes
    the guard load-bearing.
    """
    a = np.array([[1.0, np.nan], [2.0, 3.0]])
    with pytest.raises(SmrfError, match="hole"):
        erode_diamond(a, 1)
    with pytest.raises(SmrfError, match="hole"):
        dilate_diamond(a, 1)


# --- the progressive filter -------------------------------------------------------------------


def test_a_block_wider_than_the_first_windows_is_flagged_when_the_window_outgrows_it() -> None:
    """A 5-cell block on flat ground, hand-checked against the source's iteration.

    Radii 1 and 2 open the plateau back to itself (a 5-wide plateau survives an L1 ball of radius
    2), so nothing is flagged. At radius 3 the erosion erases it, the opening drops to the ground
    and the difference from the *previous opening* is 5 m against a threshold of 0.45 m.
    """
    z = np.zeros((1, 21))
    z[0, 8:13] = 5.0
    flagged = progressive_filter(z, cell=1.0, slope=0.15, window=5.0)
    assert flagged[0, 8:13].all()
    assert not flagged[0, :8].any()
    assert not flagged[0, 13:].any()


def test_a_ramp_below_the_slope_tolerance_is_never_flagged() -> None:
    """Rejects flag-everything. The companion of the block test: together they are the pair of
    degenerate implementations this filter has to sit between."""
    z = (0.1 * np.arange(21, dtype=float))[None, :]
    assert not progressive_filter(z, cell=1.0, slope=0.15, window=5.0).any()


def test_the_difference_is_taken_against_the_previous_opening_not_the_original() -> None:
    """The subtlety of `progressiveFilter`: `prevSurface` is reassigned to the last opening.

    Two nested plateaus, sized so each one falls away at a different radius. Measured on this
    fixture: the successive differences are 0.44 m at radius 3 (tolerance 0.45) and 0.44 m at
    radius 4 (tolerance 0.60), so nothing is flagged -- while the difference from the *original*
    surface reaches 0.88 m at radius 4 against the same 0.60 and would flag the inner plateau.

    The first fixture written for this test was a monotone staircase, and it could not fail: a
    morphological opening returns a monotone surface unchanged, so both readings differenced
    against the same values. The mutation control is what said so.
    """
    z = np.zeros((1, 31))
    z[0, 12:19] = 0.44  # outer plateau, 7 cells: erased at radius 4
    z[0, 13:18] = 0.88  # inner plateau, 5 cells: erased at radius 3
    assert not progressive_filter(z, cell=1.0, slope=0.15, window=8.0).any()


def test_the_window_is_metres_and_the_radius_is_ceiled() -> None:
    """Rejects reading `window` as a count of cells -- invisible at the default (18 * cell, where
    both readings give 18) and wrong for every explicit value at a cell size other than 1 m."""
    assert max_radius_for(window=4.0, cell=0.5) == 8
    assert max_radius_for(window=4.2, cell=0.5) == 9  # ceil, not round
    assert SmrfParams(cell=1.0).window_m == 18.0
    assert SmrfParams(cell=0.5).window_m == 9.0
    assert SmrfParams(cell=0.5, window=4.0).window_m == 4.0


def test_a_window_read_as_cells_would_miss_this_block() -> None:
    """The discriminator for the line above, as behaviour rather than arithmetic: a 9-cell block
    at 0.5 m needs radius 5 to be erased, which `window=4` metres supplies (8) and `window=4`
    cells does not (4)."""
    z = np.zeros((1, 41))
    z[0, 16:25] = 5.0
    assert progressive_filter(z, cell=0.5, slope=0.15, window=4.0)[0, 16:25].all()
    assert not progressive_filter(z, cell=0.5, slope=0.15, window=2.0)[0, 16:25].any()


# --- the low-outlier mask ---------------------------------------------------------------------


def test_low_mask_flags_a_deep_pit_and_leaves_a_shallow_one() -> None:
    """`createLowMask` runs the same filter on the negated surface with slope 5.0 and a window of
    one cell, so the threshold is 5 m at radius 1. A 2 m pit under it is not an outlier, and a
    test that only checked the 10 m pit would pass for any implementation that flags every pit."""
    z = np.zeros((5, 5))
    z[2, 2] = -10.0
    assert low_mask(z, cell=1.0)[2, 2]
    assert low_mask(z, cell=1.0).sum() == 1

    shallow = np.zeros((5, 5))
    shallow[2, 2] = -2.0
    assert not low_mask(shallow, cell=1.0).any()


# --- the fill ---------------------------------------------------------------------------------


def test_knn_fill_takes_the_mean_of_the_eight_nearest_and_not_the_nearest() -> None:
    z = np.array([[1.0, 2.0, 3.0, np.nan, 10.0, 11.0, 12.0]])
    filled = knn_fill(z)
    assert filled[0, 3] == pytest.approx((1 + 2 + 3 + 10 + 11 + 12) / 6)
    assert not np.isnan(filled).any()


def test_knn_fill_leaves_an_empty_surface_alone() -> None:
    """PDAL returns early when nothing can be interpolated from. Inventing a value here would be
    the one thing this package refuses to do."""
    z = np.full((3, 3), np.nan)
    assert np.isnan(knn_fill(z)).all()


def test_knn_fill_reaches_past_the_nearest_ring() -> None:
    """A hole in a plane fills to the plane, which is also what a nearest-neighbour fill would
    give -- so the asymmetric case above is the one that discriminates. This one guards the
    boring property that the fill does not move a flat surface."""
    z = np.full((7, 7), 5.0)
    z[3, 3] = np.nan
    assert knn_fill(z)[3, 3] == pytest.approx(5.0)


# --- the membership test ----------------------------------------------------------------------


def test_the_threshold_grows_with_the_slope_of_the_provisional_dem() -> None:
    """`thresh = threshold + scalar * |grad(ZIpro / cell)|`. The same 0.6 m residual is an object
    on flat ground and ground on a 0.2 slope. Rejects dropping the `scalar` term, which would
    otherwise pass every flat-ground test in this file."""
    # An explicit one-cell window, because the default (18 * cell) exceeds this 5x5 fixture: every
    # opening would collapse to the global minimum, every cell would be flagged as object, and the
    # provisional DEM would be empty. A fixture has to be large enough for the window it runs.
    params = SmrfParams(cell=1.0, window=1.0)

    flat = np.zeros((5, 5))
    dem_flat, thresh_flat = provisional_dem(flat, params)
    assert thresh_flat[2, 2] == pytest.approx(0.5)

    sloped = 0.2 * np.arange(5, dtype=float)[None, :] * np.ones((5, 1))
    dem_sloped, thresh_sloped = provisional_dem(sloped, params)
    assert thresh_sloped[2, 2] == pytest.approx(0.5 + 1.25 * 0.2)

    # Asserted against the DEM the pipeline returns, not against the surface handed to it: the
    # two differ wherever a cell was flagged, and testing the input would test nothing.
    assert not classify_cells(dem_flat + 0.6, dem_flat, thresh_flat)[2, 2]
    assert classify_cells(dem_sloped + 0.6, dem_sloped, thresh_sloped)[2, 2]


def test_a_cell_with_no_measurement_is_not_ground() -> None:
    dem = np.zeros((3, 3))
    thresh = np.full((3, 3), 0.5)
    z = np.zeros((3, 3))
    z[1, 1] = np.nan
    assert not classify_cells(z, dem, thresh)[1, 1]


# --- the coarse grid --------------------------------------------------------------------------


def test_the_coarse_grid_is_a_minimum_surface() -> None:
    """SMRF is defined on ZImin, so the grid it runs on has to be a minimum surface too.

    The minimum of minima is the minimum, which is what makes the coarse grid exact rather than
    an approximation -- and a block mean, the natural-looking alternative, is not a minimum
    surface at all: a single roof return would lift the terrain under its own block. Asserted
    here rather than end-to-end because the object mask and the refill repair that lift on a
    synthetic scene, so only the definition discriminates (the mutation control found this).
    """
    z = np.array(
        [
            [0.0, 5.0, 1.0, 1.0],
            [2.0, 3.0, 1.0, 1.0],
            [np.nan, np.nan, 7.0, 8.0],
            [np.nan, np.nan, 9.0, 6.0],
        ]
    )
    coarse = block_min(z, 2)
    np.testing.assert_array_equal(coarse[0], [0.0, 1.0])
    assert np.isnan(coarse[1, 0])  # an empty block stays empty; it is not zero, and not filled
    assert coarse[1, 1] == 6.0


# --- end to end, on a synthetic scene ---------------------------------------------------------


def scene() -> np.ndarray:
    """A 0.5 m minimum surface: a 5% hillside with a 6 m building and a 1.5 m terrace riser."""
    rows, cols = 120, 120
    col = np.arange(cols, dtype=float)
    z = np.tile(0.05 * col * 0.5, (rows, 1))  # 5% slope across a 0.5 m grid
    z[:, 60:] += 1.5  # a terrace riser, the thing that must survive
    z[30:50, 20:40] += 6.0  # a 10 m x 10 m building
    return z


def test_the_building_goes_and_the_ground_stays() -> None:
    is_ground = classify_ground_smrf(scene(), cell=0.5, params=SmrfParams(cell=1.0))

    building = np.zeros(scene().shape, dtype=bool)
    building[32:48, 22:38] = True  # the building's interior, off its own edge
    assert is_ground[building].mean() < 0.05

    open_ground = np.zeros(scene().shape, dtype=bool)
    open_ground[70:110, 5:55] = True  # away from the building and the riser
    assert is_ground[open_ground].mean() > 0.95

    # Neither degenerate answer passes the pair above, but assert it directly too: a filter that
    # said "everything is ground" would still be caught here if either margin were ever loosened.
    assert 0.05 < is_ground.mean() < 0.99


def test_the_terrace_riser_survives() -> None:
    """The symmetric risk. A filter that removes buildings by removing every abrupt step destroys
    the artefact this tool exists to publish."""
    is_ground = classify_ground_smrf(scene(), cell=0.5, params=SmrfParams(cell=1.0))
    riser = np.zeros(scene().shape, dtype=bool)
    riser[70:110, 58:63] = True  # the cells either side of the 1.5 m step, clear of the building
    assert is_ground[riser].mean() > 0.90


# --- refusals ---------------------------------------------------------------------------------


def test_net_cutting_is_refused_rather_than_approximated() -> None:
    """`cut > 0` is a branch of PDAL this implementation does not have, and the reference runs
    that validate it use the default `cut = 0`. Silently ignoring the parameter would let a
    caller believe a feature ran."""
    with pytest.raises(SmrfError, match="cut"):
        classify_ground_smrf(np.zeros((4, 4)), cell=0.5, params=SmrfParams(cell=1.0, cut=10.0))


def test_the_smrf_cell_must_be_a_whole_multiple_of_the_grid_cell() -> None:
    """The coarse grid is built by taking the minimum over blocks of fine cells, which is exact
    only when the blocks tile the grid. A 1.0 m SMRF cell on a 0.3 m grid has no such block."""
    with pytest.raises(SmrfError, match="multiple"):
        classify_ground_smrf(np.zeros((4, 4)), cell=0.3, params=SmrfParams(cell=1.0))


def test_the_grid_must_divide_into_whole_blocks() -> None:
    with pytest.raises(SmrfError, match="divis"):
        classify_ground_smrf(np.zeros((5, 4)), cell=0.5, params=SmrfParams(cell=1.0))


# --- the block factor, single-sourced ------------------------------------------------------
#
# The CLI has to know the block size before it builds the grid (to snap the grid to whole
# blocks) and the filter has to know it after (to take block minima). Computing it twice is
# how the two drift, so it is computed once here and both callers read it.


def test_the_block_factor_is_the_ratio_of_the_two_cell_sizes() -> None:
    assert block_factor(0.5, SmrfParams(cell=1.0)) == 2
    assert block_factor(1.0, SmrfParams(cell=1.0)) == 1
    assert block_factor(0.25, SmrfParams(cell=1.0)) == 4


def test_a_grid_cell_that_does_not_divide_the_smrf_cell_is_refused_by_name() -> None:
    """The message has to say what IS admissible, or the caller cannot act on it."""
    with pytest.raises(SmrfError, match="multiple") as exc:
        block_factor(0.3, SmrfParams(cell=1.0))
    assert "0.5" in str(exc.value), "a refusal that names no admissible value is a dead end"


def test_a_grid_cell_coarser_than_the_smrf_cell_is_refused_rather_than_rounded_to_zero() -> None:
    """`round(1.0 / 2.0)` is 0, and a factor of 0 is not an error anywhere downstream: it makes
    a block size of zero, which divides no grid and reads as a filter that never ran. This is
    the case the ratio check catches only because it is written as a whole-multiple test rather
    than as a rounding."""
    with pytest.raises(SmrfError, match="multiple"):
        block_factor(2.0, SmrfParams(cell=1.0))
    with pytest.raises(SmrfError, match="multiple"):
        block_factor(0.75, SmrfParams(cell=1.0))


def test_a_non_positive_grid_cell_is_refused_by_name_not_by_arithmetic() -> None:
    """`block_factor` now runs BEFORE `grid_for_bounds` at the composition root, so it inherited
    the duty of refusing a cell size that is not a positive length. Measured before the fix:
    `--cell 0` produced a bare `ZeroDivisionError` and `--cell -0.5` blamed the whole-multiple
    rule, which is not the first thing wrong with it."""
    for bad in (0.0, -0.5, -1.0):
        with pytest.raises(SmrfError, match="positive, finite"):
            block_factor(bad, SmrfParams(cell=1.0))


def test_a_non_finite_grid_cell_is_refused_too() -> None:
    """`float("nan") <= 0` is False, so a NaN cell walked through a bare positivity test and
    died in `int(round(1.0 / nan))` -- the bare-arithmetic failure the guard replaced, surviving
    inside the guard. `inf` reached a named refusal but blamed the whole-multiple rule."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(SmrfError, match="positive, finite"):
            block_factor(bad, SmrfParams(cell=1.0))


def test_a_surface_with_nothing_measured_says_so_instead_of_blaming_the_caller() -> None:
    """An AOI that holds no returns is a real input, not a broken contract.

    Without this the run reaches `_require_no_holes` -- `knn_fill` returns an all-void surface
    untouched, by design -- and refuses with "a caller skipped the fill", which describes an
    internal invariant rather than the user's situation. The retired filter raised
    `GroundError("no measured cells: ...")` and the swap lost that.
    """
    empty = np.full((4, 4), np.nan)
    with pytest.raises(SmrfError, match="no measured cells"):
        classify_ground_smrf(empty, cell=0.5, params=SmrfParams(cell=1.0))


def test_the_all_void_guard_does_not_fire_on_a_surface_that_holds_one_cell() -> None:
    """The discriminating arm: 'every cell empty' must mean every cell, not almost every cell."""
    almost = np.full((4, 4), np.nan)
    almost[2, 2] = 100.0
    out = classify_ground_smrf(almost, cell=0.5, params=SmrfParams(cell=1.0))
    assert out.shape == (4, 4)
    assert bool(out[2, 2]), "the one measured cell sits on the provisional DEM and is ground"


def test_a_surface_where_every_cell_is_cut_refuses_instead_of_publishing_nothing() -> None:
    """The all-void guard closes the INPUT side; this is the same situation from the other end.

    When the progressive filter and the low-outlier mask together cover every coarse cell, the
    surface handed to the second fill is all-void. `knn_fill` returns it untouched, by design,
    the tolerance is all-NaN, and the membership test then calls every cell non-ground: a DTM of
    nothing, exit 0. Measured before the fix on this exact input -- 0 of 16 cells ground, no
    refusal. A small AOI filled by one building or one steep face reaches it.
    """
    steep = np.repeat(
        np.repeat(np.array([[91.96, 105.42], [119.56, 114.20]]), 2, axis=0), 2, axis=1
    )
    with pytest.raises(SmrfError, match="no ground left"):
        classify_ground_smrf(steep, cell=0.5, params=SmrfParams(cell=1.0))


def test_the_all_cut_guard_leaves_an_ordinary_surface_alone() -> None:
    """The quiet arm. A guard that fires on a normal surface would refuse every real run."""
    rng = np.random.default_rng(0)
    gentle = rng.normal(100.0, 0.05, (8, 8))
    out = classify_ground_smrf(gentle, cell=0.5, params=SmrfParams(cell=1.0))
    assert out.any(), "a nearly flat surface is mostly ground; the guard must not reach it"

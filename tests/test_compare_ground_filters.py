"""The acceptance instrument's own rules, on inputs small enough to count by hand.

`scripts/compare_ground_filters.py` is what the SMRF re-implementation will be measured against,
so its three load-bearing rules are pinned here rather than left to the run that uses them:

* which points SMRF actually judged -- PDAL's `returns` default is `[last, only]` and
  `only_ground` is false, so a passed-through class-2 point is indistinguishable from a judged
  ground point *by class alone*. Get this wrong and every number in the table moves;
* that the delivery tile and the SMRF output can be zipped by index at all;
* the erosion behind "roof interior", which the diagnosis defines as "B, >= 2 cells inside the
  edge" and which is the population the whole comparison rests on.

Each rule is tested on an input where the right answer is obvious, and each guard is tested on an
input it must REFUSE as well as one it must accept -- a guard only exercised on the accepting side
is indistinguishable from no guard.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_ground_filters.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("compare_ground_filters", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


class TestJudgedMask:
    """Only last-and-only returns are judged, and the ignored class is never judged."""

    def test_last_and_only_returns_are_judged_others_are_not(self) -> None:
        # one single return; one 3-return pulse (first, middle, last); one 2-return pulse
        classification = np.array([1, 1, 1, 1, 1, 1], dtype=np.uint8)
        return_number = np.array([1, 1, 2, 3, 1, 2], dtype=np.int32)
        number_of_returns = np.array([1, 3, 3, 3, 2, 2], dtype=np.int32)

        judged = mod.judged_mask(classification, return_number, number_of_returns)

        # only(1st) yes; first-of-3 no; middle-of-3 no; last-of-3 yes; first-of-2 no; last-of-2 yes
        assert judged.tolist() == [True, False, False, True, False, True]

    def test_the_ignored_class_is_never_judged_even_when_it_is_a_last_return(self) -> None:
        classification = np.array([7, 1], dtype=np.uint8)
        return_number = np.array([1, 1], dtype=np.int32)
        number_of_returns = np.array([1, 1], dtype=np.int32)

        judged = mod.judged_mask(classification, return_number, number_of_returns)

        assert judged.tolist() == [False, True]

    def test_a_mask_admitting_everything_would_fail_this(self) -> None:
        """The discriminating arm: the mask must EXCLUDE something, or it is not a mask.

        `judged-outside-mask == 0` is passed perfectly by a mask that admits every point, which is
        why the recorded control pairs it with a count of passed-through class-2 points.
        """
        classification = np.ones(4, dtype=np.uint8)
        return_number = np.array([1, 2, 3, 4], dtype=np.int32)
        number_of_returns = np.array([4, 4, 4, 4], dtype=np.int32)

        judged = mod.judged_mask(classification, return_number, number_of_returns)

        assert int(judged.sum()) == 1, "only the last return of a 4-return pulse is judged"


class TestCorrespondence:
    """Zipping two files by index is a claim about them, so it is checked, not assumed."""

    def test_identical_coordinates_are_accepted(self) -> None:
        x = np.array([1, 2, 3], dtype=np.int32)
        mod.check_correspondence(x, x, x, x, x, x)  # must not raise

    def test_differing_coordinates_are_refused(self) -> None:
        x = np.array([1, 2, 3], dtype=np.int32)
        moved = np.array([1, 2, 4], dtype=np.int32)
        with pytest.raises(mod.ReferenceBuildError, match="coordinate"):
            mod.check_correspondence(x, x, x, moved, x, x)

    def test_differing_lengths_are_refused(self) -> None:
        x = np.array([1, 2, 3], dtype=np.int32)
        short = np.array([1, 2], dtype=np.int32)
        with pytest.raises(mod.ReferenceBuildError, match="point count"):
            mod.check_correspondence(x, x, x, short, short, short)


class TestInterior:
    """'>= n cells inside the edge' is an erosion, and it has to bite at the right depth."""

    def test_a_five_by_five_block_eroded_by_two_leaves_its_centre(self) -> None:
        mask = np.zeros((9, 9), dtype=bool)
        mask[2:7, 2:7] = True  # 5x5 block

        interior = mod.interior(mask, margin=2)

        assert int(interior.sum()) == 1
        assert bool(interior[4, 4])

    def test_a_block_thinner_than_the_margin_has_no_interior(self) -> None:
        mask = np.zeros((9, 9), dtype=bool)
        mask[2:5, 2:7] = True  # 3 rows tall: cannot be 2 cells from both edges

        assert int(mod.interior(mask, margin=2).sum()) == 0

    def test_margin_one_is_a_single_erosion(self) -> None:
        mask = np.zeros((7, 7), dtype=bool)
        mask[2:5, 2:5] = True  # 3x3

        assert int(mod.interior(mask, margin=1).sum()) == 1

    def test_the_grid_edge_counts_as_an_edge(self) -> None:
        """A block running off the raster is not 'inside' anything on that side."""
        mask = np.zeros((5, 5), dtype=bool)
        mask[0:3, 0:3] = True  # touches row 0 and column 0

        assert int(mod.interior(mask, margin=2).sum()) == 0


class TestDefaultsTrackTheShippedFilter:
    """The instrument must measure the filter that ships, not one that used to.

    The first draft of this script carried three of six defaults wrong -- typed from memory of
    the record instead of copied from it (24.0/0.2/3.0 against the shipped 4.0/0.3/2.0). Nothing
    would have failed: the table would simply have described a filter nobody runs. So the two
    sets of literals are locked to each other, and drift in EITHER file fails here.
    """

    SHARED = (
        "max-window-m",
        "slope-threshold",
        "elevation-threshold-m",
        "max-elevation-m",
        "k-min-returns",
        "d-max-interp-m",
    )

    @staticmethod
    def _defaults(source: str) -> dict[str, str]:
        """Every declaration of each shared flag, not the first one.

        `re.search` stops at the first match, so this lock only ever read the `compare` parser.
        The `terraces` parser re-declares all six of these, and drifted past the lock unseen
        until a review found it. A flag declared twice with two values is a file that disagrees
        with itself, so disagreement between declarations is recorded and fails the comparison.
        """
        import re

        found = {}
        for flag in TestDefaultsTrackTheShippedFilter.SHARED:
            values = re.findall(
                rf'add_argument\(\s*"--{re.escape(flag)}",\s*type=\w+,\s*default=([0-9.]+)\)',
                source,
            )
            if values:
                found[flag] = values[0] if len(set(values)) == 1 else f"DISAGREES:{set(values)}"
        return found

    def test_every_shared_default_matches_the_cli(self) -> None:
        cli = self._defaults((ROOT / "src" / "microrelief" / "cli.py").read_text())
        instrument = self._defaults(SCRIPT.read_text())

        assert set(cli) == set(self.SHARED), f"could not read the CLI's defaults: found {cli}"
        assert set(instrument) == set(self.SHARED), f"could not read ours: found {instrument}"
        assert instrument == cli

    def test_the_reader_would_notice_a_changed_default(self) -> None:
        """Control on the control: the comparison above must be able to fail."""
        mutated = SCRIPT.read_text().replace(
            'c.add_argument("--max-window-m", type=float, default=4.0)',
            'c.add_argument("--max-window-m", type=float, default=40.0)',
        )
        cli = self._defaults((ROOT / "src" / "microrelief" / "cli.py").read_text())

        assert self._defaults(mutated) != cli


class TestConfusionAndKappa:
    """The second number exists because the first one is passed by the degenerate answer."""

    @staticmethod
    def _all(shape: tuple[int, int], value: bool) -> np.ndarray:
        return np.full(shape, value, dtype=bool)

    def test_kappa_scores_a_filter_that_calls_everything_ground_at_zero(self) -> None:
        """On this AOI most cells are ground, so raw agreement rewards saying so about all of
        them. That is exactly the implementation the acceptance predicates have to reject."""
        reference = np.zeros((10, 10), dtype=bool)
        reference[:9, :] = True  # 90% of cells are ground
        population = self._all((10, 10), True)

        degenerate = mod.confusion(self._all((10, 10), True), reference, population)
        assert degenerate.agreement == pytest.approx(90.0)
        assert degenerate.kappa == pytest.approx(0.0)

    def test_kappa_is_one_when_the_two_filters_agree_everywhere(self) -> None:
        reference = np.zeros((10, 10), dtype=bool)
        reference[:9, :] = True
        perfect = mod.confusion(reference.copy(), reference, self._all((10, 10), True))
        assert perfect.agreement == pytest.approx(100.0)
        assert perfect.kappa == pytest.approx(1.0)

    def test_the_confusion_counts_are_the_four_cells_of_the_table(self) -> None:
        ours = np.array([[True, True], [False, False]])
        reference = np.array([[True, False], [True, False]])
        c = mod.confusion(ours, reference, self._all((2, 2), True))
        assert (c.both_ground, c.ours_only, c.reference_only, c.neither) == (1, 1, 1, 1)
        assert c.n == 4


class TestSeamCells:
    """Tile edges are where the reference's per-tile grid and our AOI grid must disagree."""

    @staticmethod
    def _grid():
        from microrelief.grid import Grid

        return Grid(origin_x=0.0, origin_y=100.0, cell=1.0, n_cols=100, n_rows=100, crs_epsg=3763)

    def test_cells_within_the_margin_of_a_tile_edge_are_marked(self) -> None:
        provenance = {"sources": [{"bounds": [0.0, 0.0, 50.0, 100.0]}]}
        seam = mod.seam_cells(provenance, self._grid(), margin_m=5.0)
        assert seam[50, 50]  # right at the x = 50 edge
        assert not seam[50, 70]  # 20 m away from any edge
        assert seam[50, 0]  # the tile's own outer edge counts too

    def test_a_second_tile_does_not_mark_the_interior_of_the_first(self) -> None:
        """Two tiles, because with one the right definition and the wrong one agree everywhere.

        The wrong one -- a row band unioned with a column band -- marks every cell that merely
        SHARES a row or column with some tile's edge. Here that is the whole of column 30 and the
        whole of row 30, including a cell in the middle of the other tile.
        """
        provenance = {
            "sources": [
                {"bounds": [0.0, 70.0, 100.0, 100.0]},  # a tile across the top
                {"bounds": [0.0, 0.0, 30.0, 30.0]},  # a small tile at the bottom left
            ]
        }
        # Row i sits at y = 99.5 - i and column j at x = j + 0.5, so these are coordinates and
        # not guesses: row 30 is y = 69.5, row 70 is y = 29.5, row 14 is y = 85.5.
        seam = mod.seam_cells(provenance, self._grid(), margin_m=5.0)
        assert seam[30, 50]  # y = 69.5, half a metre below the top tile's lower edge
        assert seam[70, 15]  # y = 29.5, half a metre below the small tile's upper edge

        # The two discriminating cells. Each SHARES a row or a column with a real tile edge, so
        # the row-band-union-column-band version marks both; each is far from every tile frame.
        assert not seam[14, 30]  # x = 30.5 shares the small tile's x edge; y = 85.5 is mid-tile
        assert not seam[70, 60]  # y = 29.5 shares its y edge; x = 60.5 is 30 m outside it

    def test_a_reference_built_before_bounds_were_recorded_marks_nothing(self) -> None:
        """Older reference files carry no `bounds`. Silently marking nothing is right -- but only
        because the seam figure is reported beside the headline and never replaces it."""
        seam = mod.seam_cells({"sources": [{"tile": "x.laz"}]}, self._grid(), margin_m=5.0)
        assert not seam.any()


class TestPredicatesMatchTheirPreRegistration:
    """The predicates are written in two places, so they are locked to each other.

    A number quoted in a document and applied in code is the shape that produced this repo's
    worst near-misses: the instrument would report a verdict against one bound while the record
    that justified it named another, and nothing would fail.

    The first version of this lock asserted only that `f"{value:g}"` appeared *somewhere* in the
    document. Measured on the real file, that passes with P1 loosened from 97.0 to 10.0 and the
    agreement bound from 90.0 to 20.0, because "10", "20" and "30" all occur in the prose -- a
    lock that admits a catastrophic loosening of the predicate it guards. The bound is now read
    from the row that NAMES it, and the control below changes a bound and requires a failure.
    """

    DOC = ROOT / "docs" / "smrf-build-preregistration.md"

    # Each bound as the document states it: the table row that names the predicate, and the
    # comparison written in bold. `P3` has two rows, told apart by their subject.
    ROWS = (
        ("P1_PLAIN_GROUND_MIN", r"\*\*P1\*\*", "≥"),
        ("P2_ROOF_MAX", r"\*\*P2\*\*", "≤"),
        ("P3_AGREEMENT_MIN", r"\*\*P3\*\*.*agreement", "≥"),
        ("P3_KAPPA_MIN", r"\*\*P3\*\*.*κ", "≥"),
    )

    @staticmethod
    def _bound(text: str, row_pattern: str, comparison: str) -> float:
        import re

        row = re.search(rf"^\|\s*{row_pattern}.*$", text, re.M)
        assert row, f"no row in the pre-registration matches {row_pattern!r}"
        found = re.search(rf"\*\*{comparison}\s*([0-9.]+)%?\*\*", row.group(0))
        assert found, f"the row {row.group(0)!r} states no bound of the form **{comparison} N**"
        return float(found.group(1))

    def test_every_bound_in_the_code_is_the_one_its_own_row_states(self) -> None:
        text = self.DOC.read_text()
        for name, row_pattern, comparison in self.ROWS:
            assert self._bound(text, row_pattern, comparison) == getattr(mod, name), name

    def test_a_loosened_bound_fails_this_lock(self) -> None:
        """Control on the control, run against the check itself rather than beside it.

        The previous control asserted a string was absent from the document, which never invoked
        the comparison and so could not notice it had stopped discriminating.
        """
        text = self.DOC.read_text()
        loosened = text.replace("**≥ 97.0%**", "**≥ 10.0%**", 1)
        assert loosened != text, "the P1 bound is not written in the form this control mutates"
        assert self._bound(loosened, r"\*\*P1\*\*", "≥") == 10.0
        assert self._bound(loosened, r"\*\*P1\*\*", "≥") != mod.P1_PLAIN_GROUND_MIN


class TestStepMagnitude:
    """The terrace population of `docs/p4-terrace-preregistration.md`.

    "Cells sitting on a real vertical step in 3.5 m" is the phrase the record leaves undefined,
    and P4b's whole denominator is built from it, so the operation is pinned here on surfaces
    where the right answer can be counted by hand. Every case is paired: a surface the mask must
    fire on, and one it must stay silent on. A population that cannot come back empty is not
    measuring anything.
    """

    def test_a_flat_surface_holds_no_step(self) -> None:
        """Must-not-fire. A constant surface has a range of zero everywhere."""
        surface = np.full((7, 7), 10.0)

        step, defined = mod.step_magnitude(surface, window_cells=3, min_finite=2)

        assert defined[1:-1, 1:-1].all()
        assert np.allclose(step[defined], 0.0)

    def test_a_known_step_is_measured_at_its_height(self) -> None:
        """Must-fire. A 3.0 m wall between two flats reads 3.0 m, and only near the wall."""
        surface = np.zeros((9, 9))
        surface[:, 5:] = 3.0

        step, defined = mod.step_magnitude(surface, window_cells=3, min_finite=2)

        # Columns 4 and 5 straddle the discontinuity; their 3-wide windows span both flats.
        assert np.allclose(step[1:-1, 4], 3.0)
        assert np.allclose(step[1:-1, 5], 3.0)
        # Column 2 lies wholly on the lower flat, column 7 wholly on the upper one.
        assert np.allclose(step[1:-1, 2], 0.0)
        assert np.allclose(step[1:-1, 7], 0.0)

    def test_a_window_holding_one_finite_cell_is_undefined(self) -> None:
        """A range needs two points. One is not a small range, it is no range."""
        surface = np.full((7, 7), np.nan)
        surface[3, 3] = 10.0

        step, defined = mod.step_magnitude(surface, window_cells=3, min_finite=2)

        assert not defined.any()
        assert np.isnan(step).all()

    def test_two_finite_cells_in_the_window_are_enough(self) -> None:
        """The control on the control: the same surface with one more point does define a step."""
        surface = np.full((7, 7), np.nan)
        surface[3, 3] = 10.0
        surface[3, 4] = 12.5

        step, defined = mod.step_magnitude(surface, window_cells=3, min_finite=2)

        assert bool(defined[3, 3])
        assert step[3, 3] == pytest.approx(2.5)

    def test_nan_does_not_propagate_through_the_range(self) -> None:
        """Accumulating min/max over NaN gives NaN unless the fill is seeded at -inf/+inf."""
        surface = np.zeros((7, 7))
        surface[0, 0] = np.nan
        surface[3, 4] = 4.0

        step, defined = mod.step_magnitude(surface, window_cells=3, min_finite=2)

        assert defined[3, 3]
        assert step[3, 3] == pytest.approx(4.0)
        assert np.isfinite(step[defined]).all()

    def test_cells_within_the_margin_of_the_border_are_excluded(self) -> None:
        """A cell whose 3.5 m neighbourhood runs off the grid was never observed.

        The same reasoning `interior()` applies with `border_value=0`: a truncated window would
        report the range of the part that happened to be inside, which is not the cell's step.
        """
        surface = np.zeros((9, 9))

        _step, defined = mod.step_magnitude(surface, window_cells=7, min_finite=2)

        assert not defined[:3, :].any()
        assert not defined[-3:, :].any()
        assert not defined[:, :3].any()
        assert not defined[:, -3:].any()
        assert int(defined.sum()) == 3 * 3  # the 3x3 interior of a 9x9 grid at margin 3

    def test_the_window_must_be_odd_so_it_has_a_centre(self) -> None:
        with pytest.raises(ValueError):
            mod.step_magnitude(np.zeros((9, 9)), window_cells=4, min_finite=2)

    def test_the_window_is_three_and_a_half_metres_at_half_metre_cells(self) -> None:
        """The reading of "in 3.5 m" the pre-registration declares, pinned to the constant."""
        assert mod.STEP_WINDOW_CELLS * 0.5 == 3.5


class TestP4BoundsMatchThePreRegistration:
    """The P4 bounds are two sets of literals -- prose and code -- and they can drift apart."""

    DOC = ROOT / "docs" / "p4-terrace-preregistration.md"
    ROWS = (
        ("P4A_TERRACE_MIN", r"\*\*P4a\*\*.*share of", "≥"),
        ("P4B_STEEP_MIN", r"\*\*P4b\*\*.*share of", "≥"),
    )

    def test_every_bound_in_the_code_is_the_one_its_own_row_states(self) -> None:
        text = self.DOC.read_text()
        for name, row_pattern, comparison in self.ROWS:
            assert TestPredicatesMatchTheirPreRegistration._bound(
                text, row_pattern, comparison
            ) == getattr(mod, name), name

    def test_a_loosened_bound_fails_this_lock(self) -> None:
        """Mutation on the lock itself: a bound moved in the document must be seen."""
        text = self.DOC.read_text()
        loosened = text.replace("**≥ 80.0%**", "**≥ 5.0%**", 1)
        assert loosened != text, "the P4b bound is not written in the form this control mutates"
        assert (
            TestPredicatesMatchTheirPreRegistration._bound(loosened, r"\*\*P4b\*\*.*share of", "≥")
            == 5.0
        )


class TestTheWindowExtentIsPinned:
    """The extent the range is taken over, pinned independently of the counts kernel.

    Found by review, not by me: a mutant that widens ONLY the two extremum filters -- leaving
    `STEP_WINDOW_CELLS`, the counts kernel and the border margin alone -- passed every test in
    `TestStepMagnitude`. My own "widened window" mutant changed the constant, which a test
    asserts directly, so it was caught by arithmetic on a literal rather than by any test of
    what the window does. These place a wall at a known distance, where a wider window reaches
    it and the declared one does not.
    """

    @staticmethod
    def _wall_at(distance_cells: int) -> np.ndarray:
        surface = np.zeros((21, 21))
        surface[:, 10 + distance_cells :] = 3.0
        return surface

    def test_the_declared_window_does_not_reach_a_wall_four_cells_away(self) -> None:
        surface = self._wall_at(4)

        step, defined = mod.step_magnitude(surface, window_cells=7, min_finite=2)

        assert defined[10, 10]
        assert step[10, 10] == pytest.approx(0.0)

    def test_a_window_two_cells_wider_does_reach_it(self) -> None:
        """Control on the control: the same cell, the same wall, a wider window."""
        surface = self._wall_at(4)

        step, defined = mod.step_magnitude(surface, window_cells=9, min_finite=2)

        assert defined[10, 10]
        assert step[10, 10] == pytest.approx(3.0)


class TestTheRampIsADeclaredLimitation:
    """A uniform hillside enters the population, and this pins that rather than hiding it.

    `step_magnitude` is a range in a window, so it cannot tell a riser from a smooth slope steep
    enough to span the threshold: above about 40 degrees at 0.5 m cells, EVERY cell of a planar
    ramp holding no step at all reads as "on a step > 2.5 m". Found by review after the P4 run.
    Measured consequence on the real window, in `docs/p4-terrace-result.md`: 1.2% of the gate
    population is near-planar, and restricting to the wall-like cells moves P4b from 95.1% to
    92.1%, still twelve points clear of the bound -- so the verdict does not rest on it. The
    behaviour is pinned here so a later change to the operation has to face it.
    """

    @staticmethod
    def _ramp(degrees: float) -> np.ndarray:
        gradient = np.tan(np.radians(degrees))
        return (np.mgrid[0:30, 0:30][1] * 0.5 * gradient).astype(np.float64)

    def test_a_gentle_ramp_does_not_enter_the_population(self) -> None:
        step, defined = mod.step_magnitude(self._ramp(30), window_cells=7, min_finite=2)

        assert not (step[defined] > 2.5).any()

    def test_a_steep_ramp_holding_no_step_enters_it_entirely(self) -> None:
        """The declared limitation, asserted so it cannot change silently."""
        step, defined = mod.step_magnitude(self._ramp(45), window_cells=7, min_finite=2)

        assert (step[defined] > 2.5).all()

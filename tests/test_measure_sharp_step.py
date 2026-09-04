"""The zone-wide instrument's own rules, on surfaces whose answer is known.

`scripts/measure_sharp_step.py` decides whether `docs/sharp-step-preregistration.md` passes, so
each of its three predicates is tested on an input where it must FAIL as well as one where it must
pass. A predicate only ever exercised on its accepting side is indistinguishable from no predicate,
and G2 in particular is passed perfectly by an instrument that selects nothing -- which is why its
two halves are asserted separately here.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measure_sharp_step.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_sharp_step", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def _cache(path: Path, surface: np.ndarray) -> Path:
    """A cache in `measure_risers.py build`'s shape, georeferenced at Zone Z's top-left."""
    minx, _, _, maxy = mod.ZONE
    np.savez_compressed(
        path,
        min_z_ground=surface.astype(np.float32),
        n_ground=np.where(np.isfinite(surface), 1, 0).astype(np.int32),
        min_z_all=surface.astype(np.float32),
        max_z_all=surface.astype(np.float32),
        n_all=np.where(np.isfinite(surface), 1, 0).astype(np.int32),
        origin_x=minx,
        origin_y=maxy,
        cell=0.5,
        crs_epsg=3763,
    )
    return path


def _summary(out: str) -> str:
    """The last verdict line, which is what a reader greps and what a record quotes.

    Asserting that a phrase appears SOMEWHERE in stdout is satisfied by the per-location table
    two lines above it, so the summary line itself was unlocked: mutating it back to naming G1
    alone left every test green.
    """
    for line in reversed(out.splitlines()):
        if line.startswith(("PASS", "FAIL:", "NOT EVALUABLE:")):
            return line
    raise AssertionError(f"no verdict line in:\n{out[-600:]}")


def _run_predicates(surface: np.ndarray) -> tuple[float, list[object]]:
    """The population, the S1 median residual, and the G1 hits -- what the predicates read."""
    result = mod.cgf.sharp_step_population(surface, cell_m=0.5)
    minx, _, _, maxy = mod.ZONE
    median = float(np.nanmedian(result.residual[result.candidates]))
    hits = mod.g1_hits(result.population, minx, maxy, 0.5, residual=result.residual)
    return median, list(hits)


class TestTheVerifiedLocations:
    def test_every_verified_location_is_inside_zone_z(self) -> None:
        """A must-fire control outside the zone would be vacuous."""
        minx, miny, maxx, maxy = mod.ZONE
        for name, x, y in mod.VERIFIED_STEPS:
            assert minx <= x <= maxx and miny <= y <= maxy, name

    def test_the_four_ranked_locations_match_the_committed_report(self) -> None:
        """The constant is copied from the record, not typed from memory."""
        report = json.loads((ROOT / "docs" / "figures" / "riser" / "report.json").read_text())
        by_rank = {i + 1: c for i, c in enumerate(report["top_clusters"])}
        for rank in (4, 8, 10, 11):
            x, y = by_rank[rank]["x"], by_rank[rank]["y"]
            assert any(
                abs(vx - x) < 1e-6 and abs(vy - y) < 1e-6 for _, vx, vy in mod.VERIFIED_STEPS
            ), rank

    def test_the_terrace_riser_is_not_in_the_report_and_cannot_be_locked_against_it(self) -> None:
        """The gap the pre-registration declares, pinned so it cannot be forgotten.

        `top_clusters` holds the twenty tallest candidates and the shortest of them is far above
        the 2.98 m terrace riser, so that location is locked against the prose of
        `docs/riser-measurement.md` and nothing else. Saying so is the alternative to implying
        all five are equally sourced.
        """
        report = json.loads((ROOT / "docs" / "figures" / "riser" / "report.json").read_text())
        heights = [c["height_m"] for c in report["top_clusters"]]

        assert min(heights) > 2.98
        assert "label" not in report["top_clusters"][0]


class TestG1:
    def test_g1_passes_only_where_the_population_actually_holds_the_step(self) -> None:
        """Built on an empty population and on one holding a single verified location."""
        cell_m, shape = 0.5, (1600, 1600)
        minx, _, _, maxy = mod.ZONE
        empty = np.zeros(shape, dtype=bool)

        assert not any(hit.found for hit in mod.g1_hits(empty, minx, maxy, cell_m))

        one = np.zeros(shape, dtype=bool)
        name, x, y = mod.VERIFIED_STEPS[0]
        one[int((maxy - y) / cell_m), int((x - minx) / cell_m)] = True
        hits = {hit.name: hit.found for hit in mod.g1_hits(one, minx, maxy, cell_m)}

        assert hits[name]
        assert sum(hits.values()) == 1, "the other four must not be found by proximity"

    def test_the_tolerance_is_a_distance_and_not_the_whole_neighbourhood(self) -> None:
        """2.0 m is a disc, not the 4-cell square that reaches it.

        The discriminating case is the corner: (3, 3) cells away is 2.12 m and must NOT count,
        while (2, 3) is 1.80 m and must. Testing at (0, 5) instead proves nothing -- five cells
        is outside the search window altogether, so a square neighbourhood passes it too. That
        was the first version of this test, and a mutation replacing the disc with the square
        survived it.
        """
        cell_m, shape = 0.5, (1600, 1600)
        minx, _, _, maxy = mod.ZONE
        name, x, y = mod.VERIFIED_STEPS[0]
        row, col = int((maxy - y) / cell_m), int((x - minx) / cell_m)

        def found_with(dr: int, dc: int) -> bool:
            grid = np.zeros(shape, dtype=bool)
            grid[row + dr, col + dc] = True
            return {h.name: h.found for h in mod.g1_hits(grid, minx, maxy, cell_m)}[name]

        assert found_with(0, 4), "4 cells on an axis is exactly 2.0 m and is inside"
        assert found_with(2, 3), "1.80 m is inside"
        assert not found_with(3, 3), "2.12 m is outside the disc but inside the square"
        assert not found_with(0, 5), "beyond the search window entirely"

    def test_a_location_outside_the_extent_is_not_reported_as_absent(self) -> None:
        """The P4-window leg found this: four of the five steps lie outside a 150 m window, and
        `found=False` for them is byte-identical to a step present in the extent and missing from
        the population. One is a question the cache cannot answer; the other is a failure."""
        minx, _, _, maxy = mod.ZONE
        small = np.zeros((300, 300), dtype=bool)

        hits = {h.name: h for h in mod.g1_hits(small, minx, maxy, 0.5)}

        assert sum(h.inside for h in hits.values()) < len(hits), "the fixture must clip some"
        for hit in hits.values():
            if not hit.inside:
                assert not hit.found, "an unanswerable location is never a hit"

    def test_a_location_whose_disc_is_truncated_is_not_answerable(self) -> None:
        """The third face of the conflation, and the one the extent fix left open.

        `inside` used to test the centre cell alone, so a location four cells from the crop edge
        was searched over a silently truncated disc -- and a miss there was printed as a refusal
        when the S2 cell that would satisfy it may simply be outside the frame.
        """
        cell_m = 0.5
        minx, _, _, maxy = mod.ZONE
        _, x, y = mod.VERIFIED_STEPS[0]
        row, col = int((maxy - y) / cell_m), int((x - minx) / cell_m)
        # An array ending two cells past the location: the centre is in, the 4-cell disc is not.
        clipped = np.zeros((row + 3, col + 3), dtype=bool)

        hit = {h.name: h for h in mod.g1_hits(clipped, minx, maxy, cell_m)}[
            mod.VERIFIED_STEPS[0][0]
        ]

        assert not hit.inside, "the disc is truncated, so the location is not searchable"
        assert hit.centre_inside, "but the centre IS in frame -- the two reasons are different"

    def test_a_location_outside_the_frame_is_not_called_truncated(self) -> None:
        """`int()` truncates toward zero, so a location up to one cell north or west of the frame
        came back as row 0 and was printed as a truncated neighbourhood -- a false reason at the
        exact boundary the field exists to draw. Measured at 0.3 m out, where it said so."""
        _, x, y = mod.VERIFIED_STEPS[0]

        for out_m in (0.3, 0.9, 2.0):
            hit = mod.g1_hits(np.zeros((100, 100), dtype=bool), x + out_m, y - out_m, 0.5)[0]

            assert not hit.inside, out_m
            assert not hit.centre_inside, f"{out_m} m outside the frame is not 'truncated'"

    def test_the_two_reasons_are_printed_apart(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The strings themselves, because a reader acts on them, and BOTH arms.

        The first version asserted only that the truncated string was absent from a run where no
        location has its centre in frame -- which deleting the branch satisfies. The second
        fixture is 538 columns wide -- SMRF needs whole 2x2 blocks, so not the 537 an earlier
        draft of this sentence claimed -- and the first verified step sits at column 534, so its
        centre is in frame and its four-cell disc, reaching 538, is not.
        """
        far = np.where(np.mgrid[0:200, 0:200][1] >= 100, 2.6, 0.0).astype(np.float64)
        mod.main(["--reference", str(_cache(tmp_path / "small.npz", far))])
        out = capsys.readouterr().out

        assert "outside this cache's extent" in out
        assert "neighbourhood truncated at the frame edge" not in out, (
            "no location here has its centre in frame"
        )

        edge = np.where(np.mgrid[0:200, 0:538][1] >= 260, 2.6, 0.0).astype(np.float64)
        mod.main(["--reference", str(_cache(tmp_path / "edge.npz", edge))])
        out = capsys.readouterr().out

        # Both blocks print it -- G1's table and G3's -- so counting is what catches a fix that
        # reaches one of them. Asserting mere presence let a mutation of the G1 branch survive;
        # `>= 2` would let it survive again if the fixture ever admitted a second truncated
        # location, so the count is exact and the fixture is built to hold exactly one.
        assert out.count("neighbourhood truncated at the frame edge") == 2, out[-900:]

    def test_every_location_is_inside_the_full_zone(self) -> None:
        """The complement: over Zone Z's own extent nothing is out of frame, so a FAIL there is
        a real one."""
        minx, _, _, maxy = mod.ZONE

        hits = mod.g1_hits(np.zeros((1600, 1600), dtype=bool), minx, maxy, 0.5)

        assert all(h.inside for h in hits)

    def test_g3_reads_the_cell_that_satisfied_g1_not_the_centre(self) -> None:
        """G1 accepts a hit anywhere in the 2 m disc; G3 must read its residual there.

        Reading the centre reports `nan` -- undefined -- for a location G1 passed through a
        neighbour, and prints it as a failure. A mutation putting the centre back survives every
        other test in this file.
        """
        cell_m, shape = 0.5, (1600, 1600)
        minx, _, _, maxy = mod.ZONE
        name, x, y = mod.VERIFIED_STEPS[0]
        row, col = int((maxy - y) / cell_m), int((x - minx) / cell_m)
        population = np.zeros(shape, dtype=bool)
        population[row, col + 4] = True
        residual = np.full(shape, np.nan)
        residual[row, col + 4] = 0.9

        hit = {h.name: h for h in mod.g1_hits(population, minx, maxy, cell_m, residual=residual)}[
            name
        ]

        assert hit.found
        assert (hit.hit_row, hit.hit_col) == (row, col + 4)
        assert hit.residual == 0.9, "the centre holds nan; reading it would print a false failure"


class TestG2:
    def test_g2_requires_every_ramp_geometry_permits_and_no_more(self) -> None:
        """Two of the twelve cannot fire at all, and the rule now says which.

        A 7-cell window separates cells by 3.0 m along an axis, so an axis-aligned ramp needs
        39.8 deg to span 2.5 m; 31 and 35 deg cannot. The pre-registration's "S1 must be
        non-empty", read per ramp, was unsatisfiable by geometry before the run -- and the code's
        first version hid it behind `>= 8`, a constant in no document.
        """
        verdict = mod.g2_verdict(cell_m=0.5)

        assert verdict.permitted == 10
        assert verdict.reached_s1 == verdict.permitted
        assert verdict.entered_s2 == 0
        assert verdict.passed

    def test_the_two_ramps_geometry_forbids_are_the_shallow_axis_aligned_ones(self) -> None:
        forbidden = [
            (deg, diagonal)
            for deg in mod.G2_DEGREES
            for diagonal in (False, True)
            if not mod.ramp_can_reach(deg, diagonal, 7, 0.5, 2.5)
        ]

        assert forbidden == [(31.0, False), (35.0, False)]

    def test_a_ramp_that_should_have_fired_and_did_not_fails_g2(self) -> None:
        """The half `>= 8` silently accepted: a regression killing one permitted ramp."""
        assert not mod.G2Verdict(reached_s1=9, entered_s2=0, permitted=10, of_n=12).passed

    def test_an_instrument_that_selects_nothing_fails_g2(self) -> None:
        """The half that stops a broken instrument passing by rejecting everything."""
        verdict = mod.g2_verdict(cell_m=0.5, step_threshold_m=1000.0)

        assert verdict.reached_s1 == 0
        assert verdict.permitted == 0
        assert verdict.entered_s2 == 0
        assert not verdict.passed, "empty S1 is a broken instrument, not a clean must-not-fire"

    def test_a_ramp_reaching_s2_fails_g2(self) -> None:
        """The other half of the rule, asserted on the verdict itself.

        No parameter can express "no planarity term": a perfect plane reads 0.000, so every
        positive threshold rejects it, and `sharp_step_population` refuses a non-positive one.
        The state is reachable only by deleting the term -- which is a mutation, and is CAUGHT
        by the P4-window tests. What is testable here is that the verdict would refuse it.
        """
        assert not mod.G2Verdict(reached_s1=10, entered_s2=1, permitted=10, of_n=12).passed

    def test_a_non_positive_threshold_is_refused_rather_than_quietly_adjusted(self) -> None:
        """The first version of this script coerced it to 1e-12 to get past the guard, which is
        production code shaped by a test. The guard reaches through instead."""
        with pytest.raises(ValueError, match="residual_min_m"):
            mod.g2_verdict(cell_m=0.5, residual_min_m=0.0)


class TestTheInstrumentMeasuresTheFilterThatShips:
    """The lock `tests/test_compare_ground_filters.py` has, extended to this file.

    The first version of `measured_basis` retyped all six -- under a comment warning against
    exactly that. Nothing would have failed: if `--max-elevation-m` moves again (it has once,
    3.0 -> 3.5), this script would keep computing a different basis and the record's 94.5% and
    93.7% would quietly stop describing the shipped filter.
    """

    def test_the_four_retired_parameters_come_from_the_dataclass(self) -> None:
        from microrelief.ground import GroundParams

        source = SCRIPT.read_text()

        assert "GroundParams()" in source
        assert "GroundParams(4.0" not in source
        assert (
            GroundParams().max_window_m,
            GroundParams().slope_threshold,
            GroundParams().elevation_threshold_m,
            GroundParams().max_elevation_m,
        ) == (4.0, 0.3, 0.3, 3.5), "the shipped configuration moved; this record's basis moved"

    def test_the_two_shared_parameters_match_the_shipped_cli(self) -> None:
        """Declared on `compare_ground_filters`'s parsers and nowhere else, so they are compared
        against every declaration there rather than against one."""
        import re

        sibling = (ROOT / "scripts" / "compare_ground_filters.py").read_text()
        for flag, ours in (
            ("--k-min-returns", mod.BASIS_K_MIN_RETURNS),
            ("--d-max-interp-m", mod.BASIS_D_MAX_INTERP_M),
        ):
            declared = set(re.findall(rf'"{flag}".*?default=([0-9.]+)', sibling))
            assert declared, flag
            assert len(declared) == 1, f"{flag} is declared with {declared} -- the file disagrees"
            assert float(declared.pop()) == float(ours), flag

    def test_the_smrf_reference_matches_the_shipped_cli(self) -> None:
        """Against the CLI's declarations, because the dataclass cannot be its own control.

        The first version asserted `SmrfParams() == mod.SMRF_REFERENCE`, and `SMRF_REFERENCE`
        *is* `SmrfParams()` -- both sides move together. Measured: changing `slope` to 0.25 in
        `src/microrelief/smrf.py` left all 91 tests in this file and its sibling green while this
        script would compute a different SMRF and republish different retention. Written in the
        round whose headline finding was a test that could not fail.
        """
        import re

        sibling = (ROOT / "scripts" / "compare_ground_filters.py").read_text()
        for flag, ours in (
            ("--smrf-cell", mod.SMRF_REFERENCE.cell),
            ("--smrf-slope", mod.SMRF_REFERENCE.slope),
            ("--smrf-scalar", mod.SMRF_REFERENCE.scalar),
            ("--smrf-threshold", mod.SMRF_REFERENCE.threshold),
        ):
            declared = set(re.findall(rf'"{flag}".*?default=([0-9.]+)', sibling))
            assert declared, flag
            assert len(declared) == 1, f"{flag} is declared with {declared} -- the file disagrees"
            assert float(declared.pop()) == float(ours), flag
        declared_window = set(re.findall(r'"--smrf-window".*?default=([^,)]+)', sibling))
        assert declared_window == {"None"}, (
            f"the shipped CLI declares --smrf-window {declared_window}; this script would run "
            f"SMRF at 18*cell and republish retention for a filter nobody runs"
        )
        assert mod.SMRF_REFERENCE.window is None
        # Against the sibling, not against a literal: `SMRF_REFERENCE` is `SmrfParams()`, so
        # comparing its `cut` to 0.0 is the dataclass being its own control -- the pattern this
        # class exists to reject, surviving one field over.
        assert "--smrf-cut" not in sibling, (
            "the shipped CLI now declares a cut; this script would run SMRF without it"
        )
        assert mod.SMRF_REFERENCE.cut == 0.0
        assert "SmrfParams(cell=" not in SCRIPT.read_text()


class TestReadCache:
    """Two producers write two schemas, and neither names its fields like the other."""

    def test_it_reads_the_build_cache(self, tmp_path: Path) -> None:
        result = mod.read_cache(_cache(tmp_path / "b.npz", np.zeros((8, 8))))

        assert result.shape_name == "measure_risers build"
        assert result.pdal_ground is None
        assert result.cell_m == 0.5
        assert result.surface.shape == (8, 8)

    def test_it_reads_the_reference_cache_and_finds_pdals_answer(self, tmp_path: Path) -> None:
        path = tmp_path / "r.npz"
        np.savez_compressed(
            path,
            min_z_ground_asprs=np.zeros((4, 4), dtype=np.float32),
            min_z_all=np.zeros((4, 4), dtype=np.float32),
            max_z_all=np.zeros((4, 4), dtype=np.float32),
            n_all=np.ones((4, 4), dtype=np.int32),
            n_ground_asprs=np.ones((4, 4), dtype=np.int32),
            n_reference_ground=np.array([[0, 1, 0, 0]] * 4, dtype=np.int32),
            provenance=json.dumps(
                {"grid": {"origin_x": -20210.0, "origin_y": 256395.0, "cell": 0.5}}
            ),
        )

        result = mod.read_cache(path)

        assert result.shape_name == "compare_ground_filters reference"
        assert result.pdal_ground is not None
        assert result.pdal_ground.sum() == 4
        assert (result.origin_x, result.origin_y) == (-20210.0, 256395.0)

    def test_a_build_cache_from_before_the_all_returns_surface_is_refused_by_name(
        self, tmp_path: Path
    ) -> None:
        """The failure mode the two-shape reader exists to remove, one version back: a cache
        written before `min_z_all` was kept would die on a bare KeyError naming one field."""
        path = tmp_path / "old.npz"
        np.savez_compressed(
            path,
            min_z_ground=np.zeros((4, 4), dtype=np.float32),
            n_ground=np.ones((4, 4), dtype=np.int32),
            origin_x=-20400.0,
            origin_y=256400.0,
            cell=0.5,
            crs_epsg=3763,
        )

        with pytest.raises(ValueError, match="before the all-returns surface"):
            mod.read_cache(path)

    def test_a_cache_of_neither_shape_is_refused_by_name(self, tmp_path: Path) -> None:
        """A KeyError naming one field would read like a corrupt file, not the wrong cache."""
        path = tmp_path / "x.npz"
        np.savez_compressed(path, something_else=np.zeros(3))

        with pytest.raises(ValueError, match="neither cache shape"):
            mod.read_cache(path)


class TestRetention:
    def test_retention_is_the_share_of_the_population_the_filter_keeps(self) -> None:
        keep = np.array([[True, True, False, True]])
        population = np.array([[True, True, True, False]])

        assert mod.retention(keep, population) == pytest.approx(200.0 / 3.0)

    def test_an_empty_population_reports_no_number_rather_than_dividing(self) -> None:
        keep = np.ones((2, 2), dtype=bool)

        assert np.isnan(mod.retention(keep, np.zeros((2, 2), dtype=bool)))

    def test_cells_outside_the_population_do_not_count(self) -> None:
        """A retention computed over the whole grid would report the filter's global behaviour
        and call it the population's."""
        keep = np.array([[False, True, True, True]])
        population = np.array([[True, False, False, False]])

        assert mod.retention(keep, population) == pytest.approx(0.0)


class TestG3:
    def test_g3_compares_against_the_median_and_can_fail(self) -> None:
        residual = np.full((10, 10), np.nan)
        s1 = np.zeros((10, 10), dtype=bool)
        s1[0, :] = True
        residual[0, :] = 0.5

        assert mod.g3_exceeds_median(0.9, residual, s1)
        assert not mod.g3_exceeds_median(0.4, residual, s1)
        assert not mod.g3_exceeds_median(float("nan"), residual, s1)


class TestExitCodes:
    def test_an_empty_s1_exits_2_rather_than_reporting_a_pass(self, tmp_path: Path) -> None:
        cache = _cache(tmp_path / "flat.npz", np.zeros((200, 200), dtype=np.float64))

        assert mod.main(["--reference", str(cache)]) == 2

    def test_a_wall_far_from_every_location_fails_G1_in_frame(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The exit-1 branch that is a REFUSAL, not an unanswerable question.

        The first version of this test used a 200x200 fixture, on which all five locations are
        outside the extent -- so it exercised the not-evaluable branch and never reached
        `failures.append("G1")` at all. The grid here spans the whole zone, so every location is
        in frame and a wall elsewhere is a genuine miss.
        """
        surface = np.where(np.mgrid[0:1600, 0:1600][1] >= 800, 2.6, 0.0).astype(np.float64)
        cache = _cache(tmp_path / "wall.npz", surface)

        assert mod.main(["--reference", str(cache)]) == 1

        out = capsys.readouterr().out

        assert _summary(out).startswith("FAIL:"), _summary(out)
        assert "in frame and not in S2" in _summary(out)
        assert "NOT EVALUABLE" not in out

    def test_a_run_with_both_states_names_both_in_the_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The summary line is what gets grepped into a record. An `elif` here dropped the
        unanswerable half whenever anything was refuted, at the one place a reader looks."""
        # 900 columns: the locations at columns 534 and 784 are in frame, the three past column
        # 960 are not, and a wall at column 450 misses both of the in-frame ones.
        surface = np.where(np.mgrid[0:1600, 0:900][1] >= 450, 2.6, 0.0).astype(np.float64)
        cache = _cache(tmp_path / "both.npz", surface)

        assert mod.main(["--reference", str(cache)]) == 1

        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln.startswith(("FAIL:", "NOT EVALUABLE:"))]

        assert len(lines) == 2, lines
        assert lines[0].startswith("FAIL:") and "G1 and G3" in lines[1], lines

    def test_a_partial_extent_is_reported_as_not_evaluable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other exit-1 branch. Both exit 1, so the exit code cannot tell them apart -- the
        summary line has to, or merging the two states back together survives the suite."""
        surface = np.where(np.mgrid[0:200, 0:200][1] >= 100, 2.6, 0.0).astype(np.float64)
        cache = _cache(tmp_path / "small.npz", surface)

        assert mod.main(["--reference", str(cache)]) == 1

        out = capsys.readouterr().out
        summary = _summary(out)

        assert summary.startswith("NOT EVALUABLE:"), summary
        assert "G1 and G3" in summary, "G3 is unevaluated at the same locations and must be named"
        assert "Nothing there was refuted" in summary
        # Over the WHOLE output, not the summary: `main` prints FAIL before NOT EVALUABLE, so
        # `_summary` returns the latter whenever anything is unanswerable and a startswith check
        # on it is implied by the assertion three lines above. The round-4 rewrite of this test
        # replaced the scan with that tautology and unlocked the property it was named for.
        assert "\nFAIL:" not in out, "an unanswerable question is not a refutation"

    def test_a_g3_failure_is_recorded_as_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A location in S2 whose residual is below the S1 median.

        The first version of this test asserted on the fixture instead of running the
        instrument, so the line that records a G3 failure was still never executed and deleting
        it still survived. Checking the fixture is not checking the branch.
        """
        surface = np.zeros((1600, 1600), dtype=np.float64)
        _, cols = np.mgrid[0:1600, 0:1600]
        # A field of sharp walls: high residuals, so the S1 median is high.
        surface[cols % 40 >= 20] = 2.6
        # And at each verified location, a gentler 1.0 m riser: in S2 (0.455) but below it.
        minx, _, _, maxy = mod.ZONE
        for _, x, y in mod.VERIFIED_STEPS:
            r, c = int((maxy - y) / 0.5), int((x - minx) / 0.5)
            surface[r - 12 : r + 13, c - 12 : c + 13] = 0.0
            ramp = np.clip((np.arange(-12, 13) - (-1)) / 2.0, 0.0, 1.0) * 2.6
            surface[r - 12 : r + 13, c - 12 : c + 13] = ramp[None, :]

        median, hits = _run_predicates(surface)
        below = [h for h in hits if h.found and h.residual < median]
        assert below, f"the fixture must put a location below the median {median:.3f}"

        assert mod.main(["--reference", str(_cache(tmp_path / "g3.npz", surface))]) == 1

        summary = _summary(capsys.readouterr().out)

        assert summary.startswith("FAIL:"), summary
        assert "G3 (" in summary, "the G3 failure must reach the summary, not just the table"

    def test_an_s1_with_no_computable_residual_exits_2(self, tmp_path: Path) -> None:
        """S1 non-empty and not one residual computable is a broken instrument, like an empty S1
        -- five G3 failures for a reason that is not the measured one would read as a result."""
        surface = np.full((400, 400), np.nan)
        surface[::9, ::9] = 0.0
        surface[4::9, 4::9] = 2.6
        cache = _cache(tmp_path / "sparse.npz", surface)

        assert mod.main(["--reference", str(cache)]) == 2

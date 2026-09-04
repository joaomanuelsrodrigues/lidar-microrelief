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

    def test_every_location_is_inside_the_full_zone(self) -> None:
        """The complement: over Zone Z's own extent nothing is out of frame, so a FAIL there is
        a real one."""
        minx, _, _, maxy = mod.ZONE

        hits = mod.g1_hits(np.zeros((1600, 1600), dtype=bool), minx, maxy, 0.5)

        assert all(h.inside for h in hits)


class TestG2:
    def test_g2_requires_both_halves(self) -> None:
        """A ramp must reach S1 and be rejected from S2."""
        verdict = mod.g2_verdict(cell_m=0.5)

        assert verdict.reached_s1 >= 8
        assert verdict.entered_s2 == 0
        assert verdict.passed

    def test_an_instrument_that_selects_nothing_fails_g2(self) -> None:
        """The half that stops a broken instrument passing by rejecting everything."""
        verdict = mod.g2_verdict(cell_m=0.5, step_threshold_m=1000.0)

        assert verdict.reached_s1 == 0
        assert verdict.entered_s2 == 0
        assert not verdict.passed, "empty S1 is a broken instrument, not a clean must-not-fire"

    def test_a_ramp_reaching_s2_fails_g2(self) -> None:
        """The other half of the rule, asserted on the verdict itself.

        No parameter can express "no planarity term": a perfect plane reads 0.000, so every
        positive threshold rejects it, and `sharp_step_population` refuses a non-positive one.
        The state is reachable only by deleting the term -- which is a mutation, and is CAUGHT
        by the P4-window tests. What is testable here is that the verdict would refuse it.
        """
        assert not mod.G2Verdict(reached_s1=12, entered_s2=1, of_n=12).passed

    def test_a_non_positive_threshold_is_refused_rather_than_quietly_adjusted(self) -> None:
        """The first version of this script coerced it to 1e-12 to get past the guard, which is
        production code shaped by a test. The guard reaches through instead."""
        with pytest.raises(ValueError, match="residual_min_m"):
            mod.g2_verdict(cell_m=0.5, residual_min_m=0.0)


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

    def test_a_surface_that_fails_the_predicates_exits_1(self, tmp_path: Path) -> None:
        """A single wall far from every verified location: S1 is non-empty, so the instrument
        is not broken, and G1 must fail."""
        surface = np.where(np.mgrid[0:200, 0:200][1] >= 100, 2.6, 0.0).astype(np.float64)
        cache = _cache(tmp_path / "wall.npz", surface)

        assert mod.main(["--reference", str(cache)]) == 1

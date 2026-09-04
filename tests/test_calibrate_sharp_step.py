"""The derivation's own rules, on geometry whose answer is known before it runs.

`scripts/calibrate_sharp_step.py` produces the three curves `docs/sharp-step-preregistration.md`
cites for its threshold. Nothing here reads data: if any of it depended on the delivery, the
threshold could be an outcome of the measurement it is supposed to precede.

Each curve is tested where its value is forced by the geometry -- a riser spread across the whole
window is a plane and must read zero; noise of a known scale must be reported at about that
scale -- rather than against the numbers the script happens to print.
"""

import functools
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calibrate_sharp_step.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("calibrate_sharp_step", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


class TestStepFloor:
    def test_the_floor_is_below_the_centred_value_because_of_sub_cell_offsets(self) -> None:
        """A boundary falling inside a cell gives that cell an intermediate value, which is
        closer to a plane. Taking only the aligned case would overstate the floor.

        Evaluated at the gate height itself: a step must exceed 2.5 m to be a candidate, so the
        floor at 2.5 m is the infimum of what any candidate step can read, which is the
        conservative side to derive a threshold from.
        """
        floor = mod.step_floor(2.5, window_cells=7, cell_m=0.5)

        assert 0.40 < floor < 0.50


class TestWidthCurve:
    """Each row names a width, and the numbers are what a cell IN THE POPULATION can read."""

    CENTRED = {0.5: 0.455, 1.0: 0.455, 1.5: 0.270, 2.0: 0.208, 2.5: 0.083, 3.0: 0.000}

    @staticmethod
    @functools.cache
    def _curve() -> dict[float, tuple[float, float, float, int]]:
        """Cached: the sweep is 46 orientations x 400 phases and costs 20 s, and every test in
        this class needs it with identical arguments.

        Uncached the file took 148 s. The first version of this cache still left two call sites
        going direct -- they had the same arguments and did not go through the helper -- so the
        file measured 59 s, not the 21 s the commit body published. Counting the callers is the
        check; measuring the file is the control.
        """
        return {
            w: (c, lo, hi, n)
            for w, c, lo, hi, n in mod.width_curve(2.6, window_cells=7, cell_m=0.5)
        }

    def test_the_centred_readings_are_the_ones_the_records_publish(self) -> None:
        """Pinned by value, because the documents quote them. An earlier version of this class
        asserted on the band's minimum while claiming to check the centred case."""
        curve = self._curve()

        for width, expected in self.CENTRED.items():
            assert curve[width][0] == pytest.approx(expected, abs=5e-4), width

    def test_a_riser_spread_across_the_window_can_be_exactly_planar(self) -> None:
        """`can be`, not `is`: centred it reads 0.000, and elsewhere in the population it does
        not. The claim was written as a property of the width; it is a property of position."""
        curve = self._curve()

        assert curve[3.0][0] == pytest.approx(0.0, abs=1e-9), "centred"
        assert curve[3.0][2] > 0.0, "and at other candidate positions it is not exactly planar"

    def test_where_the_threshold_falls_is_a_band_not_a_line(self) -> None:
        """Up to 1.0 m a riser is in wherever it sits; 1.5 m and 2.0 m straddle R; 2.5 m and
        wider are out wherever they sit.

        Two earlier versions of this assertion were narrower and each was more comfortable:
        "the last width that survives is 1.0 m" (centred only), then "2.0 m and wider are out at
        every position" (axis-aligned only, where 2.0 m tops out at 0.295). At 45 degrees a
        2.0 m riser reads 0.376 and is in S2.
        """
        curve = self._curve()
        r = mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

        assert curve[1.0][1] >= r, "1.0 m: in at every candidate position"
        assert curve[1.5][1] < r <= curve[1.5][2], "1.5 m: straddles"
        assert curve[2.0][1] < r <= curve[2.0][2], "2.0 m: straddles, once orientation is swept"
        assert curve[2.5][2] < r, "2.5 m: out at every candidate position"

    def test_the_published_band_edges_are_pinned_to_three_decimals(self) -> None:
        """By value, because the records quote them, and because an interval assertion cannot
        tell the published margin from one twenty times smaller. The first version of this test
        asserted `0.29 < max < 0.30`, which admits any margin between 0 and 0.01 while its own
        docstring named 0.005.
        """
        expected = {
            0.5: (0.339, 0.719),
            1.0: (0.388, 0.587),
            1.5: (0.270, 0.457),
            2.0: (0.190, 0.376),
            2.5: (0.083, 0.289),
            3.0: (0.000, 0.190),
        }
        curve = self._curve()

        for width, (low, high) in expected.items():
            assert curve[width][1] == pytest.approx(low, abs=5e-4), width
            assert curve[width][2] == pytest.approx(high, abs=5e-4), width

    def test_the_widest_straddling_row_is_two_metres_and_the_margin_is_named(self) -> None:
        """The number the record states, locked. 2.5 m clears R by 0.011 m -- the narrowest true
        margin on the table, and the one a reader is entitled to see.

        It read 0.012 under a four-sample orientation grid. One degree gives 0.011: the third
        decimal of a published band was a property of the sampling, which is the same shape as
        the two narrowings the sweep exists to correct.
        """
        curve = self._curve()
        r = mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

        assert r - curve[2.5][2] == pytest.approx(0.011, abs=5e-4)

    def test_the_centred_curve_falls_monotonically(self) -> None:
        centred = [row[0] for row in self._curve().values()]

        assert centred == sorted(centred, reverse=True)

    def test_the_published_candidate_shares_are_pinned(self) -> None:
        """The grid-invariant half of the `sampled` column, which the record publishes.

        The count is a property of `WIDTH_PHASES` x `WIDTH_ORIENTATIONS`. The share is much less
        so, but it is **not** invariant either: measured between the 1 and 0.5 degree grids it
        moves 0.03-0.08 percentage points, enough to change the last published digit of two of
        the six (83.8 -> 83.9, 49.2 -> 49.3). So the tolerance here is 0.15 pp -- wider than that
        drift -- and this test is not evidence of invariance. Only the band edges are invariant,
        and `test_the_band_edges_are_invariant_under_the_grid` is where that is asserted.

        Pinned at all because a document quotes these figures, and because the first hand-check
        of them used 800 phases where there are 400 and would have published half their size.
        """
        swept = len(mod.WIDTH_PHASES) * len(mod.WIDTH_ORIENTATIONS)
        expected = {0.5: 83.8, 1.0: 72.3, 1.5: 60.8, 2.0: 49.2, 2.5: 37.7, 3.0: 26.2}
        curve = self._curve()

        for width, share in expected.items():
            assert 100.0 * curve[width][3] / swept == pytest.approx(share, abs=0.15), width

    def test_the_band_edges_are_invariant_under_the_grid(self) -> None:
        """The claim the record actually rests on, measured rather than asserted.

        Refining the orientation grid from 1 degree to 0.5 (46 -> 91 orientations, 18,400 ->
        36,400 positions swept) leaves every band edge identical. The candidate counts nearly
        double and the shares move in their last published digit; the edges do not move at all.
        That is what makes the published table a statement about geometry.
        """
        import numpy as np

        coarse = self._curve()
        original = mod.WIDTH_ORIENTATIONS
        try:
            mod.WIDTH_ORIENTATIONS = tuple(float(d) for d in np.arange(0.0, 45.0001, 0.5))
            fine = {w: (c, lo, hi, n) for w, c, lo, hi, n in mod.width_curve(2.6, 7, 0.5)}
        finally:
            mod.WIDTH_ORIENTATIONS = original
        assert original == mod.WIDTH_ORIENTATIONS, "the grid must be restored"

        assert len(fine) == len(coarse)
        for width, (_, low, high, count) in coarse.items():
            assert fine[width][1] == pytest.approx(low, abs=1e-6), f"min at {width}"
            assert fine[width][2] == pytest.approx(high, abs=1e-6), f"max at {width}"
            assert fine[width][3] > 1.9 * count, "the counts, meanwhile, nearly double"

    def test_only_candidate_positions_are_counted(self) -> None:
        """The restriction that makes the band a statement about the population.

        Off-centre positions read HIGHER residuals precisely where the window's range drops under
        the threshold -- cells that are not in S1 at all. Counting them would overstate what the
        population can hold, so the phase count must shrink as the riser widens and every
        counted position must be a candidate.
        """
        phases = [row[3] for row in self._curve().values()]

        assert phases == sorted(phases, reverse=True)
        assert all(n > 0 for n in phases)
        assert phases[-1] < phases[0] / 2, "a 3.0 m riser is a candidate far less often"


class TestTheRecordQuotesTheInstrument:
    """The third copy of these figures, and the one nothing was checking.

    They live in `main`'s output, in this file's literals, and in the prose of
    `docs/sharp-step-result.md`. Only the first two were coupled: change the sweep, this file
    goes red, `expected` gets updated, and the record stays stale and green.
    """

    RECORD = ROOT / "docs" / "sharp-step-result.md"

    def test_every_row_of_the_published_table_is_what_the_script_computes(self) -> None:
        published = self.RECORD.read_text()
        rows = mod.width_curve(2.6, window_cells=7, cell_m=0.5)
        swept = len(mod.WIDTH_PHASES) * len(mod.WIDTH_ORIENTATIONS)
        assert rows, "the sweep produced nothing to check the record against"

        for width_m, centred, low, high, count in rows:
            share = 100.0 * count / swept
            expected = (
                f"{width_m:.1f} m      {centred:.3f}    {low:.3f}    {high:.3f}"
                f"     {count:>5d}       {share:.1f}%"
            )
            assert expected in published, f"row {width_m} m is not in the record as:\n{expected}"


class TestNoiseCurve:
    def test_noise_on_a_ramp_is_reported_at_about_its_own_scale(self) -> None:
        curve = dict(mod.noise_curve(35.0, (0.1, 0.2, 0.3), window_cells=7, cell_m=0.5, draws=200))

        for sigma, residual in curve.items():
            assert residual == pytest.approx(sigma, abs=0.05), sigma

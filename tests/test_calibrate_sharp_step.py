"""The derivation's own rules, on geometry whose answer is known before it runs.

`scripts/calibrate_sharp_step.py` produces the three curves `docs/sharp-step-preregistration.md`
cites for its threshold. Nothing here reads data: if any of it depended on the delivery, the
threshold could be an outcome of the measurement it is supposed to precede.

Each curve is tested where its value is forced by the geometry -- a riser spread across the whole
window is a plane and must read zero; noise of a known scale must be reported at about that
scale -- rather than against the numbers the script happens to print.
"""

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
    def _curve() -> dict[float, tuple[float, float, float, int]]:
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
        """Up to 1.0 m a riser is in wherever it sits; 1.5 m straddles R; 2.0 m and wider are out
        wherever they sit. "The last width that survives is 1.0 m" was true of the centred case
        and of nothing else.
        """
        curve = self._curve()
        r = mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

        assert curve[1.0][1] >= r, "1.0 m: in at every candidate position"
        assert curve[1.5][1] < r <= curve[1.5][2], "1.5 m: straddles"
        assert curve[2.0][2] < r, "2.0 m: out at every candidate position"

    def test_the_two_metre_row_clears_the_threshold_by_five_thousandths(self) -> None:
        """The margin the record has to state. It is 0.005 m, not the 0.027 an eleven-point
        sweep over one cell of phase reported, and it is the reason the sweep was widened.
        """
        curve = self._curve()

        assert 0.29 < curve[2.0][2] < mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

    def test_the_centred_curve_falls_monotonically(self) -> None:
        centred = [c for _, c, _, _, _ in mod.width_curve(2.6, window_cells=7, cell_m=0.5)]

        assert centred == sorted(centred, reverse=True)

    def test_only_candidate_positions_are_counted(self) -> None:
        """The restriction that makes the band a statement about the population.

        Off-centre positions read HIGHER residuals precisely where the window's range drops under
        the threshold -- cells that are not in S1 at all. Counting them would overstate what the
        population can hold, so the phase count must shrink as the riser widens and every
        counted position must be a candidate.
        """
        rows = mod.width_curve(2.6, window_cells=7, cell_m=0.5)
        phases = [n for _, _, _, _, n in rows]

        assert phases == sorted(phases, reverse=True)
        assert all(n > 0 for n in phases)
        assert phases[-1] < phases[0] / 2, "a 3.0 m riser is a candidate far less often"


class TestNoiseCurve:
    def test_noise_on_a_ramp_is_reported_at_about_its_own_scale(self) -> None:
        curve = dict(mod.noise_curve(35.0, (0.1, 0.2, 0.3), window_cells=7, cell_m=0.5, draws=200))

        for sigma, residual in curve.items():
            assert residual == pytest.approx(sigma, abs=0.05), sigma

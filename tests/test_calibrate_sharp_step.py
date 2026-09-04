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
    @staticmethod
    def _curve() -> dict[float, tuple[float, float, float]]:
        return {w: (c, lo, hi) for w, c, lo, hi in mod.width_curve(2.6, window_cells=7, cell_m=0.5)}

    def test_a_riser_spread_across_the_window_can_be_exactly_planar(self) -> None:
        """`can be`, not `is`. At one alignment it reads 0.000; the claim was written as a
        property of the width, and it is a property of where the boundary falls."""
        curve = self._curve()

        assert curve[0.5][1] > 0.4
        assert curve[3.0][1] == pytest.approx(0.0, abs=1e-9)
        assert curve[3.0][2] > 0.1, "and at other offsets it is not planar at all"

    def test_the_threshold_crossing_depends_on_the_sub_cell_offset(self) -> None:
        """The declared limitation's operative number, and its width.

        Centred, 1.0 m survives R and 1.5 m does not. Swept over offsets the two bands overlap
        the threshold from either side, so "the last width that survives is 1.0 m" is true of the
        centred alignment and of nothing else.
        """
        curve = self._curve()
        r = mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

        assert curve[1.0][0] >= r and curve[1.5][0] < r, "centred"
        assert curve[1.0][1] >= r, "1.0 m survives at every offset"
        assert curve[1.5][1] < r <= curve[1.5][2], "1.5 m straddles it"

    def test_the_centred_curve_falls_monotonically(self) -> None:
        centred = [c for _, c, _, _ in mod.width_curve(2.6, window_cells=7, cell_m=0.5)]

        assert centred == sorted(centred, reverse=True)

    def test_every_band_contains_its_centred_value(self) -> None:
        """A min/max that did not bracket the centred reading would mean the sweep and the
        centred case are not computing the same thing."""
        for _, centred, low, high in mod.width_curve(2.6, window_cells=7, cell_m=0.5):
            assert low <= centred <= high


class TestNoiseCurve:
    def test_noise_on_a_ramp_is_reported_at_about_its_own_scale(self) -> None:
        curve = dict(mod.noise_curve(35.0, (0.1, 0.2, 0.3), window_cells=7, cell_m=0.5, draws=200))

        for sigma, residual in curve.items():
            assert residual == pytest.approx(sigma, abs=0.05), sigma

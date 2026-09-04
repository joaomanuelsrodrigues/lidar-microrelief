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
    def test_a_riser_spread_across_the_window_becomes_planar(self) -> None:
        curve = dict(mod.width_curve(2.6, window_cells=7, cell_m=0.5))

        assert curve[0.5] > 0.4
        assert curve[3.0] == pytest.approx(0.0, abs=1e-9)

    def test_the_curve_crosses_the_threshold_between_one_and_one_and_a_half_metres(self) -> None:
        """The declared limitation's operative number, on the grid the instrument runs on."""
        curve = dict(mod.width_curve(2.6, window_cells=7, cell_m=0.5))

        assert curve[1.0] >= mod.cgf.SHARP_STEP_RESIDUAL_MIN_M
        assert curve[1.5] < mod.cgf.SHARP_STEP_RESIDUAL_MIN_M

    def test_the_curve_falls_monotonically(self) -> None:
        widths = [residual for _, residual in mod.width_curve(2.6, window_cells=7, cell_m=0.5)]

        assert widths == sorted(widths, reverse=True)


class TestNoiseCurve:
    def test_noise_on_a_ramp_is_reported_at_about_its_own_scale(self) -> None:
        curve = dict(mod.noise_curve(35.0, (0.1, 0.2, 0.3), window_cells=7, cell_m=0.5, draws=200))

        for sigma, residual in curve.items():
            assert residual == pytest.approx(sigma, abs=0.05), sigma

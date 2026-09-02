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
        import re

        found = {}
        for flag in TestDefaultsTrackTheShippedFilter.SHARED:
            m = re.search(
                rf'add_argument\(\s*"--{re.escape(flag)}",\s*type=\w+,\s*default=([0-9.]+)\)',
                source,
            )
            if m:
                found[flag] = m.group(1)
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

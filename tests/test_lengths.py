"""Every entry point that takes a length in metres refuses a non-finite or non-positive one.

A contract over the siblings, not a pile of unrelated tests. The same `x <= 0` hole appeared in
six places over three review rounds -- because `float("nan") <= 0` is False, so a NaN walks
through a positivity test and either dies later in `int(round(...))` / `math.floor(...)`, or does
not die at all:

* `precheck --cell inf` reported a confident "0.0% of cells expected empty", `--cell nan` printed
  `nan%`, both at exit 0;
* `precheck --max-void-fraction nan` accepted a tile with 99.99% expected void, because
  `void_at_f > nan` is False -- switching off the only refusal that command makes;
* `run --d-max-interp-m nan` published `measured 51.6% | interpolated 0.0% | undetermined 48.4%`
  against the true 51.6/42.3/6.1, and wrote a bare `NaN` token into the record, which Python's
  lenient reader accepts and any RFC 8259 parser rejects;
* `SmrfParams(window=0)` made the object stage flag nothing, taking a 20x20 fixture from 7 of
  400 cells ground to 259 of 400, no refusal.

The first version of this file listed its entry points by hand and claimed in its docstring to
cover "every" one. It did not -- three of the four above were missing -- and nothing could notice,
because the membership rule was memory. The population is DERIVED now: `_length_parameters()`
walks the package and finds every float parameter whose NAME says it is a length, and
`test_the_table_covers_every_length_parameter_in_the_package` asserts a partition -- covered
here, or exempted with a reason. A new length is a failing test, not a silent gap.
"""

import inspect
import math
import pkgutil
from importlib import import_module

import pytest

import microrelief
from microrelief.density import compute_basis, honesty_report
from microrelief.grid import GridError, grid_for_bounds
from microrelief.ground import GroundParams, classify_ground, windows_for
from microrelief.precheck import (
    PrecheckRefusal,
    check_tiles,
    estimate_tiles,
    expected_void_fraction,
)
from microrelief.smrf import (
    SmrfError,
    SmrfParams,
    block_factor,
    classify_ground_smrf,
    low_mask,
    max_radius_for,
    progressive_filter,
)

BAD = (float("nan"), float("inf"), float("-inf"), 0.0, -0.5)

# A parameter is a length if its name says so. Deliberately a NAME rule: the alternative is to
# read types, and every one of these is `float`, which is what let them diverge in the first
# place.
LENGTH_NAMES = ("cell", "window", "d_max_interp_m", "max_window_m", "max_elevation_m")

# Sites that refuse by DELEGATION: they hold no guard of their own and pass the length to one
# that does. Asserted to refuse, but not asserted on the message -- the message belongs to the
# delegate, and demanding it here would just copy the delegate's wording into a second place.
# Measured, not assumed: every one of these was run with NaN and refused.
DELEGATING = (
    (
        ("microrelief.density", "honesty_report", "cell"),
        lambda x: honesty_report(_basis(), _stats(), x, 4.0),
    ),
    (
        ("microrelief.smrf", "classify_ground_smrf", "cell"),
        lambda x: classify_ground_smrf(_z(), x, SmrfParams()),
    ),
    (
        ("microrelief.smrf", "progressive_filter", "cell"),
        lambda x: progressive_filter(_z(), x, 0.15, 18.0),
    ),
    (
        ("microrelief.smrf", "progressive_filter", "window"),
        lambda x: progressive_filter(_z(), 0.5, 0.15, x),
    ),
    (("microrelief.smrf", "low_mask", "cell"), lambda x: low_mask(_z(), x)),
    (("microrelief.smrf", "max_radius_for", "cell"), lambda x: max_radius_for(18.0, x)),
    (("microrelief.precheck", "check_tiles", "cell"), lambda x: check_tiles([_tile()], x, 0.4)),
    (
        ("microrelief.precheck", "estimate_tiles", "cell"),
        lambda x: estimate_tiles([_tile()], x, 0.4),
    ),
    (
        ("microrelief.ground", "classify_ground", "cell"),
        lambda x: classify_ground(_z32(), x, GroundParams()),
    ),
    (("microrelief.ground", "windows_for", "cell"), lambda x: windows_for(4.0, x)),
    (("microrelief.ground", "windows_for", "max_window_m"), lambda x: windows_for(x, 0.5)),
)

# Exempt, and why. A length that is not an entry-point argument at all -- a dataclass field whose
# arithmetic lives elsewhere -- is named here rather than left to be rediscovered.
EXEMPT = {
    ("microrelief.grid", "Grid", "cell"): (
        "a field of a frozen dataclass built by grid_for_bounds, which is covered above"
    ),
    ("microrelief.smrf", "SmrfParams", "window"): (
        "a dataclass field with no arithmetic of its own; the refusal lives in max_radius_for"
    ),
    ("microrelief.smrf", "SmrfParams", "cell"): ("same: the refusal lives in block_factor"),
    ("microrelief.ground", "GroundParams", "max_window_m"): (
        "the retired filter's pinned configuration, comparison arm only since 0.5.0; the "
        "function that consumes it, windows_for, is covered above"
    ),
    ("microrelief.ground", "GroundParams", "max_elevation_m"): (
        "as above: a pinned constant, consumed by classify_ground, which is covered above"
    ),
}


def _z():
    import numpy as np

    return np.full((4, 4), 100.0)


def _z32():
    import numpy as np

    return np.full((4, 4), 100.0, dtype=np.float32)


def _basis():
    import numpy as np

    from microrelief.density import BASIS_MEASURED

    return np.full((4, 4), BASIS_MEASURED, dtype=np.uint8)


def _tile():
    class _T:
        item_id = "x"
        density = 10.0
        flight_date = ""

    return _T()


def _length_parameters() -> set[tuple[str, str, str]]:
    """(module, callable, parameter) for every float parameter whose name says it is a length."""
    found: set[tuple[str, str, str]] = set()
    for info in pkgutil.walk_packages(microrelief.__path__, "microrelief."):
        module = import_module(info.name)
        for obj_name, obj in vars(module).items():
            if getattr(obj, "__module__", None) != info.name:
                continue
            if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                continue
            if obj_name.startswith("_"):
                continue
            try:
                signature = inspect.signature(obj)
            except (TypeError, ValueError):  # pragma: no cover - builtins and C types
                continue
            for param in signature.parameters.values():
                if param.name in LENGTH_NAMES:
                    found.add((info.name, obj_name, param.name))
    return found


# Each entry: the (module, callable, parameter) it covers, a label, the call as a one-argument
# lambda over the bad length, and the exception that entry point raises.
ENTRY_POINTS = (
    (
        ("microrelief.grid", "grid_for_bounds", "cell"),
        lambda x: grid_for_bounds(0.0, 0.0, 100.0, 100.0, x, 3763),
        GridError,
    ),
    (
        ("microrelief.smrf", "block_factor", "cell"),
        lambda x: block_factor(x, SmrfParams()),
        SmrfError,
    ),
    (
        ("microrelief.smrf", "block_factor", "params.cell"),
        lambda x: block_factor(0.5, SmrfParams(cell=x)),
        SmrfError,
    ),
    (
        ("microrelief.smrf", "max_radius_for", "window"),
        lambda x: max_radius_for(x, 0.5),
        SmrfError,
    ),
    (
        ("microrelief.precheck", "expected_void_fraction", "cell"),
        lambda x: expected_void_fraction(10.0, x, 0.4),
        ValueError,
    ),
    (
        ("microrelief.precheck", "expected_void_fraction", "density_pts_m2"),
        lambda x: expected_void_fraction(x, 0.5, 0.4),
        ValueError,
    ),
    (
        ("microrelief.density", "compute_basis", "d_max_interp_m"),
        lambda x: compute_basis(_ground(), _stats(), 0.5, 1, x),
        ValueError,
    ),
    (
        ("microrelief.density", "compute_basis", "cell"),
        lambda x: compute_basis(_ground(), _stats(), x, 1, 2.0),
        ValueError,
    ),
)


def _ground():
    import numpy as np

    out = np.zeros((4, 4), dtype=bool)
    out[1:3, 1:3] = True
    return out


def _stats():
    import numpy as np

    from microrelief.accumulate import CellStats

    return CellStats(
        n_all=np.ones((4, 4), dtype=np.int32),
        n_ground_asprs=np.zeros((4, 4), dtype=np.int32),
        min_z_all=np.full((4, 4), 100.0, dtype=np.float32),
        max_z_all=np.full((4, 4), 101.0, dtype=np.float32),
        min_z_ground_asprs=np.full((4, 4), np.nan, dtype=np.float32),
        n_outside=0,
    )


@pytest.mark.parametrize("bad", BAD, ids=str)
@pytest.mark.parametrize("site,call,error", ENTRY_POINTS, ids=lambda v: str(v))
def test_every_length_entry_point_refuses_a_bad_length(site, call, error, bad) -> None:
    with pytest.raises(error) as exc:
        call(bad)
    message = str(exc.value).lower()
    assert "positive" in message and "finite" in message, (
        f"{site} refused {bad} but the message does not say what a length must be: {exc.value}"
    )


@pytest.mark.parametrize("site,call,error", ENTRY_POINTS, ids=lambda v: str(v))
def test_every_length_entry_point_accepts_an_ordinary_length(site, call, error) -> None:
    """The quiet arm. A guard that refuses 0.5 m would refuse every real run."""
    call(0.5)


def test_the_table_covers_every_length_parameter_in_the_package() -> None:
    """The partition, and the reason this file is a contract rather than a list.

    Covered here, or exempt with a stated reason. Absence from both is the failure -- which is
    exactly the state `d_max_interp_m` and `window` were in while the docstring claimed "every".
    """
    covered = {site for site, _call, _error in ENTRY_POINTS} | {s for s, _c in DELEGATING}
    found = _length_parameters()
    assert found, "this check scanned nothing: the package walk found no length parameters"

    uncovered = {s for s in found if s not in covered and s not in EXEMPT}
    assert not uncovered, (
        f"{len(uncovered)} length parameter(s) neither covered nor exempted: {sorted(uncovered)} "
        "-- add an entry to ENTRY_POINTS, or an exemption to EXEMPT with the reason"
    )


def test_every_exemption_names_a_parameter_that_still_exists() -> None:
    """An exemption for a parameter that is gone is a hole nobody is watching."""
    found = _length_parameters()
    stale = sorted(s for s in EXEMPT if s not in found)
    assert not stale, f"exempted but no longer present: {stale} -- drop the exemption"


def test_the_ceiling_that_is_a_fraction_is_guarded_too() -> None:
    """Not a length, same mechanism: `void_at_f > nan` is False, so a NaN ceiling switched off
    the only refusal `precheck` makes. Measured: a tile with 99.99% expected void accepted."""
    from microrelief.precheck import TileEstimate

    tile = TileEstimate(
        item_id="x", density=0.001, flight_date="", void_open_ground=0.99, void_at_f=0.99
    )
    with pytest.raises(PrecheckRefusal):
        check_tiles([tile], 0.5, 0.4, max_void_fraction=0.35)
    with pytest.raises(ValueError, match="finite"):
        check_tiles([tile], 0.5, 0.4, max_void_fraction=float("nan"))


def test_a_bare_positivity_guard_would_fail_this_files_own_parameterisation() -> None:
    """The discriminator, on the package rather than on Python.

    This replaces a test that asserted `not (float("nan") <= 0)` and `not isfinite(nan)` -- true
    of Python, true with every guard in this package deleted, and presented in its own docstring
    as a discriminator. It was the third test written in this review arc that could not fail.

    What actually discriminates: NaN is in `BAD`, so the parameterised test above fails for any
    entry point whose guard is a bare positivity test. This states that dependency rather than
    restating float semantics.
    """
    assert any(math.isnan(b) for b in BAD), (
        "NaN must be in BAD, or a bare positivity guard passes every case in this file"
    )


@pytest.mark.parametrize("bad", BAD, ids=str)
@pytest.mark.parametrize("site,call", DELEGATING, ids=lambda v: str(v))
def test_every_delegating_site_refuses_a_bad_length(site, call, bad) -> None:
    """Refusal asserted, message not: the message is the delegate's, and copying it here would
    make two places that must agree out of one that already does."""
    with pytest.raises(ValueError):
        call(bad)

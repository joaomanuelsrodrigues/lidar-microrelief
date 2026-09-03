"""Every float a caller can hand this package is either guarded, delegating, or exempt by kind.

The same `x <= 0` hole appeared in nine places across four review rounds, because
`float("nan") <= 0` is False: a NaN walks through a positivity test and either dies later in
`int(round(...))` / `math.floor(...)`, or does not die at all. Measured, each one:

* `precheck --cell inf` reported a confident "0.0% of cells expected empty"; `--cell nan` printed
  `nan%`; both at exit 0.
* `precheck --max-void-fraction nan` accepted a tile with 99% expected void -- and so did **1.0**
  and **5.0**, because `void_at_f` is in [0, 1] by construction, so the first guard's
  finiteness-only check left the class it was written for.
* `run --d-max-interp-m nan` published `measured 51.6% | interpolated 0.0% | undetermined 48.4%`
  against the true 51.6/42.3/6.1, and wrote a bare `NaN` into the record.
* `SmrfParams(window=0)` and `window=inf` made the object stage flag nothing, because
  `range(1, radius + 1)` is empty at a radius of zero or less.
* `GroundParams(elevation_threshold_m=nan)` took a 20x20 fixture from 336/400 cells ground to
  400/400; `max_elevation_m=nan` took an 80x80 fixture with a 4.5 m plateau from 5824/6400 to
  6400/6400, because `min(finite, nan)` returns the finite operand -- a NaN cap REMOVES the cap.

Those last two are why this file's population rule changed. Its first version listed entry points
by hand; its second derived them from a hand-written tuple of five length-ish NAMES and claimed in
its docstring to find "every float parameter whose name says it is a length". Both HIGH findings of
the fourth round were parameters that tuple did not contain -- including one standing under an
EXEMPTION whose stated reason ("consumed by classify_ground, which is covered above") was false.

So the population is now every `float` parameter of every public callable in the package, found by
walking it and reading annotations. There is no name rule left to be narrowed. What survives is a
judgement -- which floats are *lengths* -- and that judgement is written down as EXEMPT_KINDS,
where a reader can disagree with it, instead of being hidden in a tuple.
"""

import inspect
import math
import pkgutil
from importlib import import_module

import numpy as np
import pytest

import microrelief
from microrelief.accumulate import CellStats
from microrelief.density import BASIS_MEASURED, compute_basis, honesty_report
from microrelief.grid import Grid, GridError, grid_for_bounds
from microrelief.ground import GroundParams, classify_ground, windows_for
from microrelief.precheck import (
    TileEstimate,
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
"""Zero is in here because a zero length is as meaningless as a negative one -- except where a
site says otherwise, which `BAD_OVERRIDES` records."""

BAD_OVERRIDES = {
    ("microrelief.density", "compute_basis", "d_max_interp_m"): tuple(b for b in BAD if b != 0.0),
}
"""`d_max_interp_m = 0` is ADMISSIBLE: it means "borrow from nothing", so `distances * cell <= 0`
holds only where the distance is zero, i.e. at cells already measured, and the band comes out
measured plus undetermined with no interpolated cell. The most conservative honest setting the
flag can express. The first guard bundled it with nan/inf/negative and quietly removed it."""


# --- fixtures, small enough to count by hand -------------------------------------------------


def _z() -> np.ndarray:
    return np.full((4, 4), 100.0)


def _z32() -> np.ndarray:
    return np.full((4, 4), 100.0, dtype=np.float32)


def _basis() -> np.ndarray:
    return np.full((4, 4), BASIS_MEASURED, dtype=np.uint8)


def _ground() -> np.ndarray:
    out = np.zeros((4, 4), dtype=bool)
    out[1:3, 1:3] = True
    return out


def _stats() -> CellStats:
    return CellStats(
        n_all=np.ones((4, 4), dtype=np.int32),
        n_ground_asprs=np.zeros((4, 4), dtype=np.int32),
        min_z_all=np.full((4, 4), 100.0, dtype=np.float32),
        max_z_all=np.full((4, 4), 101.0, dtype=np.float32),
        min_z_ground_asprs=np.full((4, 4), np.nan, dtype=np.float32),
        n_outside=0,
    )


def _tile() -> TileEstimate:
    """Dense enough that an ordinary 0.5 m cell does NOT trip the void refusal.

    The previous fixture used 10 pts/m2, which refuses at 0.5 m (36.8% void against a 35%
    ceiling) -- so this table's own quiet arm would have failed on a perfectly valid length, had
    the quiet arm existed. It did not; the delegating half was added without one.
    """
    return TileEstimate(
        item_id="x", density=40.0, flight_date="", void_open_ground=0.01, void_at_f=0.01
    )


# --- the two covered tables ------------------------------------------------------------------

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
        ("microrelief.smrf", "SmrfParams", "cell"),
        lambda x: block_factor(0.5, SmrfParams(cell=x)),
        SmrfError,
    ),
    (("microrelief.smrf", "max_radius_for", "window"), lambda x: max_radius_for(x, 0.5), SmrfError),
    (("microrelief.smrf", "max_radius_for", "cell"), lambda x: max_radius_for(18.0, x), SmrfError),
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
        ("microrelief.precheck", "check_tiles", "max_void_fraction"),
        lambda x: check_tiles([_tile()], 0.5, 0.4, max_void_fraction=x),
        ValueError,
    ),
    (
        ("microrelief.density", "compute_basis", "cell"),
        lambda x: compute_basis(_ground(), _stats(), x, 1, 2.0),
        ValueError,
    ),
    (
        ("microrelief.density", "compute_basis", "d_max_interp_m"),
        lambda x: compute_basis(_ground(), _stats(), 0.5, 1, x),
        ValueError,
    ),
    (
        ("microrelief.ground", "GroundParams", "elevation_threshold_m"),
        lambda x: classify_ground(_z32(), 0.5, GroundParams(elevation_threshold_m=x)),
        ValueError,
    ),
    (
        ("microrelief.ground", "GroundParams", "max_elevation_m"),
        lambda x: classify_ground(_z32(), 0.5, GroundParams(max_elevation_m=x)),
        ValueError,
    ),
    (
        ("microrelief.ground", "windows_for", "max_window_m"),
        lambda x: windows_for(x, 0.5),
        ValueError,
    ),
    (("microrelief.ground", "windows_for", "cell"), lambda x: windows_for(4.0, x), ValueError),
    (
        ("microrelief.ground", "GroundParams", "max_window_m"),
        lambda x: classify_ground(_z32(), 0.5, GroundParams(max_window_m=x)),
        ValueError,
    ),
    (
        # A directly-constructed Grid was the one route past grid_for_bounds's guard into every
        # metric path downstream; the check now sits beside the CRS one, on the object itself.
        ("microrelief.grid", "Grid", "cell"),
        lambda x: Grid(0.0, 100.0, x, 10, 10, 3763),
        GridError,
    ),
)

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
    (
        ("microrelief.smrf", "SmrfParams", "window"),
        lambda x: max_radius_for(SmrfParams(window=x).window_m, 0.5),
    ),
    (("microrelief.precheck", "check_tiles", "cell"), lambda x: check_tiles([_tile()], x, 0.4)),
    (
        ("microrelief.precheck", "estimate_tiles", "cell"),
        lambda x: estimate_tiles([_tile()], x, 0.4),
    ),
    (
        ("microrelief.ground", "classify_ground", "cell"),
        lambda x: classify_ground(_z32(), x, GroundParams()),
    ),
)

# --- the judgement, written where it can be argued with --------------------------------------
#
# Which floats are LENGTHS. Everything above is; everything below is not, by kind. This replaces
# a five-name tuple that silently defined the population and left two lengths outside it.

EXEMPT_KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "coordinate": (
        "a position, not a length: negative and zero are ordinary values for an easting or a "
        "northing, and the extent checks that DO matter live in grid_for_bounds",
        ("minx", "miny", "maxx", "maxy", "origin_x", "origin_y", "aoi_bounds", "bbox_wgs84"),
    ),
    "fraction or ratio": (
        "dimensionless: guarded where it is load-bearing (ground_fraction in "
        "expected_void_fraction, max_void_fraction in check_tiles) and otherwise a tuning "
        "constant of an algorithm this package re-implements rather than calibrates",
        (
            "slope",
            "slope_threshold",
            "scalar",
            "threshold",
            "cut",
            "ground_fraction",
            "min_coverage",
            "covered_fraction",
            "nodata",
        ),
    ),
    "duration": (
        "hours or seconds, not metres; a separate dimension with its own admissible range",
        ("timeout", "sortie_gap_hours", "gap_hours"),
    ),
    "area": (
        "square metres or square kilometres; derived from lengths already guarded upstream",
        ("area_m2", "max_area_km2"),
    ),
    "measured result": (
        "an output field of a frozen result dataclass, written by this package from its own "
        "arithmetic and never taken from a caller; a guard here would check our own output",
        (
            "accuracy",
            "recall_ground",
            "recall_nonground",
            "majority_class_null",
            "ground_prevalence",
            "fraction_measured",
            "fraction_interpolated",
            "fraction_undetermined",
            "expected_void_fraction",
            "measured_density",
            "density",
            "density_measured",
            "void_at_f",
            "void_open_ground",
            "honesty",
        ),
    ),
}

EXEMPT_NAMES = {name: kind for kind, (_why, names) in EXEMPT_KINDS.items() for name in names}


def _float_parameters() -> set[tuple[str, str, str]]:
    """(module, callable, parameter) for every `float`-annotated parameter of a public callable.

    Annotations, not names. The name rule this replaces is exactly what let two lengths sit
    outside the population while the file claimed to cover every one.
    """
    found: set[tuple[str, str, str]] = set()
    for info in pkgutil.walk_packages(microrelief.__path__, "microrelief."):
        module = import_module(info.name)
        for obj_name, obj in vars(module).items():
            if getattr(obj, "__module__", None) != info.name or obj_name.startswith("_"):
                continue
            if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                continue
            try:
                signature = inspect.signature(obj, eval_str=True)
            except (TypeError, ValueError, NameError):  # pragma: no cover - C types
                continue
            for param in signature.parameters.values():
                annotation = param.annotation
                args = getattr(annotation, "__args__", None)
                if annotation is float or (args and float in args):
                    found.add((info.name, obj_name, param.name))
    return found


COVERED = {site for site, _c, _e in ENTRY_POINTS} | {site for site, _c in DELEGATING}

MESSAGE_MUST_CONTAIN = {
    # Not a length but the same failure mode, so it lives in the table; its refusal names the
    # admissible RANGE rather than finiteness, because finiteness alone was the first fix and
    # left 1.0 and 5.0 accepting every tile.
    ("microrelief.precheck", "check_tiles", "max_void_fraction"): "(0, 1)",
}


def _bad_for(site: tuple[str, str, str]) -> tuple[float, ...]:
    return BAD_OVERRIDES.get(site, BAD)


@pytest.mark.parametrize("site,call,error", ENTRY_POINTS, ids=lambda v: str(v))
def test_every_guarded_site_refuses_every_bad_value(site, call, error) -> None:
    for bad in _bad_for(site):
        with pytest.raises(error) as exc:
            call(bad)
        message = str(exc.value).lower()
        wanted = MESSAGE_MUST_CONTAIN.get(site, "finite")
        assert wanted in message, (
            f"{site} refused {bad} without saying what the value must be "
            f"(expected {wanted!r}): {exc.value}"
        )


@pytest.mark.parametrize("site,call", DELEGATING, ids=lambda v: str(v))
def test_every_delegating_site_refuses_every_bad_value(site, call) -> None:
    """Refusal asserted, message not: the message belongs to the delegate, and demanding it here
    would make two places that must agree out of one that already does."""
    for bad in _bad_for(site):
        with pytest.raises(ValueError):
            call(bad)


@pytest.mark.parametrize(
    "site,call",
    [(s, c) for s, c, _e in ENTRY_POINTS] + list(DELEGATING),
    ids=lambda v: str(v),
)
def test_every_covered_site_accepts_an_ordinary_length(site, call) -> None:
    """The quiet arm, over BOTH tables. It covered only the first, so the eleven sites added in
    one commit had no positive control -- and one of their fixtures did refuse a valid 0.5 m
    cell, which nothing noticed."""
    call(0.5)


def test_the_population_is_partitioned_into_covered_or_exempt_by_kind() -> None:
    """Covered, delegating, or exempt by a named kind. Absence from all three is the failure."""
    found = _float_parameters()
    assert len(found) > 40, (
        f"the walk found only {len(found)} float parameters; it scanned too little"
    )

    unclassified = sorted(s for s in found if s not in COVERED and s[2] not in EXEMPT_NAMES)
    assert not unclassified, (
        f"{len(unclassified)} float parameter(s) neither covered nor exempt: {unclassified} -- "
        "add an entry to ENTRY_POINTS/DELEGATING, or a name to EXEMPT_KINDS with its kind"
    )


def test_every_covered_site_names_a_parameter_that_still_exists() -> None:
    """The symmetric half. Without it a covered entry can name a parameter that is gone, and the
    table keeps a row for something nobody can call -- which is how an exemption for
    `max_elevation_m` stood over an unguarded parameter."""
    found = _float_parameters()
    # `block_factor`'s second operand is reached through SmrfParams, so it is keyed by the
    # dataclass; both spellings must resolve to something real.
    stale = sorted(s for s in COVERED if s not in found)
    assert not stale, f"covered but no longer present: {stale} -- drop or re-point the entry"


def test_every_exempt_name_is_a_float_parameter_somewhere_in_the_package() -> None:
    """An exemption for a name that does not exist is a rule nobody is applying."""
    found_names = {s[2] for s in _float_parameters()}
    unused = sorted(n for n in EXEMPT_NAMES if n not in found_names)
    assert not unused, f"exempt but no such float parameter: {unused} -- drop the exemption"


def test_narrowing_the_population_rule_cannot_hide_a_parameter() -> None:
    """The lock the previous version did not have.

    Its population came from a hand-written tuple of names, so deleting one entry removed a
    parameter from the population AND from the partition's reach, leaving both tests green while
    a guard became deletable. The rule here is `float`-annotated parameter of a public callable
    -- there is no list to shorten. This states the property so a future change back to a name
    rule fails here rather than silently.
    """
    found = _float_parameters()
    for site in (
        ("microrelief.density", "compute_basis", "d_max_interp_m"),
        ("microrelief.ground", "GroundParams", "elevation_threshold_m"),
        ("microrelief.ground", "GroundParams", "max_elevation_m"),
        ("microrelief.smrf", "SmrfParams", "window"),
    ):
        assert site in found, (
            f"{site} is a float parameter the package exposes and the population must contain "
            "it; each of these was outside an earlier version of this rule while a guard was owed"
        )


def test_a_bare_positivity_guard_would_fail_this_files_own_parameterisation() -> None:
    """The discriminator, on the package rather than on Python.

    This replaces a test that asserted `not (float("nan") <= 0)` and `not isfinite(nan)` -- true
    of Python, true with every guard in this package deleted, and called a discriminator in its
    own docstring. What actually discriminates is that NaN is in `BAD`, so the parameterised
    tests above fail for any site whose guard is a bare positivity test.
    """
    assert any(math.isnan(b) for b in BAD), (
        "NaN must be in BAD, or a bare positivity guard passes every case in this file"
    )
    assert all(any(math.isnan(b) for b in _bad_for(s)) for s, _c, _e in ENTRY_POINTS), (
        "an override must never drop NaN; that is the value the whole file exists for"
    )

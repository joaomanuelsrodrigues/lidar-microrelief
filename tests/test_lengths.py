"""Every entry point that takes a length in metres refuses a non-finite or non-positive one.

A contract over the siblings, not three unrelated tests. The same `x <= 0` hole appeared in three
places, was fixed in one, and the review found it in the other two -- because `float("nan") <= 0`
is False, so a NaN walks through a positivity test and dies later in `int(round(...))` or
`math.floor(...)`, or, worse, does not die at all: `precheck --cell inf` reported a confident
"0.0% of cells expected empty" for an infinite cell, and `--cell nan` printed `nan%` at exit 0.

New length-taking entry point? Add it here. A guard nothing enumerates is a guard the next
argument over does not have.
"""

import math

import pytest

from microrelief.grid import GridError, grid_for_bounds
from microrelief.precheck import expected_void_fraction
from microrelief.smrf import SmrfError, SmrfParams, block_factor

BAD = (float("nan"), float("inf"), float("-inf"), 0.0, -0.5)

# Each entry: a name, the call under test as a one-argument lambda over the bad length, and the
# exception type that entry point raises. Written as a table so adding a site is one line.
ENTRY_POINTS = (
    (
        "grid_for_bounds(cell=...)",
        lambda x: grid_for_bounds(0.0, 0.0, 100.0, 100.0, x, 3763),
        GridError,
    ),
    ("block_factor(cell=...)", lambda x: block_factor(x, SmrfParams()), SmrfError),
    ("block_factor(params.cell=...)", lambda x: block_factor(0.5, SmrfParams(cell=x)), SmrfError),
    (
        "expected_void_fraction(cell=...)",
        lambda x: expected_void_fraction(10.0, x, 0.4),
        ValueError,
    ),
    (
        "expected_void_fraction(density=...)",
        lambda x: expected_void_fraction(x, 0.5, 0.4),
        ValueError,
    ),
)


@pytest.mark.parametrize("bad", BAD, ids=lambda v: f"{v}")
@pytest.mark.parametrize(
    "name,call,error", ENTRY_POINTS, ids=lambda v: getattr(v, "__name__", str(v))
)
def test_every_length_entry_point_refuses_a_bad_length(name, call, error, bad) -> None:
    with pytest.raises(error) as exc:
        call(bad)
    message = str(exc.value).lower()
    assert "positive" in message and "finite" in message, (
        f"{name} refused {bad} but the message does not say what a length must be: {exc.value}"
    )


@pytest.mark.parametrize(
    "name,call,error", ENTRY_POINTS, ids=lambda v: getattr(v, "__name__", str(v))
)
def test_every_length_entry_point_accepts_an_ordinary_length(name, call, error) -> None:
    """The quiet arm. A guard that refuses 0.5 m would refuse every real run."""
    call(0.5)


def test_the_table_would_notice_a_guard_that_only_tests_positivity() -> None:
    """The discriminator, on the mechanism rather than on the sites.

    `nan <= 0` is False, so a bare positivity test admits NaN. This states that the property
    being asserted above is not satisfiable by the check the sites used to have.
    """
    assert not (float("nan") <= 0), "the whole point: a bare positivity test lets NaN through"
    assert not math.isfinite(float("nan"))

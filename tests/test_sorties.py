import pytest

from microrelief.sorties import StampError, group_sorties

# The four stamps below are the real ones the DGT catalogue publishes for the Manteigas
# candidate, measured 2026-08-03: one pass of one aircraft, spread over 6m23s.
#
# It lives here rather than in `test_selection.py`, where it used to, so the test-side
# dependency runs the same way as the code's: the provider tests import the core's fixture,
# never the reverse.
MANTEIGAS = (
    "2025-07-04T21:11:07Z",
    "2025-07-04T21:13:42Z",
    "2025-07-04T21:14:21Z",
    "2025-07-04T21:17:30Z",
)


def test_stamps_minutes_apart_are_one_sortie() -> None:
    assert group_sorties(MANTEIGAS) == (MANTEIGAS,)


def test_a_flight_across_midnight_is_one_sortie_and_not_two_days() -> None:
    # The case that decides the mechanism: grouping by UTC day splits this pair, and a
    # night flight crossing midnight is one acquisition by every physical meaning.
    stamps = ("2025-07-04T23:52:00Z", "2025-07-05T00:19:00Z")
    assert group_sorties(stamps) == (stamps,)


def test_stamps_a_day_apart_are_separate_sorties() -> None:
    # Sistelo publishes date-only stamps: at that precision two calendar dates cannot be
    # shown to be one flight, so they are not merged.
    stamps = ("2026-03-22T00:00:00Z", "2026-03-23T00:00:00Z")
    assert group_sorties(stamps) == (("2026-03-22T00:00:00Z",), ("2026-03-23T00:00:00Z",))


def test_sorties_are_ordered_in_time_not_lexically() -> None:
    # 23:00+02:00 is 21:00 UTC and therefore *earlier* than 21:30Z — the reverse of the
    # order the strings sort in. Ordering by the string would misread which gap is which.
    stamps = ("2025-07-04T23:00:00+02:00", "2025-07-04T21:30:00Z")
    assert group_sorties(stamps) == (("2025-07-04T23:00:00+02:00", "2025-07-04T21:30:00Z"),)


def test_a_stamp_without_a_utc_offset_is_refused_rather_than_assumed() -> None:
    # The expectation moved with the function: clustering timestamps is core work and raises
    # core's error. What a *catalogue* caller sees is asserted in `test_selection.py`, which is
    # the only thing holding the provider's re-raise in place.
    with pytest.raises(StampError, match="no UTC offset"):
        group_sorties(("2025-07-04T21:11:07",))

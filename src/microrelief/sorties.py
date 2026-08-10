"""Clustering acquisition stamps into flights.

Pure time arithmetic on ISO-8601 strings: no catalogue, no network. It lives in core because
the record needs it — `provenance.mixed_epochs` and the selection's `sorties` have to be
answered the same way, and one definition cannot drift from itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

SORTIE_GAP_HOURS = 6.0
"""Longest gap between two acquisition stamps that still counts as one flight."""


class StampError(ValueError):
    """An acquisition stamp is not shaped the way we can reason about time with."""


def _parse_stamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StampError(f"flight date {value!r} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise StampError(f"flight date {value!r} carries no UTC offset; refusing to guess")
    return parsed


def group_sorties(
    flight_dates: Iterable[str], gap_hours: float = SORTIE_GAP_HOURS
) -> tuple[tuple[str, ...], ...]:
    """Cluster acquisition stamps into sorties by the gap between consecutive ones.

    Single-linkage on the time axis: two stamps belong to the same sortie when nothing
    separates them by more than `gap_hours`. Grouping by UTC day instead would split a
    night flight that crosses midnight, which is the one case this has to get right —
    and the catalogue does publish sub-minute stamps for night acquisitions.

    Stamps are ordered by the instant they denote, not lexically: two offsets for the
    same moment sort in the wrong order as strings and would invent a gap.
    """
    if gap_hours <= 0:
        raise ValueError(f"gap_hours must be positive, got {gap_hours}")
    parsed = sorted(((_parse_stamp(s), s) for s in set(flight_dates)), key=lambda p: p[0])
    if not parsed:
        return ()
    gap = timedelta(hours=gap_hours)
    groups: list[list[str]] = [[parsed[0][1]]]
    for (previous, _), (moment, raw) in zip(parsed, parsed[1:], strict=False):
        if moment - previous > gap:
            groups.append([raw])
        else:
            groups[-1].append(raw)
    return tuple(tuple(g) for g in groups)

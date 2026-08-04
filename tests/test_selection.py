import pytest

from microrelief.tiles import (
    SelectionError,
    TileRef,
    UnexpectedCatalogue,
    group_sorties,
    select_tiles,
)


def tile(
    minx: float,
    miny: float,
    date: str = "2024-11-22T00:00:00Z",
    count: int = 19_000_000,
    span: float = 1000.0,
) -> TileRef:
    return TileRef(
        item_id=f"LO-{int(minx)}-{int(miny)}-{date[:4]}",
        collection="LAZ",
        minx=minx,
        miny=miny,
        maxx=minx + span,
        maxy=miny + span,
        crs_epsg=3763,
        point_count=count,
        flight_date=date,
        file_size=130_000_000,
        href=f"https://example.invalid/{minx}-{miny}",
    )


AOI = (48200.0, 169200.0, 50200.0, 171200.0)  # 2 x 2 km, crossing tile boundaries


def full_cover() -> list[TileRef]:
    return [tile(x, y) for x in (48000.0, 49000.0, 50000.0) for y in (169000.0, 170000.0, 171000.0)]


def test_full_coverage_selects_every_intersecting_tile() -> None:
    sel = select_tiles(full_cover(), AOI)
    assert len(sel.tiles) == 9
    assert sel.covered_fraction == pytest.approx(1.0)
    assert sel.mixed_epochs is False


def test_millimetre_seams_between_declared_footprints_are_not_a_hole() -> None:
    # Measured against the live catalogue 2026-08-04: DGT publishes `proj:bbox` as the
    # bounding box of the returns, not of the tile, so the far corner lands ~1 mm inside
    # the lattice (-21000.0 .. -20000.001, next tile starts at -20000.0). Every internal
    # seam therefore leaves a 1 mm strip, and min_coverage=1.0 is unsatisfiable for any
    # multi-tile AOI — 3.97 m2 short over this AOI's two seams.
    seamed = [
        tile(x, y, span=999.999)
        for x in (48000.0, 49000.0, 50000.0)
        for y in (169000.0, 170000.0, 171000.0)
    ]
    sel = select_tiles(seamed, AOI)
    assert sel.covered_fraction < 1.0
    assert sel.covered_fraction > 0.9999


def test_the_smallest_real_hole_is_still_refused() -> None:
    # The corner tile is the least of the AOI any single tile carries: 200 m x 200 m of
    # 2 km x 2 km, or 1%. It is four orders of magnitude above the seams above, which is
    # the room min_coverage has to work in.
    holed = [t for t in full_cover() if (t.minx, t.miny) != (50000.0, 171000.0)]
    with pytest.raises(SelectionError, match="covers 0.99"):
        select_tiles(holed, AOI)


def test_overlapping_footprints_do_not_push_coverage_above_one() -> None:
    # Alto Douro's tiles overlap by 0.1 m in y (…169000.1 against …169000.0). Summing
    # per-tile overlaps double-counts that strip; the union does not.
    overlapping = [
        tile(x, y, span=1000.2)
        for x in (48000.0, 49000.0, 50000.0)
        for y in (169000.0, 170000.0, 171000.0)
    ]
    sel = select_tiles(overlapping, AOI)
    assert sel.covered_fraction == pytest.approx(1.0)


def test_partial_coverage_refuses_with_the_fraction_in_the_message() -> None:
    # The centre tile is the only one wholly inside the AOI, so it is exactly
    # a quarter of it. Dropping it leaves an interior hole — the case where
    # intersection still looks like coverage.
    without_centre = [t for t in full_cover() if (t.minx, t.miny) != (49000.0, 170000.0)]
    with pytest.raises(SelectionError, match="covers 0.75"):
        select_tiles(without_centre, AOI)


def test_a_footprint_flown_twice_collapses_to_the_dominant_flight() -> None:
    tiles = full_cover() + [tile(49000.0, 170000.0, date="2025-05-30T00:00:00Z")]
    sel = select_tiles(tiles, AOI)
    assert len(sel.tiles) == 9  # not 10 — the union would have double-counted
    assert sel.flight_dates == ("2024-11-22T00:00:00Z",)
    assert "LO-49000-170000-2025" in sel.dropped_duplicates


def test_mixed_epochs_are_refused_by_default_and_declared_when_allowed() -> None:
    tiles = [t for t in full_cover() if not (t.minx == 50000.0 and t.miny == 171000.0)]
    tiles.append(tile(50000.0, 171000.0, date="2025-05-30T00:00:00Z"))
    with pytest.raises(SelectionError, match="spans 2 sorties"):
        select_tiles(tiles, AOI)
    sel = select_tiles(tiles, AOI, allow_mixed_epochs=True)
    assert sel.mixed_epochs is True
    assert len(sel.flight_dates) == 2
    assert len(sel.sorties) == 2


# The four stamps below are the real ones the DGT catalogue publishes for the Manteigas
# candidate, measured 2026-08-03: one pass of one aircraft, spread over 6m23s.
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
    with pytest.raises(UnexpectedCatalogue, match="no UTC offset"):
        group_sorties(("2025-07-04T21:11:07",))


def test_one_sortie_spread_over_several_stamps_is_not_a_mixed_epoch() -> None:
    tiles = [
        tile(x, y, date=MANTEIGAS[i % len(MANTEIGAS)])
        for i, (x, y) in enumerate(
            (x, y) for x in (48000.0, 49000.0, 50000.0) for y in (169000.0, 170000.0, 171000.0)
        )
    ]
    sel = select_tiles(tiles, AOI)
    assert sel.mixed_epochs is False
    assert len(sel.sorties) == 1
    assert len(sel.tiles) == 9
    assert len(sel.flight_dates) == 4  # the raw stamps are kept; the sortie is the grouping


def test_dominance_is_measured_over_the_sortie_not_over_one_stamp() -> None:
    # The duplicated footprint is the AOI's centre tile — a quarter of the AOI, and the
    # largest single overlap. Its two candidates sit on stamps that are each a minority
    # *by stamp*, so per-stamp dominance picks neither and falls through to item_id
    # order, which keeps the 2024 intruder. Per-sortie, the Manteigas pass covers three
    # quarters of the AOI and wins outright.
    stamp_of = {
        (49000.0, 170000.0): MANTEIGAS[0],
        (49000.0, 169000.0): MANTEIGAS[1],
        (48000.0, 170000.0): MANTEIGAS[1],
        (48000.0, 169000.0): MANTEIGAS[2],
        (50000.0, 169000.0): MANTEIGAS[2],
        (50000.0, 170000.0): MANTEIGAS[3],
        (48000.0, 171000.0): MANTEIGAS[3],
        (49000.0, 171000.0): MANTEIGAS[3],
        (50000.0, 171000.0): MANTEIGAS[3],
    }
    tiles = [tile(x, y, date=d) for (x, y), d in stamp_of.items()]
    tiles.append(tile(49000.0, 170000.0, date="2024-11-22T00:00:00Z"))
    sel = select_tiles(tiles, AOI)
    assert sel.dropped_duplicates == ("LO-49000-170000-2024",)
    assert len(sel.sorties) == 1
    assert sel.mixed_epochs is False


def test_area_cap_refuses_before_anyone_tries_to_download_it() -> None:
    big = [tile(float(x) * 1000.0, float(y) * 1000.0) for x in range(20) for y in range(20)]
    with pytest.raises(SelectionError, match="400.0 km2"):
        select_tiles(big, (0.0, 0.0, 20000.0, 20000.0), max_area_km2=200.0)


def test_mixed_crs_refuses_rather_than_reprojecting_silently() -> None:
    tiles = full_cover()
    object.__setattr__(tiles[0], "crs_epsg", 4258)
    with pytest.raises(SelectionError, match="more than one CRS"):
        select_tiles(tiles, AOI)

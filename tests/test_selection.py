import pytest

from microrelief.tiles import SelectionError, TileRef, select_tiles


def tile(
    minx: float, miny: float, date: str = "2024-11-22T00:00:00Z", count: int = 19_000_000
) -> TileRef:
    return TileRef(
        item_id=f"LO-{int(minx)}-{int(miny)}-{date[:4]}",
        collection="LAZ",
        minx=minx,
        miny=miny,
        maxx=minx + 1000.0,
        maxy=miny + 1000.0,
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
    with pytest.raises(SelectionError, match="two flight dates"):
        select_tiles(tiles, AOI)
    sel = select_tiles(tiles, AOI, allow_mixed_epochs=True)
    assert sel.mixed_epochs is True
    assert len(sel.flight_dates) == 2


def test_area_cap_refuses_before_anyone_tries_to_download_it() -> None:
    big = [tile(float(x) * 1000.0, float(y) * 1000.0) for x in range(20) for y in range(20)]
    with pytest.raises(SelectionError, match="400.0 km2"):
        select_tiles(big, (0.0, 0.0, 20000.0, 20000.0), max_area_km2=200.0)


def test_mixed_crs_refuses_rather_than_reprojecting_silently() -> None:
    tiles = full_cover()
    object.__setattr__(tiles[0], "crs_epsg", 4258)
    with pytest.raises(SelectionError, match="more than one CRS"):
        select_tiles(tiles, AOI)

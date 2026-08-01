import pytest

from microrelief.tiles import (
    CatalogueTruncated,
    UnexpectedCatalogue,
    _tile_ref,
    parse_search_response,
)

FEATURE = {
    "id": "LO-248470-07-2024",
    "collection": "LAZ",
    "bbox": [-7.55, 41.18, 45.15, -7.54, 41.19, 348.3],
    "properties": {
        "pc:count": 21184681,
        "datetime": "2024-11-22T00:00:00Z",
        "file:size": 145800000,
        "proj:bbox": [48000, 169000, 45.15, 48999.999, 169999.999, 348.318],
        "proj:wkt2": 'PROJCS["ETRS89 / Portugal TM06",GEOGCS["ETRS89",AUTHORITY["EPSG","4258"]],'
        'AUTHORITY["EPSG","3763"]]',
    },
    "assets": {
        "data": {
            "href": "https://cdd.dgterritorio.gov.pt/dgt-be/v1/download/abc",
            "type": "application/vnd.laszip",
        }
    },
}


def test_three_dimensional_bbox_is_read_as_x_y_not_as_x_max_x() -> None:
    # proj:bbox is [minx, miny, minz, maxx, maxy, maxz]. Reading index 2 as maxx yields 45.15,
    # a tile 47954 m wide, and every downstream number stays plausible. This is the whole test.
    tile = _tile_ref(FEATURE)
    assert (tile.minx, tile.miny, tile.maxx, tile.maxy) == (
        48000,
        169000,
        48999.999,
        169999.999,
    )
    assert 999.0 < (tile.maxx - tile.minx) < 1001.0


def test_density_comes_from_the_catalogue_before_any_download() -> None:
    tile = _tile_ref(FEATURE)
    assert 21.0 < tile.density < 21.3


def test_crs_is_taken_from_wkt_authority_never_assumed() -> None:
    assert _tile_ref(FEATURE).crs_epsg == 3763
    broken = {
        **FEATURE,
        "properties": {**FEATURE["properties"], "proj:wkt2": 'PROJCS["nope"]'},
    }
    with pytest.raises(UnexpectedCatalogue, match="EPSG authority"):
        _tile_ref(broken)


def test_a_full_page_is_a_refusal_because_the_api_offers_no_paging() -> None:
    # Measured 2026-08-01: the response carries no `next` link and no numberMatched.
    # A result set that exactly fills the limit is indistinguishable from a truncated one.
    body = {
        "type": "FeatureCollection",
        "context": {"limit": 2, "returned": 2},
        "features": [FEATURE, FEATURE],
        "links": [{"rel": "self"}, {"rel": "root"}],
    }
    with pytest.raises(CatalogueTruncated, match="returned 2 of a limit of 2"):
        parse_search_response(body, limit=2)


def test_a_partial_page_is_trusted() -> None:
    body = {
        "type": "FeatureCollection",
        "context": {"limit": 50, "returned": 1},
        "features": [FEATURE],
        "links": [],
    }
    assert len(parse_search_response(body, limit=50)) == 1


def test_missing_download_asset_refuses() -> None:
    no_asset = {**FEATURE, "assets": {}}
    with pytest.raises(UnexpectedCatalogue, match="no data asset"):
        _tile_ref(no_asset)

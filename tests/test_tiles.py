from pathlib import Path

import pytest

from microrelief.providers.dgt import (
    CatalogueTruncated,
    UnexpectedCatalogue,
    parse_search_response,
)

# Reached through the module, not the package door: `_tile_ref` is underscore-private
# catalogue internals, and re-exporting it would make it public by accident in the very
# change that draws the layer boundary.
from microrelief.providers.dgt.catalogue import _crs_epsg_from_wkt2, _tile_ref

# Both WKTs are verbatim captures from the live catalogue, kept as files rather than as
# wrapped string literals: a re-typed or re-wrapped capture is not the capture, and these two
# differ only in ways a reader would not notice by eye. `with_authority` is Sistelo's
# LO-179556-07-2025, the tile the piece was built on; `without_authority` is Valongo's
# LO-161471-07-2025, one of 428 that publish no AUTHORITY on the PROJCS node.
FIXTURES = Path(__file__).parent / "fixtures"
WKT_WITH_AUTHORITY = (FIXTURES / "wkt_projcs_with_authority.txt").read_text()
WKT_WITHOUT_AUTHORITY = (FIXTURES / "wkt_projcs_without_authority.txt").read_text()

FEATURE = {
    "id": "LO-248470-07-2024",
    "collection": "LAZ",
    "bbox": [-7.55, 41.18, 45.15, -7.54, 41.19, 348.3],
    "properties": {
        "pc:count": 21184681,
        "datetime": "2024-11-22T00:00:00Z",
        "file:size": 145800000,
        "proj:bbox": [48000, 169000, 45.15, 48999.999, 169999.999, 348.318],
        "proj:wkt2": WKT_WITH_AUTHORITY,
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


def test_crs_is_taken_from_the_wkt_never_assumed() -> None:
    assert _tile_ref(FEATURE).crs_epsg == 3763


def test_a_projcs_that_declares_no_authority_is_still_read_as_its_own_crs() -> None:
    """Measured 2026-08-31 over the whole mainland catalogue: 428 of 91,292 tiles publish
    `PROJCS["ETRS89_Portugal_TM06", ...]` with no AUTHORITY on the PROJCS node. Taking the last
    EPSG authority in the string then returns 9001 -- the metre *unit* -- which pyproj resolves
    to IGS97, a geographic CRS. Those tiles are EPSG:3763: re-fetched and checked one by one,
    428 of 428 give `CRS.from_wkt(...).to_epsg() == 3763` and `.equals(CRS.from_epsg(3763))`.

    Reading them as 9001 refuses a whole delivery with a reason that is false and advice that
    cannot be followed: `Supply an AOI in EPSG:9001` is itself refused, as geographic. The
    nearest such tile sits 11.3 km from the AOI this repository publishes.
    """
    assert _crs_epsg_from_wkt2(WKT_WITHOUT_AUTHORITY) == 3763
    assert _crs_epsg_from_wkt2(WKT_WITH_AUTHORITY) == 3763


def test_a_wkt_that_is_not_a_crs_at_all_is_refused() -> None:
    broken = {
        **FEATURE,
        "properties": {**FEATURE["properties"], "proj:wkt2": 'PROJCS["nope"]'},
    }
    with pytest.raises(UnexpectedCatalogue, match="not readable as a CRS"):
        _tile_ref(broken)


def test_a_readable_crs_that_matches_no_epsg_code_is_refused_not_guessed() -> None:
    """The other half of the refusal, and the reason the fix is not "trust pyproj": a WKT can
    parse perfectly and still name a projection the EPSG registry does not have. This one is
    the real capture with its central meridian moved, so it is projected, in metres, and
    matches nothing -- `to_epsg()` returns None and we must say so rather than pick a number.
    """
    odd = WKT_WITHOUT_AUTHORITY.replace("-8.13310833333345", "-8.5")
    assert odd != WKT_WITHOUT_AUTHORITY  # the substitution happened; a no-op would test nothing
    with pytest.raises(UnexpectedCatalogue, match="matches no EPSG code"):
        _crs_epsg_from_wkt2(odd)


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

"""The one provider this package has actually been exercised against.

Everything DGT-specific lives here: the search endpoint, the `LAZ` collection name, the
200 km2 download cap, and the attribution string for their open data. The core knows none
of it. That this is the *only* provider exercised is a fact about the evidence, not a
statement about the core's reach — see README, "What has been exercised".
"""

from microrelief.providers.dgt.catalogue import (
    MIN_COVERAGE,
    STAC_SEARCH_URL,
    CatalogueError,
    CatalogueTruncated,
    Selection,
    SelectionError,
    TileRef,
    UnexpectedCatalogue,
    parse_search_response,
    search_tiles,
    select_tiles,
)

DGT_ATTRIBUTION = (
    "Source: Direção-Geral do Território (DGT), Centro de Dados, LiDAR point clouds, "
    "licensed CC BY 4.0. Derived products (ground classification, DTM, DSM, CHM) produced "
    "by microrelief; not reviewed or endorsed by DGT."
)

__all__ = [
    "DGT_ATTRIBUTION",
    "MIN_COVERAGE",
    "STAC_SEARCH_URL",
    "CatalogueError",
    "CatalogueTruncated",
    "Selection",
    "SelectionError",
    "TileRef",
    "UnexpectedCatalogue",
    "parse_search_response",
    "search_tiles",
    "select_tiles",
]

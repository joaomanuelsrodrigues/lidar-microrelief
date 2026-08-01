"""Tile discovery against the DGT Centro de Dados STAC API.

Measured 2026-08-01, unauthenticated: search and item metadata are open; only the
download href is closed. The API returns neither a `next` link nor `numberMatched`,
so a full page is treated as truncation rather than as a complete answer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import requests

STAC_SEARCH_URL = "https://cdd.dgterritorio.gov.pt/dgt-be/v1/search"
_EPSG_IN_WKT = re.compile(r'AUTHORITY\["EPSG","(\d+)"\]')


class CatalogueError(RuntimeError):
    """The catalogue did not answer in a way we are willing to act on."""


class CatalogueTruncated(CatalogueError):
    """The result set may be incomplete and the API gives us no way to tell."""


class UnexpectedCatalogue(CatalogueError):
    """A field we depend on is missing or shaped differently than measured."""


@dataclass(frozen=True)
class TileRef:
    item_id: str
    collection: str
    minx: float
    miny: float
    maxx: float
    maxy: float
    crs_epsg: int
    point_count: int
    flight_date: str
    file_size: int
    href: str

    @property
    def area_m2(self) -> float:
        return (self.maxx - self.minx) * (self.maxy - self.miny)

    @property
    def density(self) -> float:
        """Points per m², from the catalogue — no download required."""
        return self.point_count / self.area_m2

    @property
    def footprint_key(self) -> tuple[float, float]:
        """Identifies the ground footprint, so the same tile flown twice collapses to one entry."""
        return (round(self.minx, 3), round(self.miny, 3))


def _bbox_2d(values: Sequence[float]) -> tuple[float, float, float, float]:
    """Accept both 2D (4-element) and 3D (6-element) STAC bboxes.

    The DGT catalogue publishes 3D. Indexing blindly turns minz into maxx.
    """
    if len(values) == 6:
        return float(values[0]), float(values[1]), float(values[3]), float(values[4])
    if len(values) == 4:
        return float(values[0]), float(values[1]), float(values[2]), float(values[3])
    raise UnexpectedCatalogue(f"bbox has {len(values)} elements, expected 4 or 6")


def _crs_epsg_from_wkt2(wkt: str) -> int:
    codes = _EPSG_IN_WKT.findall(wkt)
    if not codes:
        raise UnexpectedCatalogue("proj:wkt2 carries no EPSG authority; refusing to assume a CRS")
    return int(codes[-1])  # outermost authority = the projected CRS


def _tile_ref(feature: dict[str, Any]) -> TileRef:
    props = feature.get("properties", {})
    for key in ("proj:bbox", "proj:wkt2", "pc:count", "datetime", "file:size"):
        if key not in props:
            raise UnexpectedCatalogue(f"item {feature.get('id')!r} has no {key}")
    asset = feature.get("assets", {}).get("data")
    if not asset or "href" not in asset:
        raise UnexpectedCatalogue(f"item {feature.get('id')!r} has no data asset")

    minx, miny, maxx, maxy = _bbox_2d(props["proj:bbox"])
    return TileRef(
        item_id=str(feature["id"]),
        collection=str(feature.get("collection", "")),
        minx=minx,
        miny=miny,
        maxx=maxx,
        maxy=maxy,
        crs_epsg=_crs_epsg_from_wkt2(props["proj:wkt2"]),
        point_count=int(props["pc:count"]),
        flight_date=str(props["datetime"]),
        file_size=int(props["file:size"]),
        href=str(asset["href"]),
    )


def parse_search_response(body: dict[str, Any], limit: int) -> list[TileRef]:
    features = body.get("features")
    if features is None:
        raise UnexpectedCatalogue("response has no features array")
    returned = int(body.get("context", {}).get("returned", len(features)))
    if returned >= limit:
        raise CatalogueTruncated(
            f"catalogue returned {returned} of a limit of {limit}; the API exposes no paging "
            f"(no next link, no numberMatched), so the result set may be incomplete — raise limit"
        )
    return [_tile_ref(f) for f in features]


def search_tiles(
    bbox_wgs84: tuple[float, float, float, float],
    collection: str = "LAZ",
    limit: int = 500,
    url: str = STAC_SEARCH_URL,
    timeout: float = 30.0,
) -> list[TileRef]:
    """Search the catalogue. `bbox_wgs84` is (minlon, minlat, maxlon, maxlat)."""
    response = requests.post(
        url,
        json={"bbox": list(bbox_wgs84), "collections": [collection], "limit": limit},
        timeout=timeout,  # every network call carries an explicit failure bound
    )
    if response.status_code != 200:
        raise CatalogueError(
            f"catalogue returned HTTP {response.status_code} for bbox {bbox_wgs84}"
        )
    return parse_search_response(response.json(), limit=limit)

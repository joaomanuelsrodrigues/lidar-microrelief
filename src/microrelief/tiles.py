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


class SelectionError(CatalogueError):
    """The tiles on offer do not make an AOI we are willing to process."""


@dataclass(frozen=True)
class Selection:
    tiles: tuple[TileRef, ...]
    aoi_bounds: tuple[float, float, float, float]
    covered_fraction: float
    flight_dates: tuple[str, ...]
    mixed_epochs: bool
    dropped_duplicates: tuple[str, ...]

    @property
    def total_area_km2(self) -> float:
        return sum(t.area_m2 for t in self.tiles) / 1e6


def _overlap_area(t: TileRef, bounds: tuple[float, float, float, float]) -> float:
    minx, miny, maxx, maxy = bounds
    w = min(t.maxx, maxx) - max(t.minx, minx)
    h = min(t.maxy, maxy) - max(t.miny, miny)
    return w * h if w > 0 and h > 0 else 0.0


def select_tiles(
    tiles: Sequence[TileRef],
    aoi_bounds: tuple[float, float, float, float],
    allow_mixed_epochs: bool = False,
    min_coverage: float = 1.0,
    max_area_km2: float = 200.0,
) -> Selection:
    """Choose the tiles that actually cover the AOI, preferring a single flight.

    Coverage is measured, not assumed from intersection. Where one footprint was flown more
    than once, exactly one acquisition is kept: consistency on the spatial axis is not
    consistency on the temporal one, and a mosaic of two epochs registered onto one grid is
    harder to notice, not easier.
    """
    minx, miny, maxx, maxy = aoi_bounds
    aoi_area = (maxx - minx) * (maxy - miny)
    if aoi_area <= 0:
        raise SelectionError(f"empty AOI bounds {aoi_bounds}")

    touching = [t for t in tiles if _overlap_area(t, aoi_bounds) > 0]
    if not touching:
        raise SelectionError(f"no tile intersects AOI {aoi_bounds}")

    crs = {t.crs_epsg for t in touching}
    if len(crs) > 1:
        raise SelectionError(f"tiles declare more than one CRS: {sorted(crs)}")

    # Coverage per flight date, so "dominant" means "covers most of this AOI", not "most tiles".
    by_date: dict[str, float] = {}
    for t in touching:
        by_date[t.flight_date] = by_date.get(t.flight_date, 0.0) + _overlap_area(t, aoi_bounds)
    dominant = max(sorted(by_date), key=lambda d: by_date[d])

    kept: dict[tuple[float, float], TileRef] = {}
    dropped: list[str] = []
    for t in sorted(
        touching, key=lambda t: (t.footprint_key, t.flight_date != dominant, t.item_id)
    ):
        if t.footprint_key in kept:
            dropped.append(t.item_id)
        else:
            kept[t.footprint_key] = t

    chosen = tuple(sorted(kept.values(), key=lambda t: (t.minx, t.miny)))
    dates = tuple(sorted({t.flight_date for t in chosen}))
    if len(dates) > 1 and not allow_mixed_epochs:
        raise SelectionError(
            f"AOI needs two flight dates ({', '.join(dates)}); a mosaic of two epochs is a "
            f"product made of two moments — pass allow_mixed_epochs to accept and declare it"
        )

    covered = sum(_overlap_area(t, aoi_bounds) for t in chosen) / aoi_area
    if covered < min_coverage:
        raise SelectionError(
            f"selection covers {covered:.2f} of the AOI, need {min_coverage:.2f}; "
            f"the DGT survey is ~90% of the territory, not national"
        )

    area_km2 = sum(t.area_m2 for t in chosen) / 1e6
    if area_km2 > max_area_km2:
        raise SelectionError(f"selection is {area_km2:.1f} km2, provider cap is {max_area_km2} km2")

    return Selection(
        tiles=chosen,
        aoi_bounds=aoi_bounds,
        covered_fraction=covered,
        flight_dates=dates,
        mixed_epochs=len(dates) > 1,
        dropped_duplicates=tuple(dropped),
    )

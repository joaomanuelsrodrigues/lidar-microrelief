"""Tile discovery against the DGT Centro de Dados STAC API.

Measured 2026-08-01, unauthenticated: search and item metadata are open; only the
download href is closed. The API returns neither a `next` link nor `numberMatched`,
so a full page is treated as truncation rather than as a complete answer.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import requests
from pyproj import CRS
from pyproj.exceptions import CRSError as PyprojCRSError

from microrelief.precheck import TileLike
from microrelief.sorties import SORTIE_GAP_HOURS, StampError, group_sorties

STAC_SEARCH_URL = "https://cdd.dgterritorio.gov.pt/dgt-be/v1/search"

MIN_COVERAGE = 0.999
"""Fraction of the AOI that must lie under the tiles. Not 1.0: see CALIBRATIONS.md."""


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


def _tile_ref_satisfies_tile_like(tile: TileRef) -> TileLike:
    """The structural conformance, asserted where a type checker can actually see it.

    `precheck` takes a `TileLike` Protocol so the offline core never names a catalogue's data
    class. Nothing else under mypy's scope (`files = ["src"]`) binds a concrete `TileRef` to
    that parameter — the CLI reaches it through `_selection_for() -> Any` — so mypy returned
    "Success" over a `TileRef` with `density` renamed away: silence about an unchecked
    relationship reads exactly like silence about a sound one. This function is the binding,
    and it is verified by mutation rather than assumed (2026-08-10).
    """
    return tile


def _bbox_2d(values: Sequence[float]) -> tuple[float, float, float, float]:
    """Accept both 2D (4-element) and 3D (6-element) STAC bboxes.

    The DGT catalogue publishes 3D. Indexing blindly turns minz into maxx.
    """
    if len(values) == 6:
        return float(values[0]), float(values[1]), float(values[3]), float(values[4])
    if len(values) == 4:
        return float(values[0]), float(values[1]), float(values[2]), float(values[3])
    raise UnexpectedCatalogue(f"bbox has {len(values)} elements, expected 4 or 6")


@lru_cache(maxsize=32)
def _crs_epsg_from_wkt2(wkt: str) -> int:
    """The EPSG code of the CRS the tile is in, read by a CRS reader rather than off the string.

    This used to take the last `AUTHORITY["EPSG", ...]` in the WKT, on the reasoning that the
    outermost authority is the projected CRS. That holds only while the PROJCS node carries an
    authority. Measured 2026-08-31 over the whole mainland catalogue, 428 of 91,292 tiles do
    not: their WKT is `PROJCS["ETRS89_Portugal_TM06", ...]` ending at the axes, so the last
    authority in the string is the metre *unit*, 9001 -- which pyproj resolves to IGS97, a
    geographic CRS. Every one of those 428 was re-fetched and checked: all are EPSG:3763.

    Reading a unit as a CRS is not a near miss. It refused a whole delivery with a reason that
    was false, and with advice a reader cannot act on ("Supply an AOI in EPSG:9001" is itself
    refused, as geographic); where one correctly-tagged neighbour happened to sit in the same
    search box it did something worse, and switched the CRS guard off (see `cli._selection_for`).

    `to_epsg()` returning None is kept as a refusal rather than smoothed over: a WKT can parse
    cleanly and still name a projection the registry does not have, and picking a code for it
    would be the guess this function exists to avoid. Cached because the answer is a pure
    function of the string, ~60 ms to compute, and a search returns hundreds of tiles sharing
    one or two WKTs.
    """
    try:
        crs = CRS.from_wkt(wkt)
    except PyprojCRSError as exc:
        raise UnexpectedCatalogue(f"proj:wkt2 is not readable as a CRS: {exc}") from exc
    code = crs.to_epsg()
    if code is None:
        raise UnexpectedCatalogue(
            "proj:wkt2 parses but matches no EPSG code; refusing to assume one"
        )
    return code


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


def _sorties(stamps: Iterable[str], gap_hours: float) -> tuple[tuple[str, ...], ...]:
    """`group_sorties`, with core's error re-badged as a catalogue error.

    The core says the stamp is not a timestamp; the catalogue layer says *whose* stamp it was.
    A caller's `except CatalogueError` must keep meaning what it meant before the move.
    """
    try:
        return group_sorties(stamps, gap_hours)
    except StampError as exc:
        raise UnexpectedCatalogue(str(exc)) from exc


@dataclass(frozen=True)
class Selection:
    tiles: tuple[TileRef, ...]
    aoi_bounds: tuple[float, float, float, float]
    covered_fraction: float
    flight_dates: tuple[str, ...]
    sorties: tuple[tuple[str, ...], ...]
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


def _covered_fraction(tiles: Sequence[TileRef], bounds: tuple[float, float, float, float]) -> float:
    """Fraction of the AOI under the *union* of the tiles, computed exactly.

    Summing each tile's overlap is not coverage: it double-counts where footprints
    overlap, and the DGT publishes footprints that do overlap (a 0.1 m strip in y at
    Pinhão). Coordinate compression turns the tiles into a grid of elementary
    rectangles, each either covered or not, so the answer is exact for axis-aligned
    boxes and cannot exceed 1.
    """
    minx, miny, maxx, maxy = bounds

    def edges(lo: float, hi: float, values: Iterable[float]) -> list[float]:
        return sorted({lo, hi} | {min(max(v, lo), hi) for v in values})

    xs = edges(minx, maxx, (v for t in tiles for v in (t.minx, t.maxx)))
    ys = edges(miny, maxy, (v for t in tiles for v in (t.miny, t.maxy)))
    covered: set[tuple[int, int]] = set()
    for t in tiles:
        i0 = bisect_left(xs, min(max(t.minx, minx), maxx))
        i1 = bisect_left(xs, min(max(t.maxx, minx), maxx))
        j0 = bisect_left(ys, min(max(t.miny, miny), maxy))
        j1 = bisect_left(ys, min(max(t.maxy, miny), maxy))
        covered.update((i, j) for i in range(i0, i1) for j in range(j0, j1))
    area = sum((xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) for i, j in covered)
    return area / ((maxx - minx) * (maxy - miny))


def select_tiles(
    tiles: Sequence[TileRef],
    aoi_bounds: tuple[float, float, float, float],
    allow_mixed_epochs: bool = False,
    min_coverage: float = MIN_COVERAGE,
    max_area_km2: float = 200.0,
    sortie_gap_hours: float = SORTIE_GAP_HOURS,
) -> Selection:
    """Choose the tiles that actually cover the AOI, preferring a single flight.

    Coverage is measured, not assumed from intersection. Where one footprint was flown more
    than once, exactly one acquisition is kept: consistency on the spatial axis is not
    consistency on the temporal one, and a mosaic of two epochs registered onto one grid is
    harder to notice, not easier.

    "One flight" means one **sortie**, not one stamp. The catalogue stamps each tile with
    the moment it was acquired, so a single pass appears as several stamps minutes apart;
    treating those as distinct epochs would refuse a perfectly uniform AOI.
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

    # Coverage per sortie, so "dominant" means "covers most of this AOI", not "most tiles"
    # and not "most stamps" — one pass spread over four stamps must not lose to a single
    # stamp from another flight.
    sortie_of = {
        stamp: index
        for index, group in enumerate(_sorties((t.flight_date for t in touching), sortie_gap_hours))
        for stamp in group
    }
    by_sortie: dict[int, float] = {}
    for t in touching:
        index = sortie_of[t.flight_date]
        by_sortie[index] = by_sortie.get(index, 0.0) + _overlap_area(t, aoi_bounds)
    dominant = max(sorted(by_sortie), key=lambda i: by_sortie[i])

    kept: dict[tuple[float, float], TileRef] = {}
    dropped: list[str] = []
    for t in sorted(
        touching,
        key=lambda t: (t.footprint_key, sortie_of[t.flight_date] != dominant, t.item_id),
    ):
        if t.footprint_key in kept:
            dropped.append(t.item_id)
        else:
            kept[t.footprint_key] = t

    chosen = tuple(sorted(kept.values(), key=lambda t: (t.minx, t.miny)))
    dates = tuple(sorted({t.flight_date for t in chosen}))
    sorties = _sorties(dates, sortie_gap_hours)
    if len(sorties) > 1 and not allow_mixed_epochs:
        spans = ", ".join(f"{g[0]}..{g[-1]}" if len(g) > 1 else g[0] for g in sorties)
        raise SelectionError(
            f"AOI spans {len(sorties)} sorties ({spans}); a mosaic of two epochs is a product "
            f"made of two moments — pass allow_mixed_epochs to accept and declare it"
        )

    covered = _covered_fraction(chosen, aoi_bounds)
    if covered < min_coverage:
        raise SelectionError(
            f"selection covers {covered:.4f} of the AOI, need {min_coverage:.4f}; "
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
        sorties=sorties,
        mixed_epochs=len(sorties) > 1,
        dropped_duplicates=tuple(dropped),
    )

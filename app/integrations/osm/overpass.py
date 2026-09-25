"""
Overpass API client and OSM building parsing.

SIH 2026 PS 26011 — real source data for the on-demand ingestion pipeline.

Data provenance
---------------
Every footprint returned here is OpenStreetMap data (ODbL 1.0), referenced by
``osm_type`` + ``osm_id`` so it can be independently re-fetched from
``https://www.openstreetmap.org/{type}/{id}``. Height and floor counts are taken
from the contributor-entered ``height`` and ``building:levels`` tags. When only
``building:levels`` exists, a documented floor-to-floor constant is applied and
the result is flagged as DERIVED rather than REAL — nothing is invented, and
``height_m`` stays ``None`` when OSM carries no signal at all.

This module performs NO database writes and NO ULPIN generation.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

from app.core.logging import logger

# Public Overpass API endpoints. They all serve the same ODbL OpenStreetMap
# data; failover exists because a single mirror rate-limits or times out under
# load (observed: HTTP 504 from overpass-api.de on a trivial way query).
OVERPASS_ENDPOINTS: Tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

USER_AGENT = "STRATA-Cadastral-Ingest/1.0 (SIH 2026 PS26011; contact: project repo)"

# Floor-to-floor height used ONLY when OSM supplies `building:levels` but no
# `height` tag. This is the standard storey-to-storey constant used across the
# ML engine (see ml-engine floors detector / height estimator). Values derived
# this way are tagged DERIVED and never presented as surveyed heights.
FLOOR_TO_FLOOR_M = 3.2

# Bounding box of India (incl. islands) used to reject out-of-scope coordinates
# before any network call is made.
INDIA_BBOX = (68.0, 6.5, 97.5, 37.5)  # (min_lon, min_lat, max_lon, max_lat)

_HEIGHT_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)")


class OverpassError(RuntimeError):
    """Raised when no Overpass mirror returned a usable response."""


def is_within_india(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = INDIA_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


@dataclass
class OSMBuilding:
    """A real OSM building footprint plus the attributes OSM actually declares."""

    osm_type: str  # "way" | "relation"
    osm_id: int
    name: Optional[str]
    tags: Dict[str, str]
    outer_ring: List[Tuple[float, float]]  # [(lon, lat), ...], closed
    height_m: Optional[float]
    height_source: str  # osm_height_tag | osm_levels_derived | unavailable
    floor_count: Optional[int]
    floor_source: str  # osm_levels_tag | unavailable

    @property
    def source_url(self) -> str:
        return f"https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}"

    @property
    def osm_reference(self) -> str:
        return f"{self.osm_type}/{self.osm_id}"

    @property
    def area_sq_deg(self) -> float:
        """Planar shoelace area in square degrees (used only for ranking)."""
        ring = self.outer_ring
        if len(ring) < 4:
            return 0.0
        total = 0.0
        for i in range(len(ring) - 1):
            x1, y1 = ring[i]
            x2, y2 = ring[i + 1]
            total += (x1 * y2) - (x2 * y1)
        return abs(total) / 2.0

    def centroid(self) -> Tuple[float, float]:
        """Return (lon, lat) centroid of the footprint ring."""
        ring = self.outer_ring[:-1] if len(self.outer_ring) > 1 else self.outer_ring
        if not ring:
            raise ValueError("footprint has no coordinates")
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
        return lon, lat

    def to_geojson_polygon(self) -> Dict[str, Any]:
        return {
            "type": "Polygon",
            "coordinates": [[[round(lon, 7), round(lat, 7)] for lon, lat in self.outer_ring]],
        }

    def to_wkt(self) -> str:
        from shapely.geometry import Polygon

        return Polygon(self.outer_ring).wkt

    def evidence_item(self) -> Dict[str, Any]:
        """A real, resolvable evidence record for the ML contract."""
        return {
            "source": f"OpenStreetMap {self.osm_reference}",
            "type": "other",
            "reliability": 0.40,  # crowd-sourced; matches ML fusion 'osm' weight
            "date": self.tags.get("check_date") or self.tags.get("source:date"),
        }


# --------------------------------------------------------------------------- #
# Pure parsing helpers (unit-testable without any network access)
# --------------------------------------------------------------------------- #


def _extract_lon_lat(point: Any) -> Optional[Tuple[float, float]]:
    """
    Accept both Overpass geometry encodings.

    ``out geom`` emits ``{"lat": .., "lon": ..}`` objects, while some tooling
    yields ``[lon, lat]`` sequences. Both are real and must parse.
    """
    if isinstance(point, dict):
        lon, lat = point.get("lon"), point.get("lat")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        lon, lat = point[0], point[1]
    else:
        return None
    try:
        lon_f, lat_f = float(lon), float(lat)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lon_f) and math.isfinite(lat_f)):
        return None
    return lon_f, lat_f


def _clean_ring(coords: Iterable[Any]) -> List[Tuple[float, float]]:
    """Normalise an OSM coordinate list into a closed, duplicate-free ring."""
    ring: List[Tuple[float, float]] = []
    for point in coords:
        extracted = _extract_lon_lat(point)
        if extracted is None:
            continue
        if ring and ring[-1] == extracted:
            continue
        ring.append(extracted)
    if len(ring) >= 3 and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def derive_height(tags: Dict[str, str], floor_count: Optional[int]) -> Tuple[Optional[float], str]:
    """
    Resolve building height from OSM tags.

    Priority:
      1. ``height`` (metres) — contributor-surveyed/measured -> REAL signal.
      2. ``building:levels`` x FLOOR_TO_FLOOR_M — DERIVED, explicitly flagged.
      3. ``None`` — OSM carries no height signal. Never guess.
    """
    raw = (tags or {}).get("height")
    if raw:
        match = _HEIGHT_PATTERN.search(str(raw))
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                value = 0.0
            # Ignore non-positive or absurd values rather than trusting them.
            if 0.0 < value <= 500.0:
                return value, "osm_height_tag"

    if floor_count and floor_count > 0:
        return round(floor_count * FLOOR_TO_FLOOR_M, 2), "osm_levels_derived"

    return None, "unavailable"


def derive_floor_count(tags: Dict[str, str]) -> Tuple[Optional[int], str]:
    """
    Resolve floor count from the ``building:levels`` tag (real OSM metadata).

    Accepts the variants contributors actually use: ``6``, ``6.0``, ``6;7``.
    """
    raw = (tags or {}).get("building:levels")
    if raw is None:
        return None, "unavailable"
    match = _HEIGHT_PATTERN.search(str(raw))
    if not match:
        return None, "unavailable"
    try:
        floors = int(float(match.group(1)))
    except ValueError:
        return None, "unavailable"
    if 1 <= floors <= 200:
        return floors, "osm_levels_tag"
    return None, "unavailable"


def parse_building_element(element: Dict[str, Any]) -> Optional[OSMBuilding]:
    """
    Convert one Overpass JSON element into an :class:`OSMBuilding`.

    Returns ``None`` for elements that are not polygonal buildings — e.g. a
    ``way`` with fewer than three geometry points, or a node.
    """
    if not isinstance(element, dict):
        return None
    osm_type = element.get("type")
    osm_id = element.get("id")
    tags = element.get("tags") or {}
    if osm_type not in {"way", "relation"} or osm_id is None:
        return None
    if not isinstance(tags, dict):
        tags = {}
    if "building" not in tags and "building:part" not in tags:
        return None

    geometry = element.get("geometry")
    if not isinstance(geometry, list) and not element.get("members"):
        return None
    if not isinstance(geometry, list):
        # Relations (multipolygons) without resolved member geometry cannot be
        # turned into a single footprint here; skipped rather than guessed.
        return None

    ring = _clean_ring(geometry)
    if len(ring) < 4:
        return None

    floors, floor_source = derive_floor_count(tags)
    height_m, height_source = derive_height(tags, floors)

    return OSMBuilding(
        osm_type=osm_type,
        osm_id=int(osm_id),
        name=tags.get("name") or tags.get("official_name"),
        tags={str(k): str(v) for k, v in tags.items()},
        outer_ring=ring,
        height_m=height_m,
        height_source=height_source,
        floor_count=floors,
        floor_source=floor_source,
    )


def pick_target_buildings(
    buildings: Sequence[OSMBuilding],
    *,
    name_contains: Optional[str] = None,
    osm_id: Optional[int] = None,
) -> List[OSMBuilding]:
    """
    Narrow a radius result set down to the building(s) actually being ingested.

    Without either filter every footprint in the radius is returned, which is
    the desired behaviour for area ingestion. With ``name_contains`` the match is
    a case-insensitive substring on the OSM ``name``/``official_name`` tag.
    """
    selected: List[OSMBuilding] = list(buildings)
    if osm_id is not None:
        selected = [b for b in selected if b.osm_id == int(osm_id)]
    if name_contains:
        needle = name_contains.strip().lower()
        if needle:
            selected = [
                b
                for b in selected
                if b.name and needle in b.name.lower()
            ]
    # Largest footprint first: for area ingestion the big named buildings matter
    # most, and this keeps a truncated run deterministic.
    return sorted(selected, key=lambda b: b.area_sq_deg, reverse=True)


# --------------------------------------------------------------------------- #
# Query builders
# --------------------------------------------------------------------------- #


def build_around_query(
    lat: float,
    lon: float,
    radius_m: float,
    *,
    name_contains: Optional[str] = None,
    timeout_s: int = 40,
) -> str:
    filters = '["building"]'
    if name_contains:
        # Overpass QL regex; escape quotes only — the value is user supplied.
        safe = name_contains.replace('"', '\\"')
        filters += f'["name"~"{safe}",i]'
    return (
        f"[out:json][timeout:{int(timeout_s)}];"
        f"way(around:{float(radius_m)},{float(lat)},{float(lon)}){filters};"
        f"out geom tags;"
    )


def build_osm_id_query(osm_id: int, *, timeout_s: int = 40) -> str:
    return f"[out:json][timeout:{int(timeout_s)}];way({int(osm_id)});out geom tags;"


# --------------------------------------------------------------------------- #
# Network client
# --------------------------------------------------------------------------- #


class OverpassClient:
    """
    Async Overpass API client with mirror failover.

    Every call is a live query against public OSM infrastructure — there is no
    cached or bundled fixture, so what lands in PostGIS is always re-checkable
    against the upstream OSM object.
    """

    #: How long a fetched OSM response may be reused within this process.
    #: Public Overpass mirrors rate-limit and intermittently return 504, and a
    #: demo that re-ingests the same location should not re-query for identical
    #: data. The cache is in-memory only (never persisted, never presented as
    #: newer than it is) and always keyed by the exact query string.
    CACHE_TTL_S = 600.0
    CACHE_MAX_ENTRIES = 64

    def __init__(
        self,
        endpoints: Sequence[str] = OVERPASS_ENDPOINTS,
        timeout_s: float = 30.0,
        max_attempts_per_endpoint: int = 2,
        total_budget_s: float = 75.0,
    ):
        self.endpoints = tuple(endpoints)
        # Per-request socket timeout. A mirror that has not answered within this
        # window is treated as unusable; the previous 90 s value allowed a single
        # call to hang for minutes across the mirror list.
        self.timeout_s = timeout_s
        self.max_attempts_per_endpoint = max(1, max_attempts_per_endpoint)
        # Hard wall-clock ceiling for one logical query across ALL mirrors.
        self.total_budget_s = total_budget_s
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

    def _cache_get(self, query: str) -> Optional[List[Dict[str, Any]]]:
        entry = self._cache.get(query)
        if not entry:
            return None
        stored_at, elements = entry
        if (asyncio.get_event_loop().time() - stored_at) > self.CACHE_TTL_S:
            self._cache.pop(query, None)
            return None
        logger.info("Overpass query served from in-process cache")
        return elements

    def _cache_put(self, query: str, elements: List[Dict[str, Any]]) -> None:
        if len(self._cache) >= self.CACHE_MAX_ENTRIES:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            self._cache.pop(oldest, None)
        self._cache[query] = (asyncio.get_event_loop().time(), elements)

    async def _post(self, query: str) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        deadline = asyncio.get_event_loop().time() + self.total_budget_s
        for endpoint in self.endpoints:
            for attempt in range(self.max_attempts_per_endpoint):
                if asyncio.get_event_loop().time() >= deadline:
                    logger.warning("Overpass total time budget exhausted")
                    raise OverpassError(
                        f"Overpass time budget of {self.total_budget_s}s exhausted; "
                        f"last error: {last_error}"
                    )
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                        res = await client.post(
                            endpoint,
                            data={"data": query},
                            headers={"User-Agent": USER_AGENT},
                        )
                    if res.status_code == 200:
                        return res.json()
                    # 429/502/503/504 are transient on the public mirrors.
                    last_error = OverpassError(
                        f"{endpoint} returned HTTP {res.status_code}"
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                except Exception as exc:  # network/timeout/JSON
                    last_error = exc
                    logger.warning(
                        "Overpass request failed",
                        endpoint=endpoint,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
            logger.info("Overpass mirror exhausted", endpoint=endpoint)
        raise OverpassError(
            f"All Overpass mirrors failed: {last_error}"
        )

    async def fetch_elements(self, query: str) -> List[Dict[str, Any]]:
        cached = self._cache_get(query)
        if cached is not None:
            return cached
        payload = await self._post(query)
        elements = payload.get("elements")
        if not isinstance(elements, list):
            raise OverpassError("Overpass response contained no 'elements' list")
        self._cache_put(query, elements)
        return elements

    async def buildings_around(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        *,
        name_contains: Optional[str] = None,
    ) -> List[OSMBuilding]:
        if not is_within_india(lon, lat):
            raise OverpassError(
                f"Coordinate {lat},{lon} is outside the India extent; refusing to query."
            )
        query = build_around_query(lat, lon, radius_m, name_contains=name_contains)
        elements = await self.fetch_elements(query)
        parsed = [parse_building_element(e) for e in elements]
        return [b for b in parsed if b is not None]

    async def building_by_osm_id(self, osm_id: int) -> Optional[OSMBuilding]:
        elements = await self.fetch_elements(build_osm_id_query(osm_id))
        for element in elements:
            parsed = parse_building_element(element)
            if parsed is not None:
                return parsed
        return None

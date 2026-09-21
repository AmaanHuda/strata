"""Search query and response schemas."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    entity_type: str
    entity_id: UUID
    identifier: str
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str
    location_summary: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]


class SpatialEntityItem(BaseModel):
    id: UUID
    entity_type: str  # parcel or building
    identifier: str
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str
    area_sqm: Optional[float] = None
    height_m: Optional[float] = None
    floor_count: Optional[int] = None
    geometry_geojson: Optional[Dict[str, Any]] = None
    centroid: Optional[Dict[str, float]] = None
    distance_m: Optional[float] = None


class SpatialBBoxResponse(BaseModel):
    bbox: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    layer: str
    crs: str = "EPSG:4326"
    count: int
    results: List[SpatialEntityItem]


class SpatialNearbyResponse(BaseModel):
    center_lat: float
    center_lon: float
    radius_m: float
    crs: str = "EPSG:4326"
    count: int
    results: List[SpatialEntityItem]


class SpatialQueryRequest(BaseModel):
    polygon_wkt: Optional[str] = None
    polygon_geojson: Optional[Dict[str, Any]] = None
    layer: str = "all"  # parcel, building, all
    relation: str = "intersects"  # intersects, contains, within
    limit: int = 50


class PointLookupResponse(BaseModel):
    lat: float
    lon: float
    parcel: Optional[SpatialEntityItem] = None
    building: Optional[SpatialEntityItem] = None
    floors_count: Optional[int] = None
    units_count: Optional[int] = None

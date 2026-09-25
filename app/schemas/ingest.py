"""
On-demand ingestion schemas (any lat/lon in India -> real records).

Everything produced by this path is CANDIDATE / non-authoritative: real
OpenStreetMap geometry and tags, optionally enriched by the ML engine. No
official ULPIN is ever issued here.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestLocationRequest(BaseModel):
    """Fetch real building footprints near a coordinate and persist them."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude (WGS84)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude (WGS84)")
    radius_m: float = Field(
        150.0,
        ge=10.0,
        le=2000.0,
        description="Overpass search radius in metres around the coordinate",
    )
    name_contains: Optional[str] = Field(
        None,
        max_length=120,
        description="Case-insensitive substring of the OSM `name` tag, e.g. 'Taj Mahal Palace'",
    )
    osm_id: Optional[int] = Field(
        None, description="Ingest one specific OSM way id instead of a radius scan"
    )
    max_buildings: int = Field(
        1, ge=1, le=25, description="Cap on footprints ingested in one call"
    )
    # Optional cadastral context. When omitted the values are read from the real
    # OSM addr:* tags and the numeric code segments are assigned deterministically
    # (and labelled as application-internal, never as official LGD codes).
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    taluk: Optional[str] = Field(None, max_length=100)
    village: Optional[str] = Field(None, max_length=100)
    run_ml: bool = Field(
        True,
        description="Invoke the ML engine for height/floor/unit delineation. "
        "Skipped automatically when the engine is disabled or unreachable.",
    )


class IngestedUnitOut(BaseModel):
    id: UUID
    unit_number: str
    unit_type: Optional[str] = None
    area_sqm: Optional[float] = None
    candidate_ulpin: Optional[str] = None
    status: str
    ml_derived: bool


class IngestedFloorOut(BaseModel):
    id: UUID
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[float] = None
    candidate_ulpin: Optional[str] = None
    status: str
    floor_source: Optional[str] = None
    units: List[IngestedUnitOut] = Field(default_factory=list)


class IngestedBuildingOut(BaseModel):
    """One real building persisted by this call, with its full provenance."""

    building_id: UUID
    parcel_id: UUID
    parcel_number: str

    building_name: Optional[str] = None
    building_type: Optional[str] = None

    # Traceability back to the exact upstream source object
    osm_type: str
    osm_id: int
    source_url: str
    osm_tags: Dict[str, Any] = Field(default_factory=dict)

    height_m: Optional[float] = None
    height_source: Optional[str] = None
    floor_count: Optional[int] = None
    floor_source: Optional[str] = None
    footprint_area_sqm: Optional[float] = None
    footprint_geojson: Optional[Dict[str, Any]] = None
    centroid: Optional[Dict[str, float]] = None

    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str

    ml_used: bool
    ml_model_version: Optional[str] = None
    ml_confidence: Optional[float] = None
    ml_data_status: Optional[str] = None
    ml_review_status: Optional[str] = None
    ml_validation: Optional[Dict[str, Any]] = None

    floors: List[IngestedFloorOut] = Field(default_factory=list)
    units_created: int = 0
    already_existed: bool = False


class IngestLocationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query_lat: float
    query_lon: float
    radius_m: float
    source: str = "OpenStreetMap (ODbL 1.0) via Overpass API"
    buildings_found: int
    buildings_ingested: int
    buildings_skipped: int
    parcels_created: int
    parcels_reused: int
    floors_created: int
    units_created: int
    candidate_ulpins: List[str] = Field(default_factory=list)
    buildings: List[IngestedBuildingOut] = Field(default_factory=list)
    skipped_reasons: List[str] = Field(default_factory=list)
    authoritative: bool = False
    disclaimers: List[str] = Field(default_factory=list)

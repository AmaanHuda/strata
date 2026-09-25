"""
Property hierarchy schemas: Parcel, Building, Floor, Unit.
No private owner info stored or exposed.
Includes candidate/official ULPINs, 3D geometric properties, and temporal fields.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParcelCreate(BaseModel):
    parcel_number: str = Field(..., min_length=1, max_length=100)
    survey_number: Optional[str] = None
    district: str = Field(..., min_length=1, max_length=100)
    taluk: Optional[str] = None
    village: Optional[str] = None
    state: str = "India"
    land_use: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    boundary_wkt: Optional[str] = None
    geometry_geojson: Optional[Dict[str, Any]] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    official_ulpin: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class ParcelUpdate(BaseModel):
    survey_number: Optional[str] = None
    land_use: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    boundary_wkt: Optional[str] = None
    is_verified: Optional[bool] = None
    official_ulpin: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class ParcelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    parcel_number: str
    survey_number: Optional[str] = None
    district: str
    taluk: Optional[str] = None
    village: Optional[str] = None
    state: str
    land_use: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    boundary_wkt: Optional[str] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    confidence_score: float = 1.0
    version: int = 1
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class BuildingCreate(BaseModel):
    parcel_id: UUID
    building_name: Optional[str] = None
    building_type: Optional[str] = None
    floor_count: Optional[int] = None
    floor_count_above_ground: Optional[int] = None
    floor_count_below_ground: Optional[int] = None
    height_m: Optional[float] = None
    height_confidence: Optional[float] = None
    uncertainty_range_m: Optional[float] = None
    footprint_wkt: Optional[str] = None
    footprint_geojson: Optional[Dict[str, Any]] = None
    footprint_area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"
    construction_year: Optional[int] = None
    official_ulpin: Optional[str] = None
    ml_derived: bool = False
    ml_model_version: Optional[str] = None
    ml_confidence_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class BuildingUpdate(BaseModel):
    building_name: Optional[str] = None
    building_type: Optional[str] = None
    floor_count: Optional[int] = None
    height_m: Optional[float] = None
    is_verified: Optional[bool] = None
    official_ulpin: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    parcel_id: UUID
    building_name: Optional[str] = None
    building_type: Optional[str] = None
    floor_count: Optional[int] = None
    floor_count_above_ground: Optional[int] = None
    floor_count_below_ground: Optional[int] = None
    height_m: Optional[float] = None
    height_confidence: Optional[float] = None
    uncertainty_range_m: Optional[float] = None
    footprint_wkt: Optional[str] = None
    footprint_area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    ml_derived: bool = False
    ml_model_version: Optional[str] = None
    ml_confidence_score: Optional[float] = None
    version: int = 1
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class FloorCreate(BaseModel):
    building_id: UUID
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    official_ulpin: Optional[str] = None
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    building_id: UUID
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class UnitCreate(BaseModel):
    floor_id: UUID
    unit_number: str
    unit_type: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    is_occupied: Optional[bool] = None
    official_ulpin: Optional[str] = None
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    floor_id: UUID
    unit_number: str
    unit_type: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    is_occupied: Optional[bool] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class PropertyHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    entity_type: str
    version: int
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_active: bool = True
    status: str = "CANDIDATE"
    change_summary: Optional[str] = None


class CentroidPoint(BaseModel):
    lat: float
    lon: float


class UnitStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    floor_id: UUID
    unit_number: str
    unit_type: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    is_occupied: Optional[bool] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    # Deterministic 3D ULPIN (SYSTEM GENERATED). None when real unit geometry is
    # absent — no identifier is fabricated in that case.
    three_d_ulpin: Optional[str] = None
    object_type: Optional[str] = None
    z_min_m: Optional[float] = None
    z_max_m: Optional[float] = None


class FloorStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    building_id: UUID
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[Decimal] = None
    volume_cum: Optional[Decimal] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    # Deterministic 3D ULPIN (SYSTEM GENERATED): floor code + vertical range.
    three_d_ulpin: Optional[str] = None
    floor_code: Optional[str] = None
    object_type: Optional[str] = None
    z_min_m: Optional[float] = None
    z_max_m: Optional[float] = None
    units: List[UnitStructureOut] = Field(default_factory=list)


class BuildingStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    building_id: UUID
    parcel_id: UUID
    building_name: Optional[str] = None
    building_type: Optional[str] = None
    floor_count: Optional[int] = None
    height_m: Optional[float] = None
    footprint_area_sqm: Optional[Decimal] = None
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str = "CANDIDATE"
    is_verified: bool = False
    # Deterministic 3D ULPIN (SYSTEM GENERATED) — never labelled "Official ULPIN".
    three_d_ulpin: Optional[str] = None
    parcel_three_d_ulpin: Optional[str] = None
    object_type: Optional[str] = None
    algorithm_version: Optional[str] = None
    canonicalization_version: Optional[str] = None
    # "SYSTEM GENERATED" when present, otherwise the honest reason it is absent.
    three_d_ulpin_status: Optional[str] = None
    centroid: Optional[CentroidPoint] = None
    address: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    floors: List[FloorStructureOut] = Field(default_factory=list)


class BuildingGeometryOut(BaseModel):
    building_id: UUID
    parcel_id: UUID
    centroid: Optional[CentroidPoint] = None
    height_m: Optional[float] = None
    elevation_m: Optional[float] = None
    footprint_wkt: Optional[str] = None
    footprint_geojson: Optional[Dict[str, Any]] = None
    bounds: Optional[List[float]] = None
    geometry_3d_lod2: Optional[Dict[str, Any]] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"

"""Property hierarchy schemas."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParcelCreate(BaseModel):
    parcel_number: str = Field(..., min_length=1, max_length=100)
    survey_number: Optional[str] = None
    district: str
    taluk: Optional[str] = None
    village: Optional[str] = None
    state: str = "India"
    land_use: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    geometry_wkt: Optional[str] = None  # WKT geometry
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class ParcelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    parcel_number: str
    survey_number: Optional[str]
    district: str
    taluk: Optional[str]
    village: Optional[str]
    state: str
    land_use: Optional[str]
    area_sqm: Optional[Decimal]
    is_verified: bool
    version: int
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
    footprint_wkt: Optional[str] = None
    footprint_area_sqm: Optional[Decimal] = None
    construction_year: Optional[int] = None
    ml_derived: bool = False
    ml_model_version: Optional[str] = None
    ml_confidence_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    parcel_id: UUID
    building_name: Optional[str]
    building_type: Optional[str]
    floor_count: Optional[int]
    height_m: Optional[float]
    height_confidence: Optional[float]
    footprint_area_sqm: Optional[Decimal]
    is_verified: bool
    ml_derived: bool
    ml_confidence_score: Optional[float]
    version: int
    created_at: datetime


class FloorCreate(BaseModel):
    building_id: UUID
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[Decimal] = None
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    building_id: UUID
    floor_number: int
    floor_label: Optional[str]
    floor_use: Optional[str]
    height_above_ground_m: Optional[float]
    ceiling_height_m: Optional[float]
    floor_area_sqm: Optional[Decimal]
    is_verified: bool
    ml_derived: bool
    created_at: datetime


class UnitCreate(BaseModel):
    floor_id: UUID
    unit_number: str
    unit_type: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    owner_name: Optional[str] = None
    is_occupied: Optional[bool] = None
    ml_derived: bool = False
    ml_confidence_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    floor_id: UUID
    unit_number: str
    unit_type: Optional[str]
    area_sqm: Optional[Decimal]
    owner_name: Optional[str]
    is_occupied: Optional[bool]
    is_verified: bool
    ml_derived: bool
    created_at: datetime

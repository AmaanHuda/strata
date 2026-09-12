"""Dataset registry schemas."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DatasetRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    version: str = "1.0.0"
    source: Optional[str] = None
    authority: Optional[str] = None
    license: Optional[str] = "Gov-Open"
    acquisition_date: Optional[str] = None
    modality: str = Field(..., description="satellite, lidar, dem, dsm, drone, cadastral_vector, osm")
    crs: str = "EPSG:4326"
    resolution_m: Optional[str] = None
    coverage_area: Optional[str] = None
    record_count: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    name: str
    version: str
    source: Optional[str] = None
    license: Optional[str] = None
    modality: Optional[str] = None
    crs: Optional[str] = None
    resolution_m: Optional[str] = None
    coverage_area: Optional[str] = None
    record_count: Optional[str] = None
    is_active: bool
    ingested_at: datetime

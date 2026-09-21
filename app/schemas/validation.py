"""Cadastral topology and 3D geometry validation schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus:
    PASS = "PASS"
    WARNING = "WARNING"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class ValidationCheckResult(BaseModel):
    check_name: str
    status: str = Field(..., description="PASS, WARNING, REVIEW, FAIL")
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PropertyValidationReport(BaseModel):
    property_id: UUID
    entity_type: str
    overall_status: str
    score: float
    is_authoritative_ready: bool
    checks: List[ValidationCheckResult]
    validated_at: datetime
    summary: str


class GeometryValidationRequest(BaseModel):
    geometry_wkt: Optional[str] = None
    geometry_geojson: Optional[Dict[str, Any]] = None
    crs: str = "EPSG:4326"
    expected_dim: Optional[str] = "2D"  # 2D or 3D
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    height_m: Optional[float] = None


class GeometryValidationResponse(BaseModel):
    is_valid: bool
    geom_type: Optional[str] = None
    crs: str
    dimension: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class TopologyValidationRequest(BaseModel):
    parcel_wkt: Optional[str] = None
    building_wkt: Optional[str] = None
    adjacent_building_wkts: Optional[List[str]] = Field(default_factory=list)
    floors_data: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    units_data: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class TopologyValidationResponse(BaseModel):
    is_valid: bool
    overall_status: str  # PASS, WARNING, REVIEW, FAIL
    checks: List[ValidationCheckResult]
    summary: str


class CadastralValidationRequest(BaseModel):
    parcel_id: Optional[UUID] = None
    building_id: Optional[UUID] = None
    validate_hierarchy: bool = True
    check_3d_consistency: bool = True
    check_ulpin_registry: bool = True


class CadastralValidationResponse(BaseModel):
    is_valid: bool
    overall_status: str
    entity_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    checks: List[ValidationCheckResult]
    summary: str
    timestamp: datetime

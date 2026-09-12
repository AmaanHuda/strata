"""
ML Engine API contract schemas.
These define the interface between the backend and the 3D-Mapping-ml-engine.
Any schema changes must be coordinated with both repos.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class HeightEstimationRequest(BaseModel):
    """Request to estimate building height from satellite/lidar data."""
    parcel_id: str
    building_id: str
    lat: float
    lon: float
    imagery_source: Optional[str] = "satellite"
    model_version: Optional[str] = "latest"


class HeightEstimationResponse(BaseModel):
    building_id: str
    estimated_height_m: float
    confidence_score: float  # 0.0 â€“ 1.0
    confidence_label: str    # HIGH | MEDIUM | LOW | INSUFFICIENT
    floor_count_estimate: Optional[int] = None
    model_version: str
    inference_time_ms: float
    uncertainty_range_m: Optional[float] = None
    legal_disclaimer: str = (
        "AI-derived height estimates are analytical/candidate outputs "
        "and do not constitute authoritative cadastral records."
    )


class BuildingExtractionRequest(BaseModel):
    parcel_id: str
    bbox: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    imagery_source: Optional[str] = "satellite"
    model_version: Optional[str] = "latest"


class BuildingExtractionResponse(BaseModel):
    parcel_id: str
    buildings: List[Dict[str, Any]]  # list of {footprint_wkt, confidence, area_sqm}
    model_version: str
    processing_time_ms: float
    legal_disclaimer: str = (
        "ML-extracted building footprints are candidate outputs requiring survey validation."
    )


class FloorCountRequest(BaseModel):
    building_id: str
    height_m: Optional[float] = None
    imagery_source: Optional[str] = "satellite"


class FloorCountResponse(BaseModel):
    building_id: str
    floor_count: int
    floor_count_above_ground: int
    floor_count_below_ground: int
    confidence_score: float
    model_version: str


class MLHealthResponse(BaseModel):
    status: str
    version: str
    models_loaded: List[str]
    gpu_available: bool

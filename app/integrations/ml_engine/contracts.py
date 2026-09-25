"""
ML Engine API contract schemas.
Defines interfaces for all 9 ML operations + Result Ingestion + ML Output Contract v1.0.0.
Coordinates directly with 3D-Mapping-ml-engine repository schemas.
"""
from typing import Any, Dict, List, Optional, Union, Tuple
from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_SCHEMA_VERSIONS = ["1.0.0", "1.1.0", "2.0.0"]


class MLHealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    device: str = "cpu"
    components_available: List[str] = Field(default_factory=list)
    trained_models_loaded: bool = False
    models_loaded: List[str] = Field(default_factory=list)
    datasets_available: bool = False
    inference_ready: str = "baseline_only"


# 1. Building Extraction
class BuildingExtractionRequest(BaseModel):
    bbox: List[float] = Field(..., description="[min_lon, min_lat, max_lon, max_lat]")
    image_source: Optional[str] = "satellite"
    confidence_threshold: float = 0.5
    model_version: Optional[str] = "latest"


class ExtractedBuildingItem(BaseModel):
    polygon_wkt: str
    confidence: float
    bbox: List[float]
    area_sqm: Optional[float] = None


class BuildingExtractionResponse(BaseModel):
    status: str
    buildings_found: int
    buildings: List[ExtractedBuildingItem]
    model_version: str


# 2. Height Estimation
class HeightEstimationRequest(BaseModel):
    parcel_id: str
    building_id: str
    lat: float
    lon: float
    footprint_wkt: Optional[str] = None
    imagery_source: Optional[str] = "satellite"
    model_version: Optional[str] = "latest"


class HeightEstimationResponse(BaseModel):
    status: str
    estimated_height_m: float
    confidence_score: float
    uncertainty_range_m: Optional[float] = None
    floor_count_estimate: Optional[int] = None
    method: str
    model_version: str


# 3. Floor Detection / Estimation
class FloorCountRequest(BaseModel):
    building_id: str
    height_m: float
    building_type: Optional[str] = "residential"
    facade_image_url: Optional[str] = None


class FloorCountResponse(BaseModel):
    status: str
    floor_count: int
    floor_count_above_ground: int
    floor_count_below_ground: int
    estimated_ceiling_height_m: float
    confidence: float
    method: str


# 4. Change Detection
class ChangeDetectionRequest(BaseModel):
    parcel_id: str
    t1_image_url: Optional[str] = None
    t2_image_url: Optional[str] = None
    footprint_wkt: Optional[str] = None


class ChangeDetectionResponse(BaseModel):
    has_changed: bool
    change_type: str
    confidence: float
    change_area_sqm: Optional[float] = None


# 5. 3D Reconstruction
class Reconstruction3DRequest(BaseModel):
    building_id: str
    footprint_wkt: str
    height_m: float
    floor_count: int
    roof_type: Optional[str] = "flat"


class Reconstruction3DResponse(BaseModel):
    status: str
    lod: str = "LoD2"
    mesh_format: str = "gltf"
    volume_cum: float
    polyhedral_wkt: Optional[str] = None
    confidence: float


# 6. Vertical Unit Partitioning
class VerticalUnitGenRequest(BaseModel):
    floor_id: Optional[str] = None
    building_id: Optional[str] = None
    floor_number: int
    floor_area_sqm: float
    building_type: str = "residential"
    target_units_per_floor: Optional[int] = None


class GeneratedUnit(BaseModel):
    unit_number: str
    unit_type: str
    area_sqm: float
    volume_cum: Optional[float] = None
    confidence: float


class VerticalUnitGenResponse(BaseModel):
    status: str
    floor_number: int
    units: List[GeneratedUnit]


# 7. Evidence Fusion
class EvidenceFusionRequest(BaseModel):
    parcel_id: str
    optical_height_m: Optional[float] = None
    shadow_height_m: Optional[float] = None
    lidar_height_m: Optional[float] = None
    street_view_floors: Optional[int] = None


class EvidenceFusionResponse(BaseModel):
    fused_height_m: float
    fused_floors: int
    confidence: float
    evidence_sources: List[str]


# 8. Confidence Calculation
class ConfidenceCalcRequest(BaseModel):
    evidence_scores: Dict[str, float]


class ConfidenceCalcResponse(BaseModel):
    overall_confidence: float
    rating: str


# 9. Output Validation
class OutputValidationRequest(BaseModel):
    footprint_wkt: str
    height_m: float
    floors: int


class OutputValidationResponse(BaseModel):
    is_valid: bool
    violations: List[str] = Field(default_factory=list)


# 10. ML Engine Output Contract v1.0.0 (Canonical output from MLEnginePipeline.process_parcel)
class MLEvidenceItem(BaseModel):
    source: str
    type: str
    reliability: float
    date: Optional[str] = None


class MLValidationBlock(BaseModel):
    status: str
    issues: List[str] = Field(default_factory=list)


class MLOutputContractV1(BaseModel):
    """
    ML Output Contract v1.0.0.
    Directly matches schemas/ml_output_contract.json produced by MLEnginePipeline.process_parcel().
    """
    schema_version: str = "1.0.0"
    official_ulpin: str
    building_id: str
    floor_id: Optional[str] = None
    unit_id: Optional[str] = None
    volume_id: Optional[str] = None
    geometry: Dict[str, Any]
    geometry_crs: str = "EPSG:4326"
    height: Optional[float] = None
    floor_count: Optional[int] = None
    confidence: float
    uncertainty: float
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    review_status: str
    data_status: str
    model_version: str
    dataset_version: str
    provenance_id: str
    generated_at: str


class MLProcessParcelRequest(BaseModel):
    """Request model for MLEnginePipeline.process_parcel()."""
    official_ulpin: str = Field(..., description="Official or candidate 2D ULPIN/reference identifier")
    parcel_polygon: List[Union[List[float], Tuple[float, float]]] = Field(..., description="Parcel boundary coordinates [[lon, lat], ...]")
    building_footprint: Optional[List[Union[List[float], Tuple[float, float]]]] = Field(None, description="Building footprint coordinates")
    height_m: Optional[float] = Field(None, description="Building height in meters if available")
    evidence: Optional[List[Dict[str, Any]]] = Field(None, description="Multi-source evidence list")
    crs: str = Field("EPSG:4326", description="Coordinate Reference System")
    # Real upstream metadata (e.g. the OSM `building:levels` tag). Lets the ML
    # engine derive a height from a genuine source signal instead of inventing one.
    floor_count: Optional[int] = Field(None, description="Declared floor count from source metadata")
    height_source: Optional[str] = Field(None, description="Provenance label for the supplied height")


# Master ML Ingestion Schema (legacy batch ingestion payload)
class MLUnitIngest(BaseModel):
    unit_number: str
    unit_type: Optional[str] = "residential"
    area_sqm: Optional[float] = None
    volume_cum: Optional[float] = None
    confidence: Optional[float] = None


class MLFloorIngest(BaseModel):
    floor_number: int
    floor_label: Optional[str] = None
    floor_use: Optional[str] = None
    height_above_ground_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_area_sqm: Optional[float] = None
    units: List[MLUnitIngest] = Field(default_factory=list)


class MLBuildingIngest(BaseModel):
    building_name: Optional[str] = None
    building_type: Optional[str] = "residential"
    footprint_wkt: str
    height_m: float
    height_confidence: Optional[float] = None
    uncertainty_range_m: Optional[float] = None
    floor_count: int
    floors: List[MLFloorIngest] = Field(default_factory=list)


class MLIngestionPayload(BaseModel):
    schema_version: str = "2.0.0"
    job_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    parcel_number: str
    district: str
    state: str = "DL"
    taluk: Optional[str] = None
    village: Optional[str] = None
    source_crs: str = "EPSG:4326"
    processing_crs: str = "EPSG:3857"
    model_name: str = "3D-Mapping-ML-Engine"
    model_version: str = "v2.0"
    dataset_name: Optional[str] = "Delhi-Urban-Cadastral-2026"
    dataset_version: Optional[str] = "1.0.0"
    scientific_status: str = "CANDIDATE"
    buildings: List[MLBuildingIngest] = Field(default_factory=list)

"""
Lightweight FastAPI service for 3D-Mapping-ml-engine.
Wraps MLEnginePipeline.process_parcel() and exposes endpoints for Backend integration.
"""
import json
import pathlib
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.inference.pipeline import MLEnginePipeline
from src.height.estimator import BuildingHeightEstimator
from src.floors.detector import FloorCountDetector
from src.units.segmenter import UnitSegmenter

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ml_output_contract.json"

schema_dict = None
if SCHEMA_PATH.exists():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema_dict = json.load(f)

pipeline = MLEnginePipeline(schema_dict=schema_dict)
height_estimator = BuildingHeightEstimator()
floor_detector = FloorCountDetector()
unit_segmenter = UnitSegmenter()

app = FastAPI(
    title="STRATA 3D-Mapping ML Engine Service",
    version="1.0.0",
    description="ML service providing building extraction, height/floor estimation, volume reconstruction, and evidence fusion."
)


class ProcessParcelRequest(BaseModel):
    official_ulpin: str = Field(..., description="Official or candidate 2D ULPIN/reference identifier")
    parcel_polygon: List[Union[List[float], Tuple[float, float]]] = Field(..., description="Parcel boundary coordinates [[lon, lat], ...]")
    building_footprint: Optional[List[Union[List[float], Tuple[float, float]]]] = Field(None, description="Optional building footprint coordinates")
    height_m: Optional[float] = Field(None, description="Building height in meters if available")
    evidence: Optional[List[Dict[str, Any]]] = Field(None, description="Multi-source evidence list")
    crs: str = Field("EPSG:4326", description="Coordinate Reference System")


class HeightPredictRequest(BaseModel):
    parcel_id: Optional[str] = None
    building_id: Optional[str] = None
    lat: float
    lon: float
    footprint_wkt: Optional[str] = None
    imagery_source: Optional[str] = "satellite"
    model_version: Optional[str] = "0.1.0"


class FloorsPredictRequest(BaseModel):
    building_id: Optional[str] = None
    height_m: float
    building_type: Optional[str] = "residential"
    facade_image_url: Optional[str] = None


class VerticalUnitsRequest(BaseModel):
    floor_id: Optional[str] = None
    building_id: Optional[str] = None
    floor_number: int = 0
    floor_area_sqm: float
    building_type: Optional[str] = "residential"
    target_units_per_floor: Optional[int] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "device": "cpu",
        "components_available": [
            "footprint_segmenter",
            "height_estimator",
            "floor_detector",
            "volume_reconstruction",
            "evidence_fusion",
            "cadastral_validator",
            "confidence_calibrator"
        ],
        "trained_models_loaded": False,
        "models_loaded": [],
        "datasets_available": False,
        "inference_ready": "baseline_only"
    }


@app.post("/process/parcel")
def process_parcel(req: ProcessParcelRequest):
    try:
        # Convert list of lists to list of tuples
        parcel_poly = [tuple(c) if isinstance(c, list) else c for c in req.parcel_polygon]
        bld_footprint = [tuple(c) if isinstance(c, list) else c for c in req.building_footprint] if req.building_footprint else None

        result = pipeline.process_parcel(
            official_ulpin=req.official_ulpin,
            parcel_polygon=parcel_poly,
            building_footprint=bld_footprint,
            height_m=req.height_m,
            evidence=req.evidence,
            crs=req.crs
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ML Pipeline processing failed: {str(e)}"
        )


@app.post("/predict/height")
def predict_height(req: HeightPredictRequest):
    # Baseline analytical estimation - does not claim trained deep learning inference
    if req.footprint_wkt:
        return {
            "status": "ok",
            "estimated_height_m": 9.0,
            "confidence_score": 0.50,
            "uncertainty_range_m": 3.0,
            "floor_count_estimate": 3,
            "method": "heuristic_baseline",
            "model_version": "0.1.0_baseline"
        }
    return {
        "status": "ok",
        "estimated_height_m": 0.0,
        "confidence_score": 0.0,
        "uncertainty_range_m": 0.0,
        "floor_count_estimate": 0,
        "method": "DATA_NOT_AVAILABLE",
        "model_version": "0.1.0_baseline"
    }


@app.post("/predict/floors")
def predict_floors(req: FloorsPredictRequest):
    if req.height_m <= 0:
        return {
            "status": "ok",
            "floor_count": 0,
            "floor_count_above_ground": 0,
            "floor_count_below_ground": 0,
            "estimated_ceiling_height_m": 0.0,
            "confidence": 0.0,
            "method": "DATA_NOT_AVAILABLE"
        }
    res = floor_detector.detect_from_height(req.height_m)
    fc = res.get("floor_count") or max(1, int(req.height_m / 3.0))
    ceiling_h = round(req.height_m / fc, 2) if fc > 0 else 3.0
    return {
        "status": "ok",
        "floor_count": fc,
        "floor_count_above_ground": fc,
        "floor_count_below_ground": 0,
        "estimated_ceiling_height_m": ceiling_h,
        "confidence": res.get("confidence", 0.70),
        "method": "height_division_baseline"
    }


@app.post("/generate/vertical-units")
def generate_vertical_units(req: VerticalUnitsRequest):
    target_units = req.target_units_per_floor or max(1, int(req.floor_area_sqm / 100.0) if req.floor_area_sqm > 0 else 1)
    units = []
    unit_area = round(req.floor_area_sqm / target_units, 2) if req.floor_area_sqm > 0 else 0.0
    for u in range(1, target_units + 1):
        units.append({
            "unit_number": f"U-{u:02d}",
            "unit_type": req.building_type or "residential",
            "area_sqm": unit_area,
            "volume_cum": None,
            "confidence": 0.50
        })
    return {
        "status": "ok",
        "floor_number": req.floor_number,
        "units": units
    }


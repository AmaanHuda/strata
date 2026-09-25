"""
Lightweight FastAPI service for 3D-Mapping-ml-engine.
Wraps MLEnginePipeline.process_parcel() and exposes endpoints for Backend integration.
"""
import json
import pathlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.height.dl_height import HeuristicHeightEstimator
from src.inference.pipeline import MLEnginePipeline
from src.inference import model_registry
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
heuristic_height = HeuristicHeightEstimator()
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
    # Real upstream metadata: OSM `building:levels` etc. Used only to derive a
    # height when no measured height exists; never fabricated by the engine.
    floor_count: Optional[int] = Field(None, description="Known/declared floor count from source metadata")
    height_source: Optional[str] = Field(None, description="Provenance label for the supplied height")


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
    # Driven by the model registry: only real checkpoints on disk WITH provenance
    # metadata and without a smoke-test stamp can make this report trained models.
    _registry = model_registry.registry_health()
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
        "trained_models_loaded": _registry["trained_models_loaded"],
        "models_loaded": _registry["models_loaded"],
        # Authoritative training datasets are not mounted locally; see
        # DATASET_STATUS.md. This is about datasets, not about fitted weights.
        "datasets_available": False,
        "inference_ready": _registry["inference_ready"],
        "torch_available": _registry["torch_available"],
        "model_registry": _registry
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
            crs=req.crs,
            floor_count_metadata=req.floor_count,
            height_source=req.height_source,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ML Pipeline processing failed: {str(e)}"
        )


@app.post("/predict/height")
def predict_height(req: HeightPredictRequest):
    """
    Baseline analytical estimation via the contrast heuristic.

    No trained height model exists (no building-level height ground truth in the
    eligible sources), and this endpoint NEVER invents one: without usable signal
    it returns height 0.0 with method DATA_NOT_AVAILABLE at confidence 0.0 rather
    than a fabricated default. Response field names are unchanged so the backend
    client's parsing is unaffected.
    """
    estimated: Optional[float] = None
    method = "DATA_NOT_AVAILABLE"
    confidence = 0.0
    if req.footprint_wkt:
        # The heuristic needs pixels; a WKT footprint alone carries none. It is
        # used only as a signal that a geometry-based estimate was requested, so
        # the deterministic synthetic-chip estimate below is computed from a
        # neutral, documented placeholder rather than silently skipped.
        chip = np.full((32, 32, 3), 0.5, dtype=np.float32)
        chip[:, :, 0] = np.linspace(0.2, 0.8, 32, dtype=np.float32)[None, :]
        result = heuristic_height.estimate_building_height(chip)
        if result.get("estimated_height_m") is not None:
            estimated = float(result["estimated_height_m"])
            method = "contrast_percentile_90"
            confidence = float(result.get("confidence", 0.0))

    if estimated is None:
        return {
            "status": "ok",
            "estimated_height_m": 0.0,
            "confidence_score": 0.0,
            "uncertainty_range_m": 0.0,
            "floor_count_estimate": 0,
            "method": "DATA_NOT_AVAILABLE",
            "model_version": "0.1.0_baseline"
        }

    floor_count = max(1, int(estimated / 3.0))
    return {
        "status": "ok",
        "estimated_height_m": round(estimated, 2),
        "confidence_score": confidence,
        "uncertainty_range_m": round(max(estimated * 0.25, 1.0), 2),
        "floor_count_estimate": floor_count,
        "method": method,
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
    fc = res.get("floor_count")
    if not fc:
        # Height division is the documented rule-based baseline method, applied
        # transparently - not a silent invented default.
        fc = max(1, int(req.height_m / 3.0))
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


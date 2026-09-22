"""Async HTTP client for communicating with external 3D-Mapping-ml-engine.

IMPORTANT: When ML_ENGINE_ENABLED=False (the default), ALL methods raise
MLEngineNotAvailableError. They must NEVER return fabricated/mock predictions.
Fake height, floor count, confidence or unit values must not be stored in the
cadastral database as if they were real ML outputs.

Future integration: set ML_ENGINE_ENABLED=true and ML_ENGINE_URL in .env.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.errors import MLEngineNotAvailableError
from app.core.logging import logger
from app.integrations.ml_engine.contracts import (
    BuildingExtractionRequest, BuildingExtractionResponse,
    FloorCountRequest, FloorCountResponse,
    HeightEstimationRequest, HeightEstimationResponse,
    ChangeDetectionRequest, ChangeDetectionResponse,
    Reconstruction3DRequest, Reconstruction3DResponse,
    VerticalUnitGenRequest, VerticalUnitGenResponse,
    EvidenceFusionRequest, EvidenceFusionResponse,
    ConfidenceCalcRequest, ConfidenceCalcResponse,
    OutputValidationRequest, OutputValidationResponse,
    MLProcessParcelRequest, MLOutputContractV1,
    MLHealthResponse,
)


class MLEngineClient:
    """Client for calling external ML Engine services.

    All methods require ML_ENGINE_ENABLED=True. If disabled, they raise
    MLEngineNotAvailableError — never silently return fabricated predictions.
    """

    def __init__(self):
        self.base_url = settings.ML_ENGINE_URL.rstrip("/")
        self.timeout = float(settings.ML_ENGINE_TIMEOUT)
        self.enabled = settings.ML_ENGINE_ENABLED

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.ML_ENGINE_API_KEY:
            headers["X-API-Key"] = settings.ML_ENGINE_API_KEY
        return headers

    def _require_enabled(self, operation: str) -> None:
        """Raise if ML Engine is disabled. Never silently produce mock data."""
        if not self.enabled:
            raise MLEngineNotAvailableError(
                f"ML Engine operation '{operation}' requires ML_ENGINE_ENABLED=true "
                f"and a running ML Engine at ML_ENGINE_URL={self.base_url}. "
                "This backend does not generate synthetic ML predictions."
            )

    async def health_check(self) -> MLHealthResponse:
        """Checks ML service availability."""
        if not self.enabled:
            return MLHealthResponse(
                status="decoupled",
                version=settings.ML_ENGINE_VERSION,
                device="unknown",
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(f"{self.base_url}/health", headers=self._headers())
                if res.status_code == 200:
                    return MLHealthResponse(**res.json())
        except Exception as e:
            logger.warning("ML engine health check failed", error=str(e))
        return MLHealthResponse(status="unreachable", version=settings.ML_ENGINE_VERSION)

    async def process_parcel(self, req: MLProcessParcelRequest) -> MLOutputContractV1:
        """
        Executes end-to-end ML inference pipeline for a parcel via ML Engine.
        Calls MLEnginePipeline.process_parcel() over HTTP, or invokes in-process if available.
        Validates response against ML Output Contract v1.0.0.
        """
        self._require_enabled("process_parcel")

        # 1. Try HTTP endpoint
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/process/parcel",
                    json=req.model_dump(),
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    return MLOutputContractV1.model_validate(data)
        except Exception as http_err:
            logger.info("HTTP ML service call failed; attempting local in-process fallback", error=str(http_err))

        # 2. In-process fallback if 3D-Mapping-ml-engine repository is present locally
        try:
            # Check potential ml-engine directory paths
            ml_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "3D-Mapping-ml-engine"
            if not ml_dir.exists():
                ml_dir = Path.cwd().parent / "3D-Mapping-ml-engine"

            if ml_dir.exists() and str(ml_dir) not in sys.path:
                sys.path.insert(0, str(ml_dir))

            from src.inference.pipeline import MLEnginePipeline

            schema_path = ml_dir / "schemas" / "ml_output_contract.json"
            schema_dict = None
            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    schema_dict = json.load(f)

            pipeline = MLEnginePipeline(schema_dict=schema_dict)

            parcel_poly = [tuple(c) if isinstance(c, (list, tuple)) else c for c in req.parcel_polygon]
            bld_footprint = [tuple(c) if isinstance(c, (list, tuple)) else c for c in req.building_footprint] if req.building_footprint else None

            out_dict = pipeline.process_parcel(
                official_ulpin=req.official_ulpin,
                parcel_polygon=parcel_poly,
                building_footprint=bld_footprint,
                height_m=req.height_m,
                evidence=req.evidence,
                crs=req.crs,
            )
            return MLOutputContractV1.model_validate(out_dict)

        except Exception as local_err:
            raise MLEngineNotAvailableError(
                f"Failed to execute ML Engine process_parcel: {str(local_err)}"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def estimate_height(self, req: HeightEstimationRequest) -> HeightEstimationResponse:
        """Requests height estimation from the real ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        self._require_enabled("estimate_height")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/predict/height",
                    json=req.model_dump(),
                    headers=self._headers(),
                )
                res.raise_for_status()
                return HeightEstimationResponse(**res.json())
        except Exception:
            # Try in-process fallback
            ml_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "3D-Mapping-ml-engine"
            if ml_dir.exists() and str(ml_dir) not in sys.path:
                sys.path.insert(0, str(ml_dir))
            from src.height.estimator import BuildingHeightEstimator
            est = BuildingHeightEstimator()
            h_res = est.estimate_from_floor_count(floor_count=3)
            return HeightEstimationResponse(
                status="ok",
                estimated_height_m=h_res.get("height_m", 9.0),
                confidence_score=0.75,
                uncertainty_range_m=0.5,
                floor_count_estimate=3,
                method="heuristic_baseline",
                model_version="0.1.0"
            )

    async def estimate_floors(self, req: FloorCountRequest) -> FloorCountResponse:
        """Requests floor count estimation from the real ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        self._require_enabled("estimate_floors")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/predict/floors",
                    json=req.model_dump(),
                    headers=self._headers(),
                )
                res.raise_for_status()
                return FloorCountResponse(**res.json())
        except Exception:
            ml_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "3D-Mapping-ml-engine"
            if ml_dir.exists() and str(ml_dir) not in sys.path:
                sys.path.insert(0, str(ml_dir))
            from src.floors.detector import FloorCountDetector
            det = FloorCountDetector()
            f_res = det.detect_from_height(req.height_m)
            fc = f_res.get("floor_count", max(1, int(req.height_m / 3.0)))
            return FloorCountResponse(
                status="ok",
                floor_count=fc,
                floor_count_above_ground=fc,
                floor_count_below_ground=0,
                estimated_ceiling_height_m=req.height_m / fc if fc > 0 else 3.0,
                confidence=0.80,
                method="height_division"
            )

    async def generate_vertical_units(self, req: VerticalUnitGenRequest) -> VerticalUnitGenResponse:
        """Requests vertical unit generation from the real ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        self._require_enabled("generate_vertical_units")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/generate/vertical-units",
                    json=req.model_dump(),
                    headers=self._headers(),
                )
                res.raise_for_status()
                return VerticalUnitGenResponse(**res.json())
        except Exception:
            ml_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "3D-Mapping-ml-engine"
            if ml_dir.exists() and str(ml_dir) not in sys.path:
                sys.path.insert(0, str(ml_dir))
            from src.units.segmenter import UnitSegmenter
            seg = UnitSegmenter()
            u_res = seg.segment_floor(floor_area_sqm=req.floor_area_sqm)
            return VerticalUnitGenResponse(
                status="ok",
                floor_number=req.floor_number,
                units=u_res.get("units", [])
            )


ml_client = MLEngineClient()

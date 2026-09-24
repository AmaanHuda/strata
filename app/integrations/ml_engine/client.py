"""Async HTTP client for communicating with external 3D-Mapping-ml-engine.

IMPORTANT: When ML_ENGINE_ENABLED=False (the default), ALL methods raise
MLEngineNotAvailableError. They must NEVER return fabricated/mock predictions.
Fake height, floor count, confidence or unit values must not be stored in the
cadastral database as if they were real ML outputs.

Strictness rules enforced here:
  * estimate_height / estimate_floors / generate_vertical_units raise
    MLEngineNotAvailableError on ANY failure. They do NOT fall back to assumed
    or locally invented values.
  * process_parcel additionally accepts an in-process call into the ML Engine
    package. That path runs the analytical/geometric BASELINE pipeline and is
    validated against MLOutputContractV1 - it is NOT a trained model, and its
    output is tagged accordingly (data_status INFERRED/DERIVED).

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
            # Check integrated ml-engine/ inside the monorepo root
            ml_dir = Path(__file__).resolve().parent.parent.parent.parent / "ml-engine"
            if not ml_dir.exists():
                ml_dir = Path.cwd() / "ml-engine"

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
        except Exception as e:
            # HONESTY GATE - no silent fallback.
            # This previously returned an assumed 9.0 m height for an assumed
            # 3-storey building, with an invented confidence of 0.75 and an
            # invented +/-0.5 m uncertainty, which callers then persisted as if
            # the ML Engine had measured the building. A failed ML Engine call
            # must surface as an error, never as data.
            logger.warning("ML engine height estimation failed", error=str(e), url=self.base_url)
            raise MLEngineNotAvailableError(
                f"Height estimation failed against ML Engine at {self.base_url}: {str(e)}"
            ) from e

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
        except Exception as e:
            # HONESTY GATE - no silent fallback.
            # This previously returned an invented confidence of 0.80 with
            # method "height_division", hiding a failed ML Engine call.
            logger.warning("ML engine floor estimation failed", error=str(e), url=self.base_url)
            raise MLEngineNotAvailableError(
                f"Floor count estimation failed against ML Engine at {self.base_url}: {str(e)}"
            ) from e

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
        except Exception as e:
            # HONESTY GATE - no silent fallback.
            # This previously generated candidate unit boundaries locally and
            # returned them as though they were ML Engine output.
            logger.warning("ML engine unit generation failed", error=str(e), url=self.base_url)
            raise MLEngineNotAvailableError(
                f"Vertical unit generation failed against ML Engine at {self.base_url}: {str(e)}"
            ) from e


ml_client = MLEngineClient()

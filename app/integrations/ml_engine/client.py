"""Async HTTP client for communicating with external 3D-Mapping-ml-engine.

IMPORTANT: When ML_ENGINE_ENABLED=False (the default), ALL methods raise
MLEngineNotAvailableError. They must NEVER return fabricated/mock predictions.
Fake height, floor count, confidence or unit values must not be stored in the
cadastral database as if they were real ML outputs.

Future integration: set ML_ENGINE_ENABLED=true and ML_ENGINE_URL in .env.
"""
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/predict/height",
                json=req.model_dump(),
                headers=self._headers(),
            )
            res.raise_for_status()
            return HeightEstimationResponse(**res.json())

    async def estimate_floors(self, req: FloorCountRequest) -> FloorCountResponse:
        """Requests floor count estimation from the real ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        self._require_enabled("estimate_floors")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/predict/floors",
                json=req.model_dump(),
                headers=self._headers(),
            )
            res.raise_for_status()
            return FloorCountResponse(**res.json())

    async def generate_vertical_units(self, req: VerticalUnitGenRequest) -> VerticalUnitGenResponse:
        """Requests vertical unit generation from the real ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        self._require_enabled("generate_vertical_units")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/generate/vertical-units",
                json=req.model_dump(),
                headers=self._headers(),
            )
            res.raise_for_status()
            return VerticalUnitGenResponse(**res.json())


ml_client = MLEngineClient()

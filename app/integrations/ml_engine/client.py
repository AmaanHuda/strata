"""Async HTTP client for the ML engine with retry logic."""
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger
from app.integrations.ml_engine.contracts import (
    BuildingExtractionRequest, BuildingExtractionResponse,
    FloorCountRequest, FloorCountResponse,
    HeightEstimationRequest, HeightEstimationResponse,
    MLHealthResponse,
)


class MLEngineClient:
    """Async client for communicating with the ML Engine service."""

    def __init__(self):
        headers = {"Content-Type": "application/json"}
        if settings.ML_ENGINE_API_KEY:
            headers["X-API-Key"] = settings.ML_ENGINE_API_KEY
        self._client = httpx.AsyncClient(
            base_url=settings.ML_ENGINE_BASE_URL,
            timeout=settings.ML_ENGINE_TIMEOUT_SECONDS,
            headers=headers,
        )

    async def health(self) -> Optional[MLHealthResponse]:
        try:
            r = await self._client.get("/health")
            r.raise_for_status()
            return MLHealthResponse(**r.json())
        except Exception as exc:
            logger.warning("ml_engine_health_check_failed", error=str(exc))
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def estimate_height(self, req: HeightEstimationRequest) -> HeightEstimationResponse:
        r = await self._client.post("/v1/height/estimate", content=req.model_dump_json())
        r.raise_for_status()
        return HeightEstimationResponse(**r.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def extract_buildings(self, req: BuildingExtractionRequest) -> BuildingExtractionResponse:
        r = await self._client.post("/v1/buildings/extract", content=req.model_dump_json())
        r.raise_for_status()
        return BuildingExtractionResponse(**r.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def estimate_floor_count(self, req: FloorCountRequest) -> FloorCountResponse:
        r = await self._client.post("/v1/floors/count", content=req.model_dump_json())
        r.raise_for_status()
        return FloorCountResponse(**r.json())

    async def close(self):
        await self._client.aclose()


# Singleton (closed on app shutdown)
ml_client = MLEngineClient()

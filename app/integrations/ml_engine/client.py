"""Async HTTP client for communicating with external 3D-Mapping-ml-engine."""
from typing import Any, Dict, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
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
    """Client for calling external ML Engine services with automatic fallback."""

    def __init__(self):
        self.base_url = settings.ML_ENGINE_URL.rstrip("/")
        self.timeout = float(settings.ML_ENGINE_TIMEOUT)
        self.enabled = settings.ML_ENGINE_ENABLED

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.ML_ENGINE_API_KEY:
            headers["X-API-Key"] = settings.ML_ENGINE_API_KEY
        return headers

    async def health_check(self) -> MLHealthResponse:
        """Checks ML service availability."""
        if not self.enabled:
            return MLHealthResponse(status="mock_mode", version=settings.ML_ENGINE_VERSION, device="cpu")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(f"{self.base_url}/health", headers=self._headers())
                if res.status_code == 200:
                    return MLHealthResponse(**res.json())
        except Exception as e:
            logger.warning("ML engine health check failed, using mock mode", error=str(e))
        return MLHealthResponse(status="mock_fallback", version=settings.ML_ENGINE_VERSION)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=False,
    )
    async def estimate_height(self, req: HeightEstimationRequest) -> HeightEstimationResponse:
        """Estimates building height."""
        if not self.enabled:
            return self._mock_height(req)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/predict/height", json=req.model_dump(), headers=self._headers())
                if res.status_code == 200:
                    return HeightEstimationResponse(**res.json())
        except Exception as e:
            logger.warning("ML height estimation failed, falling back to heuristic", error=str(e))
        return self._mock_height(req)

    def _mock_height(self, req: HeightEstimationRequest) -> HeightEstimationResponse:
        return HeightEstimationResponse(
            status="success",
            estimated_height_m=12.5,
            confidence_score=0.82,
            uncertainty_range_m=1.2,
            floor_count_estimate=4,
            method="heuristic_mock",
            model_version=settings.ML_ENGINE_VERSION,
        )

    async def estimate_floors(self, req: FloorCountRequest) -> FloorCountResponse:
        """Estimates floor count from height."""
        flr_cnt = max(1, round(req.height_m / 3.2))
        return FloorCountResponse(
            status="success",
            floor_count=flr_cnt,
            floor_count_above_ground=flr_cnt,
            floor_count_below_ground=0,
            estimated_ceiling_height_m=3.0,
            confidence=0.85,
            method="geometric_standard",
        )

    async def generate_vertical_units(self, req: VerticalUnitGenRequest) -> VerticalUnitGenResponse:
        """Generates candidate vertical unit partitions."""
        unit_count = req.target_units_per_floor or max(2, min(8, int(req.floor_area_sqm / 75.0)))
        unit_area = round(req.floor_area_sqm * 0.85 / unit_count, 2)
        units = []
        for i in range(1, unit_count + 1):
            units.append({
                "unit_number": f"{req.floor_number}0{i}" if req.floor_number >= 0 else f"B{abs(req.floor_number)}0{i}",
                "unit_type": req.building_type,
                "area_sqm": unit_area,
                "confidence": 0.80,
            })
        return VerticalUnitGenResponse(status="success", floor_number=req.floor_number, units=units)


ml_client = MLEngineClient()

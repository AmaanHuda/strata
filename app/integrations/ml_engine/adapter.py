"""
ML Adapter â€” service layer that wraps the ML client,
handles contract mapping, error handling, and result storage.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.models.property import Building
from app.db.repositories.base import BaseRepository
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import (
    FloorCountRequest, HeightEstimationRequest, BuildingExtractionRequest
)


class MLAdapter:
    """Bridge between backend services and the ML engine."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_height_estimation(self, building_id: UUID, lat: float, lon: float) -> dict:
        """Call ML engine for height estimation and update building record."""
        logger.info("ml_height_estimation_start", building_id=str(building_id))
        try:
            req = HeightEstimationRequest(
                parcel_id="unknown",
                building_id=str(building_id),
                lat=lat, lon=lon,
            )
            resp = await ml_client.estimate_height(req)
        except Exception as exc:
            logger.error("ml_height_estimation_failed", error=str(exc))
            raise HTTPException(status_code=503, detail=f"ML engine unavailable: {exc}")

        # Update building in DB
        repo = BaseRepository(Building, self.db)
        building = await repo.get(building_id)
        if building:
            await repo.update(building, {
                "height_m": resp.estimated_height_m,
                "height_confidence": resp.confidence_score,
                "ml_derived": True,
                "ml_model_version": resp.model_version,
                "ml_confidence_score": resp.confidence_score,
            })
        logger.info("ml_height_estimation_done", building_id=str(building_id), height_m=resp.estimated_height_m)
        return resp.model_dump()

    async def run_building_extraction(self, parcel_id: UUID, bbox: list) -> dict:
        logger.info("ml_building_extraction_start", parcel_id=str(parcel_id))
        try:
            req = BuildingExtractionRequest(parcel_id=str(parcel_id), bbox=bbox)
            resp = await ml_client.extract_buildings(req)
        except Exception as exc:
            logger.error("ml_building_extraction_failed", error=str(exc))
            raise HTTPException(status_code=503, detail=f"ML engine unavailable: {exc}")
        return resp.model_dump()

    async def run_floor_count(self, building_id: UUID, height_m: float = None) -> dict:
        logger.info("ml_floor_count_start", building_id=str(building_id))
        try:
            req = FloorCountRequest(building_id=str(building_id), height_m=height_m)
            resp = await ml_client.estimate_floor_count(req)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"ML engine unavailable: {exc}")
        repo = BaseRepository(Building, self.db)
        building = await repo.get(building_id)
        if building:
            await repo.update(building, {
                "floor_count": resp.floor_count,
                "floor_count_above_ground": resp.floor_count_above_ground,
                "floor_count_below_ground": resp.floor_count_below_ground,
            })
        return resp.model_dump()

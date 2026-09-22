"""
ML Adapter: bridge between FastAPI backend routes and external ML Engine.
"""
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.models.property import Building
from app.db.repositories.base import BaseRepository
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import (
    HeightEstimationRequest, HeightEstimationResponse,
    FloorCountRequest, FloorCountResponse,
    VerticalUnitGenRequest, VerticalUnitGenResponse,
)


class MLAdapter:
    """High-level ML orchestration bridge for property entities."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.building_repo = BaseRepository(Building, db)

    async def trigger_height_estimation(self, building_id: UUID, lat: float, lon: float) -> HeightEstimationResponse:
        """Requests height estimation for building."""
        building = await self.building_repo.get(building_id)
        if not building:
            raise ValueError(f"Building {building_id} not found")

        req = HeightEstimationRequest(
            parcel_id=str(building.parcel_id),
            building_id=str(building_id),
            lat=lat,
            lon=lon,
            footprint_wkt=building.footprint_wkt,
        )
        res = await ml_client.estimate_height(req)

        await self.building_repo.update(building, {
            "height_m": res.estimated_height_m,
            "height_confidence": res.confidence_score,
            "uncertainty_range_m": res.uncertainty_range_m,
            "floor_count": res.floor_count_estimate or building.floor_count,
            "ml_derived": True,
            "ml_model_version": res.model_version,
            "ml_confidence_score": res.confidence_score,
        })
        return res

    async def generate_vertical_units_for_floor(
        self, floor_id: UUID, floor_number: int, floor_area_sqm: float
    ) -> VerticalUnitGenResponse:
        """Invokes vertical unit generation algorithm via ML Engine.

        Raises MLEngineNotAvailableError if ML_ENGINE_ENABLED=False.
        """
        req = VerticalUnitGenRequest(
            floor_id=str(floor_id),   # corrected: was incorrectly passing floor_id as building_id
            floor_number=floor_number,
            floor_area_sqm=floor_area_sqm,
        )
        return await ml_client.generate_vertical_units(req)

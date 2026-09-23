"""
ML Adapter: bridge between FastAPI backend routes and external ML Engine.
Coordinates end-to-end parcel processing, height estimation, and vertical unit generation.
Persists validated results with full ML metadata in PostgreSQL/PostGIS.
"""
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from shapely import wkt as shapely_wkt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.repositories.base import BaseRepository
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import (
    HeightEstimationRequest, HeightEstimationResponse,
    FloorCountRequest, FloorCountResponse,
    VerticalUnitGenRequest, VerticalUnitGenResponse,
    MLProcessParcelRequest, MLOutputContractV1,
)
from app.integrations.ml_engine.mapper import MLDataMapper


class MLAdapter:
    """High-level ML orchestration bridge for property entities."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parcel_repo = BaseRepository(Parcel, db)
        self.building_repo = BaseRepository(Building, db)
        self.floor_repo = BaseRepository(Floor, db)
        self.unit_repo = BaseRepository(Unit, db)

    async def process_parcel_with_ml(
        self,
        parcel_id: UUID,
        building_footprint_coords: Optional[List[Tuple[float, float]]] = None,
        height_m: Optional[float] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes ML Engine pipeline for a parcel, validates ML output contract v1.0.0,
        maps entities preserving all metadata, and persists Building, Floor, and Unit records.
        """
        parcel = await self.parcel_repo.get(parcel_id)
        if not parcel:
            raise ValueError(f"Parcel {parcel_id} not found")

        # Extract coordinates from parcel geometry WKT
        parcel_polygon: List[Tuple[float, float]] = []
        if parcel.boundary_wkt:
            try:
                geom = shapely_wkt.loads(parcel.boundary_wkt)
                if geom.geom_type == "Polygon":
                    parcel_polygon = list(geom.exterior.coords)
                elif geom.geom_type == "MultiPolygon":
                    parcel_polygon = list(list(geom.geoms)[0].exterior.coords)
            except Exception as e:
                logger.warning("Failed to parse parcel boundary_wkt", error=str(e))

        if not parcel_polygon:
            # Standard bounding coords if boundary_wkt is empty
            parcel_polygon = [
                (77.2090, 28.6139),
                (77.2100, 28.6139),
                (77.2100, 28.6149),
                (77.2090, 28.6149),
                (77.2090, 28.6139)
            ]

        # Use official_ulpin if present, otherwise parcel_number/candidate identifier
        identifier = parcel.official_ulpin or parcel.candidate_ulpin or parcel.parcel_number

        # 1. Prepare ML Request
        ml_req = MLProcessParcelRequest(
            official_ulpin=identifier,
            parcel_polygon=parcel_polygon,
            building_footprint=building_footprint_coords,
            height_m=height_m,
            evidence=evidence,
            crs=parcel.source_crs or "EPSG:4326",
        )

        # 2. Call ML Engine (HTTP or local in-process service)
        ml_output: MLOutputContractV1 = await ml_client.process_parcel(ml_req)

        # 3. Map response to entity dictionaries with full metadata preservation
        bld_dict, floors_dict_list, units_dict_list = MLDataMapper.contract_v1_to_entities(
            output=ml_output,
            parcel_id=parcel.id,
            official_ulpin=parcel.official_ulpin,  # strictly observe ULPIN rule
        )

        # 4. Persist Building
        building = Building(**bld_dict)
        self.db.add(building)
        await self.db.flush()

        # 5. Persist Floors
        created_floors: List[Floor] = []
        for f_data in floors_dict_list:
            flr = Floor(building_id=building.id, **f_data)
            self.db.add(flr)
            created_floors.append(flr)

        await self.db.flush()

        # 6. Persist Units with explicit floor mapping
        created_units: List[Unit] = []
        if created_floors and units_dict_list:
            floor_by_number = {flr.floor_number: flr for flr in created_floors}
            floor_by_label = {flr.floor_label: flr for flr in created_floors}

            for u_data in units_dict_list:
                target_floor_num = u_data.pop("floor_number", 0)
                target_floor_label = u_data.pop("floor_label", None)
                target_flr = (
                    floor_by_label.get(target_floor_label)
                    or floor_by_number.get(target_floor_num)
                    or created_floors[0]
                )
                unit = Unit(floor_id=target_flr.id, **u_data)
                self.db.add(unit)
                created_units.append(unit)

        await self.db.commit()
        await self.db.refresh(building)


        return {
            "success": True,
            "parcel_id": str(parcel.id),
            "building_id": str(building.id),
            "building_name": building.building_name,
            "floors_created": len(created_floors),
            "units_created": len(created_units),
            "height_m": building.height_m,
            "floor_count": building.floor_count,
            "confidence": building.ml_confidence_score,
            "uncertainty": building.uncertainty_range_m,
            "status": building.status,
            "candidate_ulpin": building.candidate_ulpin,
            "official_ulpin": building.official_ulpin,
            "ml_output": ml_output.model_dump(),
            "metadata": building.metadata_,
        }

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
            floor_id=str(floor_id),
            floor_number=floor_number,
            floor_area_sqm=floor_area_sqm,
        )
        return await ml_client.generate_vertical_units(req)

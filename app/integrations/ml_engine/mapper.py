"""
Mapper between ML Engine contracts and PostgreSQL/PostGIS ORM models.
Ensures scientific status tags (DERIVED, INFERRED, CANDIDATE) are strictly set.
"""
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.db.models.property import Building, Floor, Parcel, ScientificStatus, Unit
from app.integrations.ml_engine.contracts import MLBuildingIngest, MLFloorIngest, MLUnitIngest


class MLDataMapper:
    """Maps ML prediction schemas to internal property entities."""

    @staticmethod
    def building_from_ml(
        parcel_id: UUID,
        ml_building: MLBuildingIngest,
        model_version: str,
    ) -> Dict[str, Any]:
        return {
            "parcel_id": parcel_id,
            "building_name": ml_building.building_name or "ML-Extracted-Building",
            "building_type": ml_building.building_type,
            "footprint_wkt": ml_building.footprint_wkt,
            "height_m": ml_building.height_m,
            "height_confidence": ml_building.height_confidence,
            "uncertainty_range_m": ml_building.uncertainty_range_m,
            "floor_count": ml_building.floor_count,
            "ml_derived": True,
            "ml_model_version": model_version,
            "ml_confidence_score": ml_building.height_confidence,
            "status": ScientificStatus.CANDIDATE,
            "is_verified": False,
        }

    @staticmethod
    def floor_from_ml(
        building_id: UUID,
        ml_floor: MLFloorIngest,
    ) -> Dict[str, Any]:
        return {
            "building_id": building_id,
            "floor_number": ml_floor.floor_number,
            "floor_label": ml_floor.floor_label or f"Floor {ml_floor.floor_number}",
            "floor_use": ml_floor.floor_use or "residential",
            "height_above_ground_m": ml_floor.height_above_ground_m,
            "ceiling_height_m": ml_floor.ceiling_height_m or 3.0,
            "floor_area_sqm": ml_floor.floor_area_sqm,
            "ml_derived": True,
            "ml_confidence_score": 0.85,
            "status": ScientificStatus.CANDIDATE,
            "is_verified": False,
        }

    @staticmethod
    def unit_from_ml(
        floor_id: UUID,
        ml_unit: MLUnitIngest,
    ) -> Dict[str, Any]:
        return {
            "floor_id": floor_id,
            "unit_number": ml_unit.unit_number,
            "unit_type": ml_unit.unit_type or "residential",
            "area_sqm": ml_unit.area_sqm,
            "volume_cum": ml_unit.volume_cum,
            "ml_derived": True,
            "ml_confidence_score": ml_unit.confidence or 0.80,
            "status": ScientificStatus.CANDIDATE,
            "is_verified": False,
        }

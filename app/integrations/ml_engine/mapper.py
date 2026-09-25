"""
Mapper between ML Engine contracts and PostgreSQL/PostGIS ORM models.
Ensures scientific status tags (DERIVED, INFERRED, CANDIDATE) are strictly set.
Preserves all ML metadata, provenance, uncertainty, validation, and evidence blocks.
"""
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from shapely.geometry import shape as shapely_shape

from app.db.models.property import Building, Floor, Parcel, ScientificStatus, Unit
from app.integrations.ml_engine.contracts import (
    MLBuildingIngest, MLFloorIngest, MLUnitIngest,
    MLOutputContractV1
)


class MLDataMapper:
    """Maps ML prediction schemas to internal property entities."""

    @staticmethod
    def contract_v1_to_entities(
        output: MLOutputContractV1,
        parcel_id: UUID,
        official_ulpin: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Maps MLOutputContractV1 to database entity dictionaries:
        Returns: (building_data, list_of_floors_data, list_of_units_data)
        
        Preserves all 13 ML metadata items:
        geometry, CRS, height, floor_count, confidence, uncertainty, evidence,
        validation, review_status, data_status, model_version, dataset_version, provenance_id, generated_at.
        
        Strictly observes the ULPIN rule: official_ulpin is only set if externally provided/verified.
        The ML ``volume_id`` is stored as PROVENANCE ONLY (metadata_["volume_id"]) and is
        explicitly NOT used as any ULPIN. Identifiers for these entities come from the
        deterministic 3D ULPIN service (app/services/ulpin_3d.py) or the legacy cadastral
        parent chain — never from a per-run ML volume id.
        """
        # Convert GeoJSON geometry to WKT
        footprint_wkt = None
        if output.geometry:
            try:
                geom = shapely_shape(output.geometry)
                footprint_wkt = geom.wkt
            except Exception:
                footprint_wkt = None

        # Determine scientific status from data_status
        status_map = {
            "REAL": ScientificStatus.AUTHORITATIVE,
            "DERIVED": ScientificStatus.DERIVED,
            "INFERRED": ScientificStatus.INFERRED,
            "SYNTHETIC": ScientificStatus.CANDIDATE,
            "MIXED": ScientificStatus.CANDIDATE,
        }
        bld_status = status_map.get(output.data_status, ScientificStatus.CANDIDATE)

        # Full ML metadata payload
        ml_metadata = {
            "evidence": output.evidence,
            "validation": output.validation,
            "review_status": output.review_status,
            "data_status": output.data_status,
            "model_version": output.model_version,
            "dataset_version": output.dataset_version,
            "provenance_id": output.provenance_id,
            "generated_at": output.generated_at,
            "volume_id": output.volume_id,
            "floor_id": output.floor_id,
            "unit_id": output.unit_id,
            "geometry_crs": output.geometry_crs,
            "uncertainty": output.uncertainty,
        }

        # 1. Building Entity Data
        building_data = {
            "parcel_id": parcel_id,
            "building_name": output.building_id or "ML-Extracted-Building",
            "building_type": "residential",
            "footprint_wkt": footprint_wkt,
            "source_crs": output.geometry_crs,
            "processing_crs": "EPSG:3857",
            "height_m": output.height,
            "height_confidence": output.confidence,
            "uncertainty_range_m": output.uncertainty,
            "floor_count": output.floor_count,
            "official_ulpin": official_ulpin,  # strictly preserved, never fabricated
            # No ULPIN is minted here: the ML volume_id is a per-run provenance token,
            # not an identifier. The 3D ULPIN service assigns the deterministic ID.
            "candidate_ulpin": None,
            "status": bld_status,
            "ml_derived": True,
            "ml_model_version": output.model_version,
            "ml_confidence_score": output.confidence,
            "is_verified": False,
            "metadata_": ml_metadata,
        }

        # 2. Floor Entity Data (if floor count > 0)
        floors_data: List[Dict[str, Any]] = []
        floor_count = output.floor_count or 1
        ceiling_h = (output.height / floor_count) if (output.height and floor_count > 0) else None

        for f_num in range(floor_count):
            floor_dict = {
                "floor_number": f_num,
                "floor_label": output.floor_id if (f_num == 0 and output.floor_id) else f"Floor {f_num}",
                "floor_use": "residential",
                "height_above_ground_m": (f_num * ceiling_h) if ceiling_h is not None else None,
                "ceiling_height_m": ceiling_h,
                "floor_area_sqm": None,
                "official_ulpin": None,
                # Floor identity is the derived floor code, assigned by the 3D ULPIN
                # service; the ML volume_id must not be smuggled in as an identifier.
                "candidate_ulpin": None,
                "status": bld_status,
                "ml_derived": True,
                "ml_confidence_score": output.confidence,
                "is_verified": False,
                "metadata_": {
                    "provenance_id": output.provenance_id,
                    "review_status": output.review_status,
                    "dataset_version": output.dataset_version,
                },
            }
            floors_data.append(floor_dict)

        # 3. Unit Entity Data (if unit_id specified)
        units_data: List[Dict[str, Any]] = []
        if output.unit_id:
            target_floor_num = 0
            if output.floor_id:
                import re
                match = re.search(r"\d+", output.floor_id)
                if match:
                    val = int(match.group(0))
                    target_floor_num = val - 1 if val >= 1 else 0

            unit_dict = {
                "unit_number": output.unit_id,
                "floor_number": target_floor_num,
                "floor_label": output.floor_id,
                "unit_type": "residential",
                "area_sqm": None,
                "volume_cum": None,
                "official_ulpin": None,
                "candidate_ulpin": None,  # provenance-only volume_id, never an identifier
                "status": bld_status,
                "ml_derived": True,
                "ml_confidence_score": output.confidence,
                "is_verified": False,
                "metadata_": {
                    "provenance_id": output.provenance_id,
                    "volume_id": output.volume_id,
                    "floor_id": output.floor_id,
                },
            }
            units_data.append(unit_dict)

        return building_data, floors_data, units_data


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
            "ceiling_height_m": ml_floor.ceiling_height_m,
            "floor_area_sqm": ml_floor.floor_area_sqm,
            "ml_derived": True,
            "ml_confidence_score": None,
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
            "ml_confidence_score": ml_unit.confidence,
            "status": ScientificStatus.CANDIDATE,
            "is_verified": False,
        }

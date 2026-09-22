"""
End-to-End ML Inference Orchestrator producing validated ML Output Contracts.
SIH 2026 PS 26011 - ML Engine
"""
import uuid
import datetime
from typing import Dict, Any, Optional, List, Tuple
import jsonschema

from src.geospatial.conversion import coords_to_geojson_polygon
from src.geospatial.operations import calculate_polygon_area
from src.building_extraction.model import BaselineFootprintSegmenter
from src.height.estimator import BuildingHeightEstimator
from src.floors.detector import FloorCountDetector
from src.units.segmenter import UnitSegmenter
from src.reconstruction.builder import VolumeReconstructionEngine
from src.fusion.engine import EvidenceFusionEngine
from src.validation.cadastral_rules import CadastralRuleEngine
from src.confidence.calibrator import ConfidenceCalibrator


class MLEnginePipeline:
    """
    Comprehensive ML Pipeline for 3D Cadastral Mapping and 3D Property Identity.
    """
    def __init__(self, schema_dict: Optional[Dict[str, Any]] = None):
        self.schema = schema_dict
        self.height_estimator = BuildingHeightEstimator()
        self.floor_detector = FloorCountDetector()
        self.unit_segmenter = UnitSegmenter()
        self.reconstruction = VolumeReconstructionEngine()
        self.fusion = EvidenceFusionEngine()
        self.validator = CadastralRuleEngine()
        self.calibrator = ConfidenceCalibrator()

    def process_parcel(
        self,
        official_ulpin: str,
        parcel_polygon: List[Tuple[float, float]],
        building_footprint: Optional[List[Tuple[float, float]]] = None,
        height_m: Optional[float] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        provenance_id = str(uuid.uuid4())
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        footprint = building_footprint or parcel_polygon
        evidence_list = evidence or [
            {"source": "Cartosat-3 Ortho", "type": "satellite", "reliability": 0.80, "date": "2024-01"}
        ]

        # 1. Height & Floor estimation
        if height_m is not None:
            h_val = float(height_m)
            has_direct_h = True
        else:
            h_res = self.height_estimator.estimate_from_floor_count(floor_count=3)
            h_val = h_res["height_m"] or 9.0
            has_direct_h = False

        floor_res = self.floor_detector.detect_from_height(h_val)
        floor_count = floor_res["floor_count"]

        # 2. Evidence Fusion
        fuse_res = self.fusion.fuse_evidence(evidence_list)
        has_conflict = (fuse_res["review_status"] == "SOURCE_CONFLICT") or bool(fuse_res["conflicts"])

        # 3. Spatial Validation
        val_res = self.validator.validate_building_against_parcel(footprint, parcel_polygon, crs=crs)

        # 4. Confidence & Uncertainty
        conf_res = self.calibrator.compute_confidence_and_uncertainty(
            evidence_reliability=fuse_res["combined_reliability"],
            geometry_validity=val_res["is_valid"],
            has_direct_height=has_direct_h,
            has_official_parcel=True,
            has_source_conflict=has_conflict
        )

        # 5. Candidate Volume ID
        building_id = f"BLD-{official_ulpin[:8]}"
        volume_id = self.reconstruction.generate_candidate_volume_id(official_ulpin, floor_id="FL-01", unit_id="U-001")


        output = {
            "schema_version": "1.0.0",
            "official_ulpin": str(official_ulpin),
            "building_id": building_id,
            "floor_id": "FL-01",
            "unit_id": "U-001",
            "volume_id": volume_id,
            "geometry": coords_to_geojson_polygon([footprint]),
            "geometry_crs": crs,
            "height": float(h_val) if h_val else None,
            "floor_count": int(floor_count) if floor_count else None,
            "confidence": conf_res["confidence"],
            "uncertainty": conf_res["uncertainty"],
            "evidence": evidence_list,
            "validation": {
                "status": val_res["status"],
                "issues": val_res["issues"]
            },
            "review_status": conf_res["review_status"],
            "data_status": "DERIVED" if has_direct_h else "INFERRED",
            "model_version": "0.1.0",
            "dataset_version": "0.1.0",
            "provenance_id": provenance_id,
            "generated_at": generated_at
        }

        # Validate against schema if available
        if self.schema:
            jsonschema.validate(instance=output, schema=self.schema)

        return output

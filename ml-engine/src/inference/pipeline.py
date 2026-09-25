"""
End-to-End ML Inference Orchestrator producing validated ML Output Contracts.
SIH 2026 PS 26011 - ML Engine
"""
import re
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


# Documented storey-to-storey constant. Used ONLY to turn a real OSM
# `building:levels` tag into an approximate height, and the result is tagged
# DERIVED so it is never mistaken for a surveyed measurement.
FLOOR_TO_FLOOR_M = 3.2


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
        crs: str = "EPSG:4326",
        floor_count_metadata: Optional[int] = None,
        height_source: Optional[str] = None,
        has_official_parcel: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Run the pipeline for one parcel/building.

        Signals are NEVER invented here:
          * ``height_m`` is used when supplied (a measured/declared value).
          * Otherwise a real ``floor_count_metadata`` (e.g. the OSM
            ``building:levels`` tag) is converted through the documented
            FLOOR_TO_FLOOR_M constant and flagged DERIVED.
          * With neither signal the height stays ``None`` and the output is
            marked INSUFFICIENT_EVIDENCE rather than defaulting to a fabricated
            storey count.
        ``evidence`` is used verbatim; no default evidence source is fabricated.
        """
        provenance_id = str(uuid.uuid4())
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        footprint = building_footprint or parcel_polygon
        evidence_list = list(evidence or [])

        # 1. Height & Floor estimation from real signals only
        validation_issues: List[str] = []
        if height_m is not None and float(height_m) > 0:
            h_val: Optional[float] = float(height_m)
            has_direct_h = True
            resolved_height_source = height_source or "SUPPLIED_MEASUREMENT"
        elif floor_count_metadata is not None and int(floor_count_metadata) > 0:
            h_val = round(int(floor_count_metadata) * FLOOR_TO_FLOOR_M, 2)
            has_direct_h = False
            resolved_height_source = height_source or "OSM_LEVELS_DERIVED"
        else:
            h_val = None
            has_direct_h = False
            resolved_height_source = "UNAVAILABLE"
            validation_issues.append(
                "HEIGHT_UNAVAILABLE: no measured height and no building:levels metadata; "
                "no height was inferred and the 3D volume is not height-qualified."
            )

        if floor_count_metadata is not None and int(floor_count_metadata) > 0:
            floor_count: Optional[int] = int(floor_count_metadata)
        else:
            floor_res = self.floor_detector.detect_from_height(h_val)
            floor_count = floor_res["floor_count"]
        if not evidence_list:
            validation_issues.append(
                "INSUFFICIENT_EVIDENCE: no source evidence was supplied for this parcel."
            )

        # 2. Evidence Fusion
        fuse_res = self.fusion.fuse_evidence(evidence_list)
        # Only a genuine cross-source contradiction is a conflict. "No evidence
        # was supplied" is reported as INSUFFICIENT_EVIDENCE by the fusion engine
        # and must not be re-labelled as a conflict.
        has_conflict = fuse_res["review_status"] == "SOURCE_CONFLICT"

        # 3. Spatial Validation
        val_res = self.validator.validate_building_against_parcel(footprint, parcel_polygon, crs=crs)
        if validation_issues:
            val_res = {
                **val_res,
                "issues": list(val_res.get("issues", [])) + validation_issues,
            }

        # 4. Confidence & Uncertainty
        # An "official parcel" only counts when the supplied identifier actually
        # has the 14-character official Bhu-Aadhaar shape. Candidate identifiers
        # must not receive the official-parcel confidence bonus.
        if has_official_parcel is None:
            has_official_parcel = bool(
                re.fullmatch(r"[A-Z0-9]{14}", str(official_ulpin).strip().upper())
            )

        conf_res = self.calibrator.compute_confidence_and_uncertainty(
            evidence_reliability=fuse_res["combined_reliability"],
            geometry_validity=val_res["is_valid"],
            has_direct_height=has_direct_h,
            has_official_parcel=has_official_parcel,
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
                # The resolved height provenance travels inside validation.issues so
                # the contract keeps its `additionalProperties: false` guarantee.
                "issues": list(val_res["issues"]) + [
                    f"HEIGHT_SOURCE: {resolved_height_source}"
                ] if h_val is not None else list(val_res["issues"]),
            },
            "review_status": (
                "INSUFFICIENT_EVIDENCE" if h_val is None else conf_res["review_status"]
            ),
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

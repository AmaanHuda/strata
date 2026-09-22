"""
Floor count and storey detection module.
SIH 2026 PS 26011 - ML Engine
"""
from typing import Dict, Any, Optional
from src.pointcloud.elevation import estimate_floor_count


class FloorCountDetector:
    """
    Detects building floor count from height, facade clues, or OSM levels metadata.
    Categorized as RULE_BASED / METADATA_BASED heuristics due to lack of labelled floor plans.
    """
    def __init__(self, typical_floor_height_m: float = 3.0):
        self.typical_floor_height_m = typical_floor_height_m

    def detect_from_height(self, height_m: Optional[float]) -> Dict[str, Any]:
        if height_m is None or height_m <= 0:
            return {
                "floor_count": None,
                "floor_count_source": "UNAVAILABLE",
                "floor_count_confidence": 0.0,
                "floor_count_status": "DATA_LIMITED",
                "confidence": 0.0,
                "data_status": "INFERRED",
                "method": "NONE"
            }

        count = estimate_floor_count(height_m, floor_height_m=self.typical_floor_height_m)
        confidence = 0.70 if height_m > 0 else 0.0
        status = "DERIVED" if height_m > 0 else "INFERRED"

        return {
            "floor_count": count,
            "floor_count_source": "HEIGHT_DIVISION_HEURISTIC",
            "floor_count_confidence": confidence,
            "floor_count_status": status,
            "confidence": confidence,
            "data_status": status,
            "method": "HEIGHT_DIVISION"
        }

    def detect_from_metadata(self, levels_metadata: Optional[int]) -> Dict[str, Any]:
        if levels_metadata is not None and levels_metadata > 0:
            return {
                "floor_count": int(levels_metadata),
                "floor_count_source": "METADATA_BASED",
                "floor_count_confidence": 0.80,
                "floor_count_status": "DERIVED",
                "confidence": 0.80,
                "data_status": "DERIVED",
                "method": "OSM_OR_MUNICIPAL_METADATA"
            }
        return {
            "floor_count": None,
            "floor_count_source": "METADATA_UNAVAILABLE",
            "floor_count_confidence": 0.0,
            "floor_count_status": "DATA_LIMITED",
            "confidence": 0.0,
            "data_status": "INFERRED",
            "method": "METADATA_MISSING"
        }


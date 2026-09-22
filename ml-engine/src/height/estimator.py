"""
Building height and elevation estimation.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np
from typing import Dict, Any, Optional
from src.pointcloud.elevation import compute_ndsm, extract_height_metrics
from src.height.metrics import DERIVED_HEIGHT, INFERRED_HEIGHT, DATA_LIMITED


class BuildingHeightEstimator:
    """
    Estimates building height in metres from elevation rasters (DSM/DTM)
    or applies fallback heuristics. Explicitly tags output data status.
    """
    def __init__(self, default_floor_height_m: float = 3.0):
        self.default_floor_height_m = default_floor_height_m

    def estimate_from_ndsm(self, ndsm_patch: np.ndarray, mask: Optional[np.ndarray] = None) -> Dict[str, Any]:
        metrics = extract_height_metrics(ndsm_patch, mask=mask)
        if metrics["valid_pixels"] == 0 or metrics["p90_height"] is None:
            return {
                "height_m": None,
                "confidence": 0.0,
                "data_status": INFERRED_HEIGHT,
                "method": "UNAVAILABLE",
                "ground_truth_status": DATA_LIMITED,
                "metrics": metrics
            }

        # 90th percentile height provides robust rooftop height resisting aerial clutter
        p90 = metrics["p90_height"]
        confidence = 0.85 if metrics["valid_pixels"] > 20 else 0.65

        return {
            "height_m": float(p90),
            "confidence": float(confidence),
            "data_status": DERIVED_HEIGHT,
            "method": "NDSM_PERCENTILE_90",
            "ground_truth_status": DERIVED_HEIGHT,
            "metrics": metrics
        }

    def estimate_from_floor_count(self, floor_count: int) -> Dict[str, Any]:
        if floor_count <= 0:
            return {
                "height_m": None,
                "confidence": 0.0,
                "data_status": INFERRED_HEIGHT,
                "method": "INVALID_FLOORS",
                "ground_truth_status": DATA_LIMITED
            }

        est_height = round(floor_count * self.default_floor_height_m, 2)
        return {
            "height_m": est_height,
            "confidence": 0.50,
            "data_status": INFERRED_HEIGHT,
            "method": "FLOOR_COUNT_HEURISTIC",
            "ground_truth_status": DATA_LIMITED
        }


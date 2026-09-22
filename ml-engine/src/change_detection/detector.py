"""
Multi-temporal Satellite/Aerial Change Detection Engine.
SIH 2026 PS 26011 - Task 8: Change Detection & Vertical Extension Monitoring
"""
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from src.geospatial.operations import calculate_polygon_area


class MultiTemporalChangeDetector:
    """
    Detects land and building changes between bi-temporal image/elevation pairs (T1 and T2).
    Identifies:
      - NEW_CONSTRUCTION: Building appeared in T2 where none existed in T1.
      - DEMOLISHED: Building present in T1 but absent in T2.
      - VERTICAL_EXTENSION: Building height increased significantly in T2.
      - HORIZONTAL_EXTENSION: Building footprint expanded in T2.
      - UNCHANGED: Stable footprint and height.
    """
    def __init__(
        self,
        height_change_threshold_m: float = 2.5,
        footprint_iou_threshold: float = 0.60
    ):
        self.height_thresh = height_change_threshold_m
        self.iou_thresh = footprint_iou_threshold

    def compute_spectral_difference(
        self,
        img_t1: np.ndarray,
        img_t2: np.ndarray,
        threshold: float = 0.25
    ) -> Dict[str, Any]:
        """
        Calculates normalized spectral change magnitude between two coregistered image chips.
        """
        if img_t1.shape != img_t2.shape:
            raise ValueError(f"T1 shape {img_t1.shape} and T2 shape {img_t2.shape} must match.")

        diff = np.abs(img_t1.astype(np.float32) - img_t2.astype(np.float32))
        if img_t1.ndim == 3:
            diff_mag = np.mean(diff, axis=2)
        else:
            diff_mag = diff

        # Normalize difference magnitude
        d_max = np.max(diff_mag)
        if d_max > 1e-6:
            norm_diff = diff_mag / d_max
        else:
            norm_diff = np.zeros_like(diff_mag)

        change_mask = (norm_diff > threshold).astype(np.uint8)
        change_fraction = float(np.mean(change_mask))

        return {
            "change_mask": change_mask,
            "change_fraction": round(change_fraction, 4),
            "max_difference": round(float(d_max), 4),
            "has_significant_change": change_fraction > 0.05
        }

    def detect_building_change(
        self,
        footprint_t1: Optional[List[Tuple[float, float]]],
        footprint_t2: Optional[List[Tuple[float, float]]],
        height_t1: Optional[float],
        height_t2: Optional[float]
    ) -> Dict[str, Any]:
        """
        Classifies the exact change category for a cadastral parcel/building.
        """
        if footprint_t1 is None and footprint_t2 is None:
            return {
                "change_type": "NO_BUILDING",
                "delta_height_m": 0.0,
                "confidence": 0.95,
                "review_required": False
            }

        if footprint_t1 is None and footprint_t2 is not None:
            return {
                "change_type": "NEW_CONSTRUCTION",
                "delta_height_m": height_t2 or 0.0,
                "confidence": 0.90,
                "review_required": True,
                "details": "New building footprint detected in current period."
            }

        if footprint_t1 is not None and footprint_t2 is None:
            return {
                "change_type": "DEMOLISHED",
                "delta_height_m": -(height_t1 or 0.0),
                "confidence": 0.88,
                "review_required": True,
                "details": "Prior building footprint missing in current period."
            }

        # Both exist - check height delta
        h1 = height_t1 or 0.0
        h2 = height_t2 or 0.0
        delta_h = round(h2 - h1, 2)

        area1 = calculate_polygon_area(footprint_t1)
        area2 = calculate_polygon_area(footprint_t2)
        area_ratio = (area2 / area1) if area1 > 0 else 1.0

        if delta_h >= self.height_thresh:
            est_floors_added = max(1, int(round(delta_h / 3.0)))
            return {
                "change_type": "VERTICAL_EXTENSION",
                "delta_height_m": delta_h,
                "estimated_floors_added": est_floors_added,
                "confidence": 0.85,
                "review_required": True,
                "details": f"Vertical extension detected: +{delta_h}m (~{est_floors_added} additional floors)."
            }
        elif area_ratio > 1.25:
            return {
                "change_type": "HORIZONTAL_EXTENSION",
                "delta_height_m": delta_h,
                "area_increase_ratio": round(area_ratio, 2),
                "confidence": 0.82,
                "review_required": True,
                "details": f"Footprint expanded by {((area_ratio - 1) * 100):.1f}%."
            }
        else:
            return {
                "change_type": "UNCHANGED",
                "delta_height_m": delta_h,
                "confidence": 0.95,
                "review_required": False,
                "details": "Footprint and elevation remain consistent."
            }

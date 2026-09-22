"""
Elevation raster processing (DSM, DTM, nDSM) and building height extraction.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np
from typing import Dict, Any, Optional


def compute_ndsm(dsm: np.ndarray, dtm: np.ndarray, nodata_val: float = -9999.0) -> np.ndarray:
    if dsm.shape != dtm.shape:
        raise ValueError(f"DSM shape {dsm.shape} and DTM shape {dtm.shape} must match.")

    valid_mask = (dsm != nodata_val) & (dtm != nodata_val) & ~np.isnan(dsm) & ~np.isnan(dtm)
    ndsm = np.full_like(dsm, nodata_val, dtype=np.float32)

    diff = dsm[valid_mask] - dtm[valid_mask]
    ndsm[valid_mask] = np.maximum(0.0, diff)

    return ndsm


def extract_height_metrics(
    elevation_patch: np.ndarray,
    mask: Optional[np.ndarray] = None,
    nodata_val: float = -9999.0
) -> Dict[str, Any]:
    if mask is not None:
        if mask.shape != elevation_patch.shape:
            raise ValueError("Mask shape must match elevation patch shape.")
        valid = (mask > 0) & (elevation_patch != nodata_val) & ~np.isnan(elevation_patch)
    else:
        valid = (elevation_patch != nodata_val) & ~np.isnan(elevation_patch)

    values = elevation_patch[valid].astype(np.float64)
    if len(values) == 0:
        return {
            "valid_pixels": 0,
            "mean_height": None,
            "median_height": None,
            "p75_height": None,
            "p90_height": None,
            "p95_height": None,
            "max_height": None,
            "min_height": None,
            "std_height": None
        }

    return {
        "valid_pixels": int(len(values)),
        "mean_height": float(np.round(np.mean(values), 2)),
        "median_height": float(np.round(np.median(values), 2)),
        "p75_height": float(np.round(np.percentile(values, 75), 2)),
        "p90_height": float(np.round(np.percentile(values, 90), 2)),
        "p95_height": float(np.round(np.percentile(values, 95), 2)),
        "max_height": float(np.round(np.max(values), 2)),
        "min_height": float(np.round(np.min(values), 2)),
        "std_height": float(np.round(np.std(values), 2))
    }


def estimate_floor_count(height_metres: Optional[float], floor_height_m: float = 3.0) -> Optional[int]:
    if height_metres is None or height_metres <= 0:
        return None
    return max(1, int(round(height_metres / floor_height_m)))

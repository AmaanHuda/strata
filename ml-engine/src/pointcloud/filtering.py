"""
Statistical outlier removal and grid filtering for elevation point clouds.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np


def statistical_outlier_removal(elevations: np.ndarray, k_std: float = 2.5) -> np.ndarray:
    valid_mask = ~np.isnan(elevations)
    if not np.any(valid_mask):
        return elevations

    mean = np.mean(elevations[valid_mask])
    std = np.std(elevations[valid_mask])

    filtered = elevations.copy()
    outlier_mask = valid_mask & (np.abs(elevations - mean) > (k_std * std))
    filtered[outlier_mask] = np.nan
    return filtered


def filter_invalid_z(elevations: np.ndarray, min_z: float = -500.0, max_z: float = 9000.0) -> np.ndarray:
    filtered = elevations.copy()
    invalid_mask = (elevations < min_z) | (elevations > max_z)
    filtered[invalid_mask] = np.nan
    return filtered


def fill_nodata_nearest(grid: np.ndarray, nodata_val: float = -9999.0) -> np.ndarray:
    filled = grid.copy().astype(np.float32)
    invalid_mask = (filled == nodata_val) | np.isnan(filled)

    if not np.any(invalid_mask) or np.all(invalid_mask):
        return filled

    valid_coords = np.argwhere(~invalid_mask)
    invalid_coords = np.argwhere(invalid_mask)

    for r_inv, c_inv in invalid_coords:
        dists = (valid_coords[:, 0] - r_inv) ** 2 + (valid_coords[:, 1] - c_inv) ** 2
        nearest_idx = np.argmin(dists)
        r_val, c_val = valid_coords[nearest_idx]
        filled[r_inv, c_inv] = grid[r_val, c_val]

    return filled

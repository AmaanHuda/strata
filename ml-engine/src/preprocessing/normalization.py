"""
Imagery normalization for Cartosat, Sentinel, and aerial datasets.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np


def normalize_min_max(img: np.ndarray, min_val: float = None, max_val: float = None) -> np.ndarray:
    data = img.astype(np.float32)
    c_min = float(np.min(data)) if min_val is None else min_val
    c_max = float(np.max(data)) if max_val is None else max_val

    if c_max - c_min < 1e-8:
        return np.zeros_like(data)

    return np.clip((data - c_min) / (c_max - c_min), 0.0, 1.0)


def normalize_percentile(img: np.ndarray, p_min: float = 2.0, p_max: float = 98.0) -> np.ndarray:
    data = img.astype(np.float32)
    v_min = float(np.percentile(data, p_min))
    v_max = float(np.percentile(data, p_max))

    if v_max - v_min < 1e-8:
        return np.zeros_like(data)

    return np.clip((data - v_min) / (v_max - v_min), 0.0, 1.0)


def normalize_zscore(img: np.ndarray) -> np.ndarray:
    data = img.astype(np.float32)
    mean = float(np.mean(data))
    std = float(np.std(data))
    if std < 1e-8:
        return np.zeros_like(data)
    return (data - mean) / std

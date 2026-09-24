"""
Heuristic monocular height heuristic (NOT a neural network).

SIH 2026 PS 26011 - ML Engine

CORRECTION NOTICE
-----------------
This module previously defined `DeepHeightEstimator`, documented as a "Deep
neural network estimator". It was not: it imported numpy only, had no
parameters, no layers and no weights, and its "height map" was
`std(image, axis=channels) * 25.0`.

Worse, when the image contained no usable signal it returned a hard-coded
9.0 m at confidence 0.50 - an invented measurement. That fabricated fallback is
removed here: with no signal this returns `estimated_height_m = None` and
confidence 0.0, mirroring the honest pattern already used by
`src/height/estimator.py`.

The analytical, nDSM-based estimator in `src/height/estimator.py` remains the
preferred height path. There is currently no trained height model because no
building-level height ground truth exists in the eligible data sources.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

HEURISTIC_MODEL_VERSION = "heuristic-baseline-1.0.0"


class HeuristicHeightEstimator:
    """
    Deterministic contrast-based height heuristic.

    NOT a trained model: `is_trained_model` is False and no weights exist.
    Returns None rather than an invented height when there is no usable signal.
    """

    is_trained_model = False

    def __init__(self, model_version: str = HEURISTIC_MODEL_VERSION):
        self.model_version = model_version

    def predict_height_map(self, optical_chip: np.ndarray, terrain_dem: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Relative height response in metres, derived from per-pixel channel
        contrast. Deterministic arithmetic, not learned inference.
        """
        if optical_chip.ndim == 3:
            contrast = np.std(optical_chip, axis=2).astype(np.float32)
        else:
            contrast = optical_chip.astype(np.float32)

        c_max = np.max(contrast)
        norm_contrast = (contrast / c_max) if c_max > 1e-5 else np.zeros_like(contrast)
        return norm_contrast * 25.0

    def estimate_building_height(
        self,
        optical_chip: np.ndarray,
        footprint_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        height_map = self.predict_height_map(optical_chip)

        if footprint_mask is not None and np.any(footprint_mask):
            candidates = height_map[footprint_mask > 0]
        else:
            candidates = height_map[height_map > 3.0]

        if candidates.size == 0:
            # No usable signal. Report that honestly instead of inventing a value.
            return {
                "estimated_height_m": None,
                "confidence": 0.0,
                "data_status": "INFERRED",
                "method": "NO_SIGNAL",
                "model_version": self.model_version,
                "is_trained_model": self.is_trained_model,
                "limitation": (
                    "Contrast heuristic found no usable height signal. No trained "
                    "height model exists: building-level height ground truth is "
                    "absent from eligible data sources."
                ),
            }

        return {
            "estimated_height_m": round(float(np.percentile(candidates, 90)), 2),
            "confidence": 0.80,
            "data_status": "INFERRED",
            "model_version": self.model_version,
            "is_trained_model": self.is_trained_model,
            "method": "contrast_percentile_90",
        }

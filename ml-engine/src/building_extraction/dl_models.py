"""
Heuristic footprint segmentation baseline (NOT a neural network).

SIH 2026 PS 26011 - ML Engine

CORRECTION NOTICE
-----------------
This module previously defined `UNetFootprintModel`, documented as a "Standard
PyTorch / ONNX-compatible U-Net building footprint segmentation runner" and
stamped every result with `model_version = "1.0.0-unet-cartosat"`.

It was not a neural network and never could have been trained:

  * it imported numpy only - there was no torch import anywhere in the repo,
  * it held no parameters, no layers and no weights,
  * its "inference" was a fixed logistic response over greyscale pixel intensity.

The genuinely trainable architecture now lives in
`src/building_extraction/torch_unet.py` (a real `torch.nn.Module` U-Net with
checkpointing and provenance metadata).

This module retains the deterministic intensity-response heuristic that the
benchmark script relies on, under an honest name, with `is_trained_model = False`
so that no output of this module can be mistaken for a trained model prediction.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

# Kept for interface compatibility with the previous class name.
HEURISTIC_MODEL_VERSION = "heuristic-baseline-1.0.0"


class HeuristicFootprintSegmenter:
    """
    Deterministic intensity-threshold footprint heuristic.

    NOT a trained model. `is_trained_model` is False and no weights are loaded.
    Use `torch_unet.UNet` for trainable segmentation.
    """

    is_trained_model = False

    def __init__(self, weights_path: Optional[str] = None, input_channels: int = 3):
        # `weights_path` is accepted for backwards compatibility only. This class
        # has no weights: passing a path here does NOT load a model.
        self.weights_path = weights_path
        self.input_channels = input_channels
        self.model_version = HEURISTIC_MODEL_VERSION

    def predict_probability_map(self, image_chip: np.ndarray) -> np.ndarray:
        """
        Deterministic response map in [0, 1] derived from pixel intensity.

        This is arithmetic, not inference: the same input always yields the same
        output and nothing was learned from data.
        """
        if image_chip.ndim == 3:
            gray = np.mean(image_chip, axis=2).astype(np.float32)
        else:
            gray = image_chip.astype(np.float32)

        g_min, g_max = np.min(gray), np.max(gray)
        if g_max - g_min > 1e-5:
            norm = (gray - g_min) / (g_max - g_min)
        else:
            norm = np.zeros_like(gray)

        return 1.0 / (1.0 + np.exp(-6.0 * (norm - 0.45)))

    def segment(self, image_chip: np.ndarray, threshold: float = 0.50) -> Dict[str, Any]:
        prob_map = self.predict_probability_map(image_chip)
        binary_mask = (prob_map >= threshold).astype(np.uint8)
        mean_confidence = float(np.mean(prob_map[binary_mask == 1])) if np.any(binary_mask) else 0.0
        return {
            "binary_mask": binary_mask,
            "probability_map": prob_map,
            "mean_confidence": round(mean_confidence, 4),
            "model_version": self.model_version,
            "is_trained_model": self.is_trained_model,
            "method": "heuristic_intensity_response",
        }

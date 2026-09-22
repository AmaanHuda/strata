"""
Evaluation metrics for building footprint segmentation.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np
from typing import Dict, Any


def calculate_iou(pred_mask: np.ndarray, true_mask: np.ndarray) -> float:
    p = pred_mask.astype(bool)
    t = true_mask.astype(bool)
    intersection = np.logical_and(p, t).sum()
    union = np.logical_or(p, t).sum()
    if union == 0:
        return 1.0 if intersection == 0 else 0.0
    return float(intersection / union)


def calculate_dice(pred_mask: np.ndarray, true_mask: np.ndarray) -> float:
    p = pred_mask.astype(bool)
    t = true_mask.astype(bool)
    intersection = np.logical_and(p, t).sum()
    total = p.sum() + t.sum()
    if total == 0:
        return 1.0
    return float(2.0 * intersection / total)


def calculate_precision_recall_f1(pred_mask: np.ndarray, true_mask: np.ndarray) -> Dict[str, float]:
    p = pred_mask.astype(bool)
    t = true_mask.astype(bool)
    tp = np.logical_and(p, t).sum()
    fp = np.logical_and(p, ~t).sum()
    fn = np.logical_and(~p, t).sum()

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "iou": round(calculate_iou(p, t), 4)
    }

"""
Height estimation evaluation metrics and ground truth classification.
SIH 2026 PS 26011 - Task 3: Building Height Estimation
"""
import numpy as np
from typing import Dict, Any, List, Union, Optional

# Standardized Ground Truth Statuses for Height
REAL_REFERENCE_HEIGHT = "REAL_REFERENCE_HEIGHT"
DERIVED_HEIGHT = "DERIVED_HEIGHT"
INFERRED_HEIGHT = "INFERRED_HEIGHT"
DATA_LIMITED = "DATA_LIMITED"


def calculate_height_metrics(
    y_pred: Union[List[float], np.ndarray],
    y_true: Union[List[float], np.ndarray],
    ground_truth_type: str = DATA_LIMITED
) -> Dict[str, Any]:
    """
    Computes regression and error distribution metrics for height estimation:
      - MAE (Mean Absolute Error)
      - RMSE (Root Mean Squared Error)
      - MedAE (Median Absolute Error)
      - p90_AE (90th percentile Absolute Error)
      - MAPE (Mean Absolute Percentage Error / Relative Error)
    """
    pred = np.asarray(y_pred, dtype=np.float64)
    target = np.asarray(y_true, dtype=np.float64)

    if len(pred) == 0 or len(target) == 0 or len(pred) != len(target):
        raise ValueError("y_pred and y_true must be non-empty and have identical length.")

    errors = np.abs(pred - target)
    sq_errors = (pred - target) ** 2

    mae = float(np.mean(errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))
    med_ae = float(np.median(errors))
    p90_ae = float(np.percentile(errors, 90))

    # Calculate MAPE where ground truth > 0
    non_zero = target > 0.1
    if np.any(non_zero):
        mape = float(np.mean(errors[non_zero] / target[non_zero]) * 100.0)
    else:
        mape = 0.0

    return {
        "sample_count": int(len(pred)),
        "mae_metres": round(mae, 4),
        "rmse_metres": round(rmse, 4),
        "median_ae_metres": round(med_ae, 4),
        "p90_ae_metres": round(p90_ae, 4),
        "relative_error_mape_percent": round(mape, 2),
        "ground_truth_type": ground_truth_type,
        "is_real_ground_truth": ground_truth_type == REAL_REFERENCE_HEIGHT
    }

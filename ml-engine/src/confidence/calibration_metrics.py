"""
Statistical calibration metrics for confidence scores and probabilistic predictions.
SIH 2026 PS 26011 - Task 10: Calibrated Confidence & Uncertainty
"""
import numpy as np
from typing import Dict, Any, List, Union, Tuple


def calculate_brier_score(
    predicted_probs: Union[List[float], np.ndarray],
    true_labels: Union[List[int], np.ndarray]
) -> float:
    """
    Computes Brier Score (Mean Squared Error of probability forecasts):
      Brier = (1/N) * sum((p_i - y_i)^2)
    Ranges from 0.0 (perfectly calibrated) to 1.0.
    """
    p = np.asarray(predicted_probs, dtype=np.float64)
    y = np.asarray(true_labels, dtype=np.float64)

    if len(p) == 0 or len(y) == 0 or len(p) != len(y):
        raise ValueError("predicted_probs and true_labels must be non-empty and have matching dimensions.")

    return float(np.mean((p - y) ** 2))


def calculate_expected_calibration_error(
    predicted_probs: Union[List[float], np.ndarray],
    true_labels: Union[List[int], np.ndarray],
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Computes Expected Calibration Error (ECE) and Maximum Calibration Error (MCE)
    by partitioning predictions into equispaced confidence bins.
    """
    p = np.asarray(predicted_probs, dtype=np.float64)
    y = np.asarray(true_labels, dtype=np.float64)

    if len(p) == 0 or len(y) == 0 or len(p) != len(y):
        raise ValueError("predicted_probs and true_labels must have matching non-empty lengths.")

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    bin_details = []

    total_samples = len(p)

    for b in range(n_bins):
        bin_lower = bin_boundaries[b]
        bin_upper = bin_boundaries[b + 1]

        if b == n_bins - 1:
            in_bin = (p >= bin_lower) & (p <= bin_upper)
        else:
            in_bin = (p >= bin_lower) & (p < bin_upper)

        bin_count = int(np.sum(in_bin))
        if bin_count > 0:
            bin_acc = float(np.mean(y[in_bin]))
            bin_conf = float(np.mean(p[in_bin]))
            bin_error = abs(bin_acc - bin_conf)

            ece += (bin_count / total_samples) * bin_error
            mce = max(mce, bin_error)

            bin_details.append({
                "bin_index": b,
                "range": [round(bin_lower, 2), round(bin_upper, 2)],
                "count": bin_count,
                "mean_confidence": round(bin_conf, 4),
                "empirical_accuracy": round(bin_acc, 4),
                "calibration_gap": round(bin_error, 4)
            })

    return {
        "expected_calibration_error": round(float(ece), 4),
        "maximum_calibration_error": round(float(mce), 4),
        "n_bins": n_bins,
        "sample_count": total_samples,
        "bin_details": bin_details
    }


def compute_prediction_interval(
    estimate: float,
    uncertainty: float,
    confidence_level: float = 0.95
) -> Tuple[float, float]:
    """
    Constructs symmetric predictive interval bounds [lower, upper] given base estimate and uncertainty scale.
    """
    # Approximate z-score for 95% interval
    z = 1.96 if confidence_level >= 0.95 else 1.645
    margin = z * (uncertainty * max(1.0, abs(estimate) * 0.15))
    lower = max(0.0, estimate - margin)
    upper = estimate + margin
    return (round(lower, 2), round(upper, 2))

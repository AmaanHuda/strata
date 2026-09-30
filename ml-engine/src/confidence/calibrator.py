"""
Confidence & Uncertainty Quantification Calibrator.
SIH 2026 PS 26011 - ML Engine
"""
from typing import Optional, Dict, Any, Tuple

from src.confidence.calibration_metrics import (
    calculate_brier_score,
    calculate_expected_calibration_error,
    compute_prediction_interval
)


class ConfidenceCalibrator:
    """
    Calculates calibrated confidence (0.0 to 1.0) and uncertainty (0.0 to 1.0)
    integrating model probability, sensor reliability, cross-source agreement, and geometry validity.
    """
    def __init__(self, high_confidence_threshold: float = 0.75, max_uncertainty_threshold: float = 0.30):
        self.high_conf_thresh = high_confidence_threshold
        self.max_uncert_thresh = max_uncertainty_threshold

    def compute_confidence_and_uncertainty(
        self,
        evidence_reliability: float,
        geometry_validity: bool,
        has_direct_height: bool,
        has_official_parcel: bool,
        model_probability: Optional[float] = None,
        has_source_conflict: bool = False
    ) -> Dict[str, Any]:
        score = 0.0
        # Evidence contribution: 35%
        score += 0.35 * evidence_reliability
        # Geometry validity: 25%
        score += 0.25 if geometry_validity else 0.0
        # Direct height measurement: 20%
        score += 0.20 if has_direct_height else 0.05
        # Official parcel match: 15%
        score += 0.15 if has_official_parcel else 0.05
        # Model probability nuance: 5%
        if model_probability is not None:
            score += 0.05 * min(1.0, max(0.0, model_probability))
        else:
            score += 0.03

        # Conflict penalty: severe reduction if conflicting evidence
        if has_source_conflict:
            score *= 0.60

        confidence = round(min(1.0, max(0.0, score)), 4)
        
        # Uncertainty is elevated by missing modalities and conflicts
        base_uncert = 1.0 - confidence
        if not has_direct_height:
            base_uncert = max(base_uncert, 0.35)
        if has_source_conflict:
            base_uncert = max(base_uncert, 0.50)
            
        uncertainty = round(min(1.0, max(0.0, base_uncert)), 4)

        if has_source_conflict:
            review_status = "SOURCE_CONFLICT"
        elif confidence >= self.high_conf_thresh and uncertainty <= self.max_uncert_thresh and geometry_validity:
            review_status = "APPROVED"
        elif confidence < 0.50:
            review_status = "LOW_CONFIDENCE"
        else:
            review_status = "REVIEW_REQUIRED"

        return {
            "confidence": confidence,
            "uncertainty": uncertainty,
            "review_status": review_status,
            "has_source_conflict": has_source_conflict
        }

    def get_height_prediction_interval(self, height_m: float, uncertainty: float) -> Tuple[float, float]:
        return compute_prediction_interval(height_m, uncertainty)


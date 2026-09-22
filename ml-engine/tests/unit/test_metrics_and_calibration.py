"""
test_metrics_and_calibration.py
Unit tests for height regression metrics, statistical confidence calibration, and multi-modal conflict fusion.
SIH 2026 PS 26011 - ML Engine
"""
import pytest
import numpy as np

from src.height.metrics import calculate_height_metrics, DERIVED_HEIGHT, REAL_REFERENCE_HEIGHT, DATA_LIMITED
from src.confidence.calibration_metrics import (
    calculate_brier_score,
    calculate_expected_calibration_error,
    compute_prediction_interval
)
from src.fusion.engine import EvidenceFusionEngine, EVIDENCE_SUPPORTED, EVIDENCE_CONFLICTING, EVIDENCE_MISSING
from src.floors.detector import FloorCountDetector


class TestHeightMetrics:
    def test_calculate_height_metrics_perfect(self):
        y_true = [10.0, 20.0, 30.0]
        y_pred = [10.0, 20.0, 30.0]
        res = calculate_height_metrics(y_pred, y_true, ground_truth_type=REAL_REFERENCE_HEIGHT)
        assert res["mae_metres"] == 0.0
        assert res["rmse_metres"] == 0.0
        assert res["median_ae_metres"] == 0.0
        assert res["p90_ae_metres"] == 0.0
        assert res["relative_error_mape_percent"] == 0.0
        assert res["is_real_ground_truth"] is True

    def test_calculate_height_metrics_with_error(self):
        y_true = [10.0, 20.0, 30.0]
        y_pred = [11.0, 19.0, 32.0]
        res = calculate_height_metrics(y_pred, y_true, ground_truth_type=DERIVED_HEIGHT)
        assert res["mae_metres"] > 0.0
        assert res["rmse_metres"] > 0.0
        assert res["sample_count"] == 3
        assert res["ground_truth_type"] == DERIVED_HEIGHT


class TestConfidenceCalibrationMetrics:
    def test_brier_score(self):
        probs = [0.9, 0.8, 0.1, 0.2]
        labels = [1, 1, 0, 0]
        score = calculate_brier_score(probs, labels)
        assert score < 0.05

    def test_expected_calibration_error(self):
        probs = [0.95, 0.85, 0.75, 0.65, 0.25, 0.15]
        labels = [1, 1, 1, 0, 0, 0]
        res = calculate_expected_calibration_error(probs, labels, n_bins=3)
        assert "expected_calibration_error" in res
        assert "maximum_calibration_error" in res
        assert res["sample_count"] == 6

    def test_prediction_interval(self):
        lower, upper = compute_prediction_interval(estimate=18.0, uncertainty=0.20, confidence_level=0.95)
        assert lower < 18.0
        assert upper > 18.0
        assert lower >= 0.0


class TestEvidenceConflictFusion:
    def test_detect_height_discrepancy_conflict(self):
        fusion = EvidenceFusionEngine()
        evidence_list = [
            {"source": "Cartosat-3", "type": "satellite", "reliability": 0.80},
            {"source": "Drone Survey", "type": "drone", "reliability": 0.90}
        ]
        height_observations = [
            {"source": "satellite_stereo", "height_m": 12.0},
            {"source": "drone_lidar", "height_m": 22.0}  # 10m conflict!
        ]
        res = fusion.fuse_evidence(evidence_list, height_observations=height_observations)
        assert res["evidence_state"] == EVIDENCE_CONFLICTING
        assert res["review_status"] == "SOURCE_CONFLICT"
        assert len(res["conflicts"]) > 0

    def test_harmonious_multi_modal_evidence(self):
        fusion = EvidenceFusionEngine()
        evidence_list = [
            {"source": "Cartosat-3", "type": "satellite", "reliability": 0.80},
            {"source": "DILRMP Cadastral", "type": "cadastral", "reliability": 0.90}
        ]
        res = fusion.fuse_evidence(evidence_list)
        assert res["evidence_state"] == EVIDENCE_SUPPORTED
        assert res["review_status"] == "APPROVED"


class TestFloorDetectorMetadata:
    def test_floor_detector_from_metadata(self):
        detector = FloorCountDetector()
        res = detector.detect_from_metadata(levels_metadata=4)
        assert res["floor_count"] == 4
        assert res["floor_count_source"] == "METADATA_BASED"
        assert res["floor_count_status"] == "DERIVED"
        assert res["confidence"] == 0.80

"""
Regression guards for the ML Engine HTTP layer.

SIH 2026 PS 26011 - ML Engine

The /predict/* endpoints previously returned hard-coded fabricated values
(estimated_height_m 9.0 at confidence 0.50 for any request carrying a WKT
footprint). These tests lock in the honest behaviour: any reported value must
come from the documented heuristic, and without usable signal the API must say
so rather than invent a number.
"""
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from src.server import app  # noqa: E402


@pytest.fixture()
def client():
    return fastapi_testclient.TestClient(app)


def test_health_reports_registry_truth(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["inference_ready"] in ("baseline_only", "trained_models_available")
    assert data["trained_models_loaded"] == bool(data["models_loaded"])
    assert data["model_registry"]["checkpoints_found"] >= 0


def test_predict_height_without_signal_reports_unavailable(client):
    """No footprint means no pixels; the API must not return an invented height."""
    data = client.post("/predict/height", json={"lat": 28.6, "lon": 77.2}).json()
    assert data["status"] == "ok"
    assert data["estimated_height_m"] == 0.0
    assert data["confidence_score"] == 0.0
    assert data["method"] == "DATA_NOT_AVAILABLE"


def test_predict_height_with_footprint_is_heuristic_not_fabricated(client):
    """
    With a footprint the response comes from the documented contrast heuristic.
    The old hard-coded response was exactly 9.0 at confidence 0.50 with method
    'heuristic_baseline' - it must never reappear.
    """
    data = client.post(
        "/predict/height",
        json={
            "lat": 28.6,
            "lon": 77.2,
            "footprint_wkt": "POLYGON((0 0,1 0,1 1,0 0))",
        },
    ).json()
    assert data["status"] == "ok"
    assert data["method"] == "contrast_percentile_90"
    assert data["confidence_score"] > 0.0
    assert data["estimated_height_m"] > 0.0
    # Deterministic heuristic output: the neutral test chip always yields the
    # same height. The fabricated constant must never return.
    assert data["estimated_height_m"] != 9.0 or data["method"] != "heuristic_baseline"


def test_predict_height_is_deterministic(client):
    payload = {"lat": 28.6, "lon": 77.2, "footprint_wkt": "POLYGON((0 0,1 0,1 1,0 0))"}
    first = client.post("/predict/height", json=payload).json()
    second = client.post("/predict/height", json=payload).json()
    assert first["estimated_height_m"] == second["estimated_height_m"]


def test_predict_floors_reports_baseline_method(client):
    data = client.post("/predict/floors", json={"height_m": 10.5}).json()
    assert data["status"] == "ok"
    assert data["floor_count"] >= 1
    assert data["method"] == "height_division_baseline"


def test_predict_floors_zero_height_is_explicitly_unavailable(client):
    data = client.post("/predict/floors", json={"height_m": 0}).json()
    assert data["floor_count"] == 0
    assert data["method"] == "DATA_NOT_AVAILABLE"

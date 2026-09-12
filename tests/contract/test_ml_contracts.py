"""Contract tests: ML engine schema validation."""
from app.integrations.ml_engine.contracts import (
    HeightEstimationRequest,
    HeightEstimationResponse,
    BuildingExtractionRequest,
    FloorCountRequest,
)


def test_height_request_schema():
    req = HeightEstimationRequest(parcel_id="p1", building_id="b1", lat=19.0, lon=72.8)
    assert req.lat == 19.0


def test_height_response_has_disclaimer():
    resp = HeightEstimationResponse(
        building_id="b1",
        estimated_height_m=15.5,
        confidence_score=0.87,
        confidence_label="HIGH",
        model_version="v1.0",
        inference_time_ms=120.5,
    )
    assert "AI-derived" in resp.legal_disclaimer


def test_extraction_request_schema():
    req = BuildingExtractionRequest(parcel_id="p1", bbox=[72.8, 18.9, 72.9, 19.0])
    assert len(req.bbox) == 4

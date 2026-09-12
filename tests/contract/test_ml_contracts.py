"""ML integration contracts tests."""
import pytest
from pydantic import ValidationError
from app.integrations.ml_engine.contracts import (
    BuildingExtractionRequest,
    HeightEstimationRequest,
    HeightEstimationResponse,
    MLIngestionPayload,
    SUPPORTED_SCHEMA_VERSIONS,
)


def test_height_estimation_contract():
    req = HeightEstimationRequest(
        parcel_id="parcel-1",
        building_id="bldg-1",
        lat=28.6139,
        lon=77.2090,
    )
    assert req.lat == 28.6139
    assert req.lon == 77.2090

    res = HeightEstimationResponse(
        status="success",
        estimated_height_m=15.2,
        confidence_score=0.88,
        method="lidar_fusion",
        model_version="v2.0",
    )
    assert res.estimated_height_m == 15.2
    assert res.status == "success"


def test_ml_ingestion_payload_validation():
    payload = MLIngestionPayload(
        schema_version="2.0.0",
        parcel_number="DEL-001-99",
        district="Central Delhi",
        buildings=[
            {
                "footprint_wkt": "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))",
                "height_m": 12.0,
                "floor_count": 4,
            }
        ],
    )
    assert payload.schema_version in SUPPORTED_SCHEMA_VERSIONS
    assert len(payload.buildings) == 1

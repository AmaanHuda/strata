"""
End-to-End Integration tests for full ML pipeline.
Validates end-to-end payload against schemas/ml_output_contract.json.
SIH 2026 PS 26011 - ML Engine
"""
import json
import pathlib
import pytest
import jsonschema

from src.inference.pipeline import MLEnginePipeline

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ml_output_contract.json"


@pytest.fixture
def contract_schema():
    assert SCHEMA_PATH.exists(), f"Output contract schema missing: {SCHEMA_PATH}"
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_full_pipeline_execution_and_schema_compliance(contract_schema):
    pipeline = MLEnginePipeline(schema_dict=contract_schema)

    # Realistic Mumbai parcel and building in EPSG:4326
    parcel_coords = [
        (72.8250, 18.9750),
        (72.8260, 18.9750),
        (72.8260, 18.9760),
        (72.8250, 18.9760),
        (72.8250, 18.9750)
    ]
    building_coords = [
        (72.8252, 18.9752),
        (72.8258, 18.9752),
        (72.8258, 18.9758),
        (72.8252, 18.9758),
        (72.8252, 18.9752)
    ]

    output = pipeline.process_parcel(
        official_ulpin="MH-MUM-2026-009876",
        parcel_polygon=parcel_coords,
        building_footprint=building_coords,
        height_m=18.5,
        evidence=[
            {"source": "ISRO Cartosat-3", "type": "satellite", "reliability": 0.85, "date": "2024-03"},
            {"source": "CartoDEM v3", "type": "dem", "reliability": 0.75, "date": "2023-11"}
        ],
        crs="EPSG:4326"
    )

    # Assert schema validation passed
    assert output["official_ulpin"] == "MH-MUM-2026-009876"
    assert output["height"] == 18.5
    assert output["floor_count"] == 6  # 18.5 / 3.0 ~ 6 floors
    assert output["data_status"] == "DERIVED"
    assert output["review_status"] in ["APPROVED", "REVIEW_REQUIRED"]
    assert output["confidence"] >= 0.70
    assert output["uncertainty"] <= 0.30
    assert output["validation"]["status"] == "VALID"
    assert output["volume_id"].startswith("VOL-MH-MUM-2026-009876")


def test_pipeline_handles_unmeasured_height_with_inferred_status(contract_schema):
    pipeline = MLEnginePipeline(schema_dict=contract_schema)

    parcel_coords = [
        (77.2000, 28.6000),
        (77.2010, 28.6000),
        (77.2010, 28.6010),
        (77.2000, 28.6010),
        (77.2000, 28.6000)
    ]

    output = pipeline.process_parcel(
        official_ulpin="DL-ND-2026-001234",
        parcel_polygon=parcel_coords,
        height_m=None,  # Missing height -> heuristic fallback
        crs="EPSG:4326"
    )

    assert output["data_status"] == "INFERRED"
    assert output["height"] is not None  # Estimated height from floor heuristic
    # Still valid schema-compliant output
    jsonschema.validate(instance=output, schema=contract_schema)

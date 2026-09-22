"""
test_output_schema.py — validate ML output contract schema is well-formed.
Phase 0 baseline test.
"""
import json
import pathlib
import pytest
import jsonschema


SCHEMAS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "schemas"


def test_output_contract_schema_loads():
    schema_path = SCHEMAS_DIR / "ml_output_contract.json"
    assert schema_path.exists(), f"Schema not found: {schema_path}"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    assert schema.get("type") == "object"
    assert "required" in schema


def test_output_contract_schema_validates_valid_payload():
    schema_path = SCHEMAS_DIR / "ml_output_contract.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    valid_payload = {
        "schema_version": "1.0.0",
        "official_ulpin": "ULPIN-MH-001-0001234",
        "building_id": "BLD-001",
        "floor_id": "FL-01",
        "unit_id": "UNIT-001",
        "volume_id": None,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[72.8, 19.0], [72.81, 19.0], [72.81, 19.01], [72.8, 19.01], [72.8, 19.0]]]
        },
        "geometry_crs": "EPSG:4326",
        "height": 12.5,
        "floor_count": 4,
        "confidence": 0.72,
        "uncertainty": 0.18,
        "evidence": [
            {"source": "Cartosat-3", "type": "satellite", "reliability": 0.8, "date": "2024-01"}
        ],
        "validation": {"status": "REVIEW_REQUIRED", "issues": ["geometry_crs is geographic not projected"]},
        "review_status": "REVIEW_REQUIRED",
        "data_status": "DERIVED",
        "model_version": "0.1.0",
        "dataset_version": "0.1.0",
        "provenance_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "generated_at": "2026-09-12T00:00:00Z"
    }
    # Should not raise
    jsonschema.validate(instance=valid_payload, schema=schema)


def test_output_contract_schema_rejects_missing_ulpin():
    schema_path = SCHEMAS_DIR / "ml_output_contract.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    invalid_payload = {
        "schema_version": "1.0.0",
        # missing official_ulpin
        "building_id": "BLD-001",
        "geometry": {"type": "Polygon", "coordinates": []},
        "geometry_crs": "EPSG:4326",
        "confidence": 0.5,
        "uncertainty": 0.2,
        "validation": {"status": "VALID", "issues": []},
        "review_status": "APPROVED",
        "data_status": "REAL",
        "model_version": "0.1.0",
        "dataset_version": "0.1.0",
        "provenance_id": "abc",
        "generated_at": "2026-09-12T00:00:00Z"
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_payload, schema=schema)


def test_dataset_manifest_schema_loads():
    schema_path = SCHEMAS_DIR / "dataset_manifest.json"
    assert schema_path.exists(), f"Schema not found: {schema_path}"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    assert "required" in schema

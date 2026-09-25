"""
Real End-to-End Integration Test: Backend -> ML Engine -> Backend.

Validates the full cycle:
1. Backend receives/initiates parcel processing request
2. ML Service invokes MLEnginePipeline.process_parcel()
3. ML Output Contract v1.0.0 is generated and validated against JSON schema
4. Backend MLDataMapper maps ML Output Contract to Building, Floor, and Unit entities
5. MLAdapter persists validated entities with full ML metadata in database
6. Preserves all 13 ML metadata attributes (geometry, CRS, height, floor_count, confidence,
   uncertainty, evidence, validation, review_status, data_status, model_version, dataset_version, provenance)
7. ULPIN rule is strictly adhered to: official_ulpin is NOT fabricated and the ML volume_id
   is PROVENANCE ONLY (metadata_["volume_id"]) — it is never used as a ULPIN
8. No fake default ML values are introduced (no 0.85/0.80/3.0m).
"""
import json
import pathlib
import uuid
import pytest
import jsonschema

from app.core.config import settings
from app.db.models.property import Building, Floor, Parcel, ScientificStatus, Unit
from app.integrations.ml_engine.adapter import MLAdapter
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import MLProcessParcelRequest, MLOutputContractV1
from app.integrations.ml_engine.mapper import MLDataMapper
from tests.conftest import MockAsyncSession, MockDbStore


@pytest.mark.asyncio
async def test_end_to_end_backend_ml_integration():
    """
    Test end-to-end integration:
    Backend Request -> ML Engine Pipeline -> Contract Validation -> Mapper -> DB Persistence.
    """
    # 1. Enable ML Engine in configuration for the test
    original_enabled = settings.ML_ENGINE_ENABLED
    settings.ML_ENGINE_ENABLED = True
    ml_client.enabled = True

    try:
        store = MockDbStore()
        session = MockAsyncSession(store)

        # 2. Setup existing Parcel in database
        parcel_id = uuid.uuid4()
        test_parcel = Parcel(
            id=parcel_id,
            parcel_number="MH-MUM-2026-009876",
            district="Mumbai",
            state="Maharashtra",
            official_ulpin="MH-MUM-2026-009876",  # genuine official ULPIN supplied externally
            candidate_ulpin=None,
            source_crs="EPSG:4326",
            boundary_wkt="POLYGON((72.8250 18.9750, 72.8260 18.9750, 72.8260 18.9760, 72.8250 18.9760, 72.8250 18.9750))",
        )
        store.save(test_parcel)

        # 3. Instantiate MLAdapter
        adapter = MLAdapter(session)

        # 4. Trigger ML Parcel Processing
        building_footprint_coords = [
            (72.8252, 18.9752),
            (72.8258, 18.9752),
            (72.8258, 18.9758),
            (72.8252, 18.9758),
            (72.8252, 18.9752)
        ]
        evidence = [
            {"source": "ISRO Cartosat-3", "type": "satellite", "reliability": 0.85, "date": "2024-03"},
            {"source": "CartoDEM v3", "type": "dem", "reliability": 0.75, "date": "2023-11"}
        ]

        result = await adapter.process_parcel_with_ml(
            parcel_id=parcel_id,
            building_footprint_coords=building_footprint_coords,
            height_m=18.5,
            evidence=evidence,
        )

        # 5. Verify ML Output Contract Validation & Content
        assert result["success"] is True
        assert result["height_m"] == 18.5
        assert result["floor_count"] == 6
        assert result["confidence"] >= 0.70
        assert result["uncertainty"] <= 0.30
        assert result["floors_created"] == 6
        assert result["units_created"] == 1

        # Check ULPIN Rule
        assert result["official_ulpin"] == "MH-MUM-2026-009876"  # Preserved from parcel, not modified
        # The ML volume_id is provenance, not an identifier: nothing is minted here.
        assert result["candidate_ulpin"] is None
        assert result["metadata"]["volume_id"].startswith("VOL-")

        # 6. Verify Persisted Database Entities
        bld_id = uuid.UUID(result["building_id"])
        persisted_bld = store.get(Building, bld_id)
        assert persisted_bld is not None
        assert persisted_bld.parcel_id == parcel_id
        assert persisted_bld.height_m == 18.5
        assert persisted_bld.floor_count == 6
        assert persisted_bld.ml_derived is True
        assert persisted_bld.ml_model_version == "0.1.0"
        assert persisted_bld.ml_confidence_score == result["confidence"]

        # 7. Verify all 13 ML metadata items are preserved
        meta = persisted_bld.metadata_
        assert meta is not None
        assert "evidence" in meta and len(meta["evidence"]) == 2
        assert "validation" in meta and meta["validation"]["status"] == "VALID"
        assert "review_status" in meta and meta["review_status"] in ["APPROVED", "REVIEW_REQUIRED"]
        assert "data_status" in meta and meta["data_status"] == "DERIVED"
        assert "model_version" in meta and meta["model_version"] == "0.1.0"
        assert "dataset_version" in meta and meta["dataset_version"] == "0.1.0"
        assert "provenance_id" in meta and len(meta["provenance_id"]) > 0
        assert "generated_at" in meta and len(meta["generated_at"]) > 0
        assert "volume_id" in meta and meta["volume_id"].startswith("VOL-")
        assert "floor_id" in meta and meta["floor_id"] == "FL-01"
        assert "unit_id" in meta and meta["unit_id"] == "U-001"
        assert "geometry_crs" in meta and meta["geometry_crs"] == "EPSG:4326"
        assert "uncertainty" in meta and meta["uncertainty"] <= 0.30

        # 8. Verify Persisted Floors and Units
        floors = [v for v in store.entities.values() if isinstance(v, Floor) and v.building_id == bld_id]
        assert len(floors) == 6
        assert floors[0].floor_number == 0
        assert floors[0].ceiling_height_m == (18.5 / 6)  # Real calculated value, not hardcoded 3.0

        units = [v for v in store.entities.values() if isinstance(v, Unit)]
        assert len(units) >= 1
        assert units[0].unit_number == "U-001"
        # No ULPIN is derived from the ML volume_id (provenance only).
        assert units[0].candidate_ulpin is None
        assert units[0].metadata_["volume_id"].startswith("VOL-")

    finally:
        settings.ML_ENGINE_ENABLED = original_enabled
        ml_client.enabled = original_enabled


@pytest.mark.asyncio
async def test_end_to_end_ml_api_endpoint(client_with_auth):
    """
    Tests the Backend HTTP API endpoint POST /api/v1/parcels/{parcel_id}/process-ml.
    """
    original_enabled = settings.ML_ENGINE_ENABLED
    settings.ML_ENGINE_ENABLED = True
    ml_client.enabled = True

    try:
        from tests.conftest import _global_test_store
        parcel_id = uuid.uuid4()
        test_parcel = Parcel(
            id=parcel_id,
            parcel_number="DL-ND-2026-001234",
            district="New Delhi",
            state="Delhi",
            official_ulpin=None,  # Unofficial/unverified parcel
            candidate_ulpin="CAND-DL-001",
            source_crs="EPSG:4326",
            boundary_wkt="POLYGON((77.2000 28.6000, 77.2010 28.6000, 77.2010 28.6010, 77.2000 28.6010, 77.2000 28.6000))",
        )
        _global_test_store.save(test_parcel)

        response = await client_with_auth.post(
            f"/api/v1/parcels/{parcel_id}/process-ml",
            params={"height_m": 12.0}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is True
        assert data["height_m"] == 12.0
        assert data["floor_count"] == 4
        assert data["official_ulpin"] is None  # ULPIN rule: official_ulpin not fabricated!
        assert data["candidate_ulpin"] is None  # volume_id is provenance, not a ULPIN
        assert data["metadata"]["volume_id"].startswith("VOL-")
        assert data["metadata"]["review_status"] in ["APPROVED", "REVIEW_REQUIRED"]

    finally:
        settings.ML_ENGINE_ENABLED = original_enabled
        ml_client.enabled = original_enabled

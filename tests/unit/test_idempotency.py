"""
Unit tests for canonical deterministic input hashing and payload idempotency.
"""
import hashlib
import json
import pytest
import uuid
from app.integrations.ml_engine.contracts import (
    MLBuildingIngest,
    MLFloorIngest,
    MLIngestionPayload,
    MLUnitIngest,
)
from app.services.ingestion import MLIngestionService
from app.db.models.user import User
from tests.conftest import MockAsyncSession, MockDbStore


def test_canonical_input_hashing_determinism():
    """Identical input payloads produce identical deterministic SHA-256 hashes regardless of field order."""
    payload1 = MLIngestionPayload(
        parcel_number="DL-01-002-000456",
        district="New Delhi",
        state="DL",
        model_name="3D-Mapping-Engine",
        model_version="v2.0",
        buildings=[
            MLBuildingIngest(
                building_name="Block-A",
                footprint_wkt="POLYGON((77.20 28.60, 77.21 28.60, 77.21 28.61, 77.20 28.61, 77.20 28.60))",
                height_m=12.0,
                floor_count=4,
            )
        ]
    )

    payload2 = MLIngestionPayload(
        parcel_number="DL-01-002-000456",
        district="New Delhi",
        state="DL",
        model_name="3D-Mapping-Engine",
        model_version="v2.0",
        buildings=[
            MLBuildingIngest(
                building_name="Block-A",
                footprint_wkt="POLYGON((77.20 28.60, 77.21 28.60, 77.21 28.61, 77.20 28.61, 77.20 28.60))",
                height_m=12.0,
                floor_count=4,
            )
        ]
    )

    dict1 = payload1.model_dump(exclude={"idempotency_key", "job_id"})
    dict2 = payload2.model_dump(exclude={"idempotency_key", "job_id"})

    hash1 = hashlib.sha256(json.dumps(dict1, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(json.dumps(dict2, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    assert hash1 == hash2
    assert len(hash1) == 64


@pytest.mark.asyncio
async def test_idempotent_ingestion_with_key():
    """Submitting payload with identical idempotency key returns cached status without duplicating records."""
    store = MockDbStore()
    session = MockAsyncSession(store)
    service = MLIngestionService(session)

    user = User(
        id=uuid.uuid4(),
        email="surveyor@cadastre.gov.in",
        username="surveyor1",
        role="SURVEYOR"
    )

    payload = MLIngestionPayload(
        idempotency_key="IDEMPOTENCY-KEY-ABC-123",
        parcel_number="DL-01-002-000456",
        district="New Delhi",
        state="DL",
        model_name="3D-Mapping-Engine",
        model_version="v2.0",
        buildings=[
            MLBuildingIngest(
                building_name="Block-A",
                footprint_wkt="POLYGON((77.20 28.60, 77.21 28.60, 77.21 28.61, 77.20 28.61, 77.20 28.60))",
                height_m=12.0,
                floor_count=4,
            )
        ]
    )

    # First ingestion
    res1 = await service.ingest_ml_payload(payload, user)
    assert res1["success"] is True
    assert res1["buildings_created"] == 1

    # Simulate AsyncJob record created with this idempotency key
    from app.db.models.job import AsyncJob, JobStatus
    job = AsyncJob(
        id=uuid.uuid4(),
        job_type="ML_INGESTION",
        idempotency_key="IDEMPOTENCY-KEY-ABC-123",
        status=JobStatus.COMPLETED,
        created_by=user.id,
    )
    store.save(job)


    # Second ingestion with same key
    res2 = await service.ingest_ml_payload(payload, user)
    assert res2["status"] == "already_processed"
    assert res2["idempotency_key"] == "IDEMPOTENCY-KEY-ABC-123"

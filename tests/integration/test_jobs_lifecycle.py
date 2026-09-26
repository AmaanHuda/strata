"""
Integration tests for async job lifecycle endpoints.
Tests /api/v1/jobs (list, submit), /api/v1/jobs/{id} (get), /api/v1/jobs/{id}/cancel.
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4


NONEXISTENT_ID = str(uuid4())


# --- Submit Job ---

@pytest.mark.asyncio
async def test_submit_batch_validation_job(client: AsyncClient, auth_headers: dict):
    """Submit batch_validation job returns 202 Accepted with job metadata."""
    resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "batch_validation", "payload": {"scope": "parcels"}},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "id" in data
    assert data["status"] in ("QUEUED", "PROCESSING")
    assert data["job_type"] == "batch_validation"


@pytest.mark.asyncio
async def test_submit_cadastral_audit_job(client: AsyncClient, auth_headers: dict):
    """Submit cadastral_audit job returns 202 Accepted."""
    resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "cadastral_audit"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["job_type"] == "cadastral_audit"


@pytest.mark.asyncio
async def test_submit_ulpin_batch_job(client: AsyncClient, auth_headers: dict):
    """Submit ulpin_batch job returns 202 Accepted."""
    resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "ulpin_batch"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["job_type"] == "ulpin_batch"


@pytest.mark.asyncio
async def test_submit_job_idempotency(client: AsyncClient, auth_headers: dict):
    """Submitting a job with the same idempotency_key returns the existing job."""
    idempotency_key = f"test-idempotent-{uuid4()}"
    payload = {"job_type": "cadastral_audit", "idempotency_key": idempotency_key}

    # First submission
    resp1 = await client.post("/api/v1/jobs", json=payload, headers=auth_headers)
    assert resp1.status_code == 202
    job_id_1 = resp1.json()["data"]["id"]

    # Second submission with same key
    resp2 = await client.post("/api/v1/jobs", json=payload, headers=auth_headers)
    assert resp2.status_code == 202
    job_id_2 = resp2.json()["data"]["id"]

    # Must return same job ID (idempotency guarantee)
    assert job_id_1 == job_id_2


@pytest.mark.asyncio
async def test_submit_job_invalid_type(client: AsyncClient, auth_headers: dict):
    """Submitting an invalid job type returns 400 or 422."""
    resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "completely_invalid_job_type_xyz"},
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422)


# --- List Jobs ---

@pytest.mark.asyncio
async def test_list_jobs_with_auth(client: AsyncClient, auth_headers: dict):
    """Jobs list returns 200 with jobs array."""
    resp = await client.get("/api/v1/jobs", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_list_jobs_status_filter(client: AsyncClient, auth_headers: dict):
    """Jobs list supports status filter parameter."""
    resp = await client.get(
        "/api/v1/jobs",
        params={"status": "QUEUED"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    for job in body["data"]:
        assert job["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_list_jobs_pagination(client: AsyncClient, auth_headers: dict):
    """Jobs list supports pagination."""
    resp = await client.get(
        "/api/v1/jobs",
        params={"page": 1, "page_size": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200


# --- Get Single Job ---

@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient, auth_headers: dict):
    """Get job returns 404 for non-existent ID."""
    resp = await client.get(f"/api/v1/jobs/{NONEXISTENT_ID}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_get_job_after_submit(client: AsyncClient, auth_headers: dict):
    """Get job returns job details after submission."""
    # Submit a job first
    submit_resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "cadastral_audit"},
        headers=auth_headers,
    )
    assert submit_resp.status_code == 202
    job_id = submit_resp.json()["data"]["id"]

    # Get the job
    get_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] == job_id
    assert "status" in data
    assert "progress" in data
    assert "created_at" in data


# --- Cancel Job ---

@pytest.mark.asyncio
async def test_cancel_job_not_found(client: AsyncClient, auth_headers: dict):
    """Cancel job returns 404 for non-existent ID."""
    resp = await client.post(
        f"/api/v1/jobs/{NONEXISTENT_ID}/cancel",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_queued_job(client: AsyncClient, auth_headers: dict):
    """Cancel a QUEUED job successfully."""
    # Submit a job
    submit_resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "ulpin_batch"},
        headers=auth_headers,
    )
    assert submit_resp.status_code == 202
    job_id = submit_resp.json()["data"]["id"]

    # Cancel immediately (likely still QUEUED)
    cancel_resp = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers=auth_headers,
    )
    # Accept 200 (cancelled) or 409 (already completed/not cancellable)
    assert cancel_resp.status_code in (200, 409)
    if cancel_resp.status_code == 200:
        body = cancel_resp.json()
        assert body["data"]["status"] == "CANCELLED"


# --- Job Response Schema ---

@pytest.mark.asyncio
async def test_job_response_has_required_fields(client: AsyncClient, auth_headers: dict):
    """Job response schema includes all required fields."""
    resp = await client.post(
        "/api/v1/jobs",
        json={"job_type": "batch_validation"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()["data"]

    required_fields = ["id", "job_type", "status", "progress", "created_at"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

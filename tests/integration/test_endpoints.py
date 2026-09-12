"""API Integration tests for endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_openapi_json_available():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        assert "paths" in schema
        assert "/api/v1/auth/register" in schema["paths"]
        assert "/api/v1/parcels" in schema["paths"]
        assert "/api/v1/buildings" in schema["paths"]
        assert "/api/v1/floors" in schema["paths"]
        assert "/api/v1/units" in schema["paths"]
        assert "/api/v1/ulpin/{ulpin_str}" in schema["paths"]
        assert "/api/v1/search" in schema["paths"]
        assert "/api/v1/validation/{property_id}" in schema["paths"]
        assert "/api/v1/datasets" in schema["paths"]
        assert "/api/v1/jobs" in schema["paths"]
        assert "/api/v1/jobs/ingest-ml" in schema["paths"]


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["version"] == "2.0.0"
        assert body["data"]["environment"] == "development"


@pytest.mark.asyncio
async def test_unauthorized_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/parcels")
        assert res.status_code == 401
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "AUTHENTICATION_ERROR"

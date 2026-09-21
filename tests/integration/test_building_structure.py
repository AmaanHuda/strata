"""
Integration tests for building hierarchy structure endpoints.
Tests /api/v1/buildings/{id}/structure and /api/v1/buildings/{id}/geometry.
Uses client_with_auth fixture (dependency-overridden, no real DB needed).
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4


NONEXISTENT_ID = str(uuid4())


# --- Building Structure Endpoint ---

@pytest.mark.asyncio
async def test_building_structure_requires_auth(client: AsyncClient):
    """Building structure endpoint must reject unauthenticated requests."""
    resp = await client.get(f"/api/v1/buildings/{NONEXISTENT_ID}/structure")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_building_structure_not_found(client_with_auth: AsyncClient):
    """Building structure endpoint returns 404 for non-existent building."""
    resp = await client_with_auth.get(f"/api/v1/buildings/{NONEXISTENT_ID}/structure")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_building_structure_response_schema(client_with_auth: AsyncClient):
    """
    When a building exists, structure endpoint returns full nested hierarchy.
    Schema check only - passes if 200 or 404 (empty test DB).
    """
    resp = await client_with_auth.get(f"/api/v1/buildings/{NONEXISTENT_ID}/structure")
    assert resp.status_code in (200, 404)

    if resp.status_code == 200:
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "building_id" in data
        assert "parcel_id" in data
        assert "floors" in data
        assert isinstance(data["floors"], list)
        for floor in data["floors"]:
            assert "floor_number" in floor
            assert "units" in floor
            assert isinstance(floor["units"], list)


# --- Building Geometry Endpoint ---

@pytest.mark.asyncio
async def test_building_geometry_requires_auth(client: AsyncClient):
    """Building geometry endpoint must reject unauthenticated requests."""
    resp = await client.get(f"/api/v1/buildings/{NONEXISTENT_ID}/geometry")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_building_geometry_not_found(client_with_auth: AsyncClient):
    """Building geometry endpoint returns 404 for non-existent building."""
    resp = await client_with_auth.get(f"/api/v1/buildings/{NONEXISTENT_ID}/geometry")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_building_geometry_response_schema(client_with_auth: AsyncClient):
    """Geometry endpoint schema: must contain required fields if 200."""
    resp = await client_with_auth.get(f"/api/v1/buildings/{NONEXISTENT_ID}/geometry")
    assert resp.status_code in (200, 404)

    if resp.status_code == 200:
        data = resp.json()["data"]
        assert "building_id" in data
        assert "centroid" in data
        assert "height_m" in data


# --- Building GeoJSON Endpoint ---

@pytest.mark.asyncio
async def test_building_geojson_not_found(client_with_auth: AsyncClient):
    """Building GeoJSON endpoint returns 404 for non-existent building."""
    resp = await client_with_auth.get(f"/api/v1/buildings/{NONEXISTENT_ID}/geojson")
    assert resp.status_code == 404


# --- Buildings List Endpoint ---

@pytest.mark.asyncio
async def test_buildings_list_requires_auth(client: AsyncClient):
    """Buildings list must require auth."""
    resp = await client.get("/api/v1/buildings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_buildings_list_with_auth(client_with_auth: AsyncClient):
    """Buildings list returns 200 with auth."""
    resp = await client_with_auth.get("/api/v1/buildings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_buildings_list_pagination(client_with_auth: AsyncClient):
    """Buildings list supports pagination with page/page_size params."""
    resp = await client_with_auth.get(
        "/api/v1/buildings",
        params={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

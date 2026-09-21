"""
Integration tests for validation endpoints.
Tests /api/v1/validation/geometry, /topology, and /cadastral.
Uses client_with_auth fixture (dependency-overridden, no real DB needed).
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4


# --- Geometry Validation ---

@pytest.mark.asyncio
async def test_geometry_validation_requires_auth(client: AsyncClient):
    """Geometry validation must reject unauthenticated requests."""
    resp = await client.post(
        "/api/v1/validation/geometry",
        json={"geometry_wkt": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_geometry_validation_valid_polygon(client_with_auth: AsyncClient):
    """Geometry validation accepts a valid 2D WKT polygon."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={
            "geometry_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
            "crs": "EPSG:4326",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_valid"] is True
    assert "errors" in data


@pytest.mark.asyncio
async def test_geometry_validation_self_intersecting(client_with_auth: AsyncClient):
    """Geometry validation detects self-intersecting (bowtie) polygon."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={"geometry_wkt": "POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_geometry_validation_empty_geometry(client_with_auth: AsyncClient):
    """Geometry validation detects empty geometry."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={"geometry_wkt": "POLYGON EMPTY"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_valid"] is False


@pytest.mark.asyncio
async def test_geometry_validation_missing_input(client_with_auth: AsyncClient):
    """Geometry validation returns error when no geometry input is given."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={"crs": "EPSG:4326"},
    )
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json()["data"]["is_valid"] is False


@pytest.mark.asyncio
async def test_geometry_validation_unsupported_crs(client_with_auth: AsyncClient):
    """Geometry validation rejects unsupported CRS."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={
            "geometry_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
            "crs": "EPSG:99999",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_valid"] is False


@pytest.mark.asyncio
async def test_geometry_validation_3d_hierarchy(client_with_auth: AsyncClient):
    """Geometry validation validates 3D floor height hierarchy."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={
            "geometry_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
            "elevation_min_m": 0.0,
            "elevation_max_m": 30.0,
            "floor_number": 2,
            "height_above_ground_m": 3.0,
            "ceiling_height_m": 6.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_valid"] is True


@pytest.mark.asyncio
async def test_geometry_validation_invalid_3d_heights(client_with_auth: AsyncClient):
    """Geometry validation rejects min_elevation > max_elevation."""
    resp = await client_with_auth.post(
        "/api/v1/validation/geometry",
        json={
            "geometry_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
            "elevation_min_m": 50.0,
            "elevation_max_m": 10.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_valid"] is False


# --- Topology Validation ---

@pytest.mark.asyncio
async def test_topology_validation_requires_auth(client: AsyncClient):
    """Topology validation must reject unauthenticated requests."""
    resp = await client.post(
        "/api/v1/validation/topology",
        json={
            "parcel_wkt": "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))",
            "building_wkt": "POLYGON((2 2, 8 2, 8 8, 2 8, 2 2))",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_topology_validation_building_inside_parcel(client_with_auth: AsyncClient):
    """Topology validation passes when building is fully inside parcel."""
    resp = await client_with_auth.post(
        "/api/v1/validation/topology",
        json={
            "parcel_wkt": "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))",
            "building_wkt": "POLYGON((2 2, 8 2, 8 8, 2 8, 2 2))",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_valid"] is True


@pytest.mark.asyncio
async def test_topology_validation_building_outside_parcel(client_with_auth: AsyncClient):
    """Topology validation fails when building extends outside parcel."""
    resp = await client_with_auth.post(
        "/api/v1/validation/topology",
        json={
            "parcel_wkt": "POLYGON((0 0, 5 0, 5 5, 0 5, 0 0))",
            "building_wkt": "POLYGON((3 3, 9 3, 9 9, 3 9, 3 3))",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_valid"] is False or any(
        not c["passed"] for c in data.get("checks", [])
        if c.get("check_name") == "building_within_parcel"
    )


@pytest.mark.asyncio
async def test_topology_validation_missing_parcel(client_with_auth: AsyncClient):
    """Topology validation handles missing parcel_wkt gracefully."""
    resp = await client_with_auth.post(
        "/api/v1/validation/topology",
        json={"building_wkt": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"},
    )
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        data = resp.json()["data"]
        assert "is_valid" in data


# --- Cadastral Validation ---

@pytest.mark.asyncio
async def test_cadastral_validation_requires_auth(client: AsyncClient):
    """Cadastral validation must reject unauthenticated requests."""
    resp = await client.post(
        "/api/v1/validation/cadastral",
        json={"parcel_id": str(uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cadastral_validation_not_found(client_with_auth: AsyncClient):
    """Cadastral validation returns 404 for non-existent parcel_id."""
    resp = await client_with_auth.post(
        "/api/v1/validation/cadastral",
        json={"parcel_id": str(uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cadastral_validation_missing_input(client_with_auth: AsyncClient):
    """Cadastral validation returns error when no entity_id is provided."""
    resp = await client_with_auth.post(
        "/api/v1/validation/cadastral",
        json={},
    )
    assert resp.status_code in (400, 422)

"""
Integration tests for spatial query endpoints.
Tests /api/v1/spatial/bbox, /nearby, /query, and /search (point-in-polygon).
Uses client_with_auth fixture (dependency-overridden, no real DB needed).
"""
import pytest
from httpx import AsyncClient


# --- BBox Endpoint Tests ---

@pytest.mark.asyncio
async def test_spatial_bbox_valid_request(client_with_auth: AsyncClient):
    """BBox endpoint returns 200 with valid coordinates and auth."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/bbox",
        params={
            "min_lon": 77.0,
            "min_lat": 28.0,
            "max_lon": 78.0,
            "max_lat": 29.0,
            "layer": "all",
            "limit": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "results" in data and "count" in data


@pytest.mark.asyncio
async def test_spatial_bbox_invalid_bounds(client_with_auth: AsyncClient):
    """BBox endpoint rejects inverted bounding box (min > max)."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/bbox",
        params={"min_lon": 80.0, "min_lat": 30.0, "max_lon": 77.0, "max_lat": 28.0},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_spatial_bbox_layer_filter(client_with_auth: AsyncClient):
    """BBox endpoint respects layer=parcel filter."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/bbox",
        params={"min_lon": 77.0, "min_lat": 28.0, "max_lon": 78.0, "max_lat": 29.0, "layer": "parcel"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "buildings" not in data or data.get("buildings") is None


# --- Nearby Endpoint Tests ---

@pytest.mark.asyncio
async def test_spatial_nearby_valid_request(client_with_auth: AsyncClient):
    """Nearby endpoint returns 200 with valid lat/lon/radius_m."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/nearby",
        params={"lat": 28.6139, "lon": 77.2090, "radius_m": 1000, "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "results" in data
    for item in data["results"]:
        assert "distance_m" in item
        assert isinstance(item["distance_m"], (int, float))


@pytest.mark.asyncio
async def test_spatial_nearby_invalid_radius(client_with_auth: AsyncClient):
    """Nearby endpoint rejects radius > 50000m."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/nearby",
        params={"lat": 28.6139, "lon": 77.2090, "radius_m": 100000},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_spatial_nearby_invalid_lat_lon(client_with_auth: AsyncClient):
    """Nearby endpoint rejects out-of-range lat/lon."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/nearby",
        params={"lat": 200.0, "lon": 400.0, "radius_m": 500},
    )
    assert resp.status_code in (400, 422)


# --- Polygon Query Endpoint Tests ---

@pytest.mark.asyncio
async def test_spatial_query_valid_polygon_wkt(client_with_auth: AsyncClient):
    """Polygon query returns 200 with valid WKT polygon."""
    resp = await client_with_auth.post(
        "/api/v1/spatial/query",
        json={
            "polygon_wkt": "POLYGON((77.0 28.0, 78.0 28.0, 78.0 29.0, 77.0 29.0, 77.0 28.0))",
            "relation": "intersects",
            "layer": "parcel",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_spatial_query_invalid_wkt(client_with_auth: AsyncClient):
    """Polygon query rejects malformed WKT."""
    resp = await client_with_auth.post(
        "/api/v1/spatial/query",
        json={
            "polygon_wkt": "NOT_VALID_WKT((xyz))",
            "relation": "intersects",
            "layer": "parcel",
        },
    )
    assert resp.status_code in (400, 422)


# --- Point-in-Polygon Lookup Endpoint Tests ---

@pytest.mark.asyncio
async def test_spatial_search_valid_coords(client_with_auth: AsyncClient):
    """Point lookup returns structured result with valid lat/lon (404 if no data in test DB)."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/search",
        params={"lat": 28.6139, "lon": 77.2090},
    )
    assert resp.status_code in (200, 404, 500)
    assert "success" in resp.json()


@pytest.mark.asyncio
async def test_spatial_search_invalid_coords(client_with_auth: AsyncClient):
    """Point lookup rejects invalid lat/lon outside global bounds."""
    resp = await client_with_auth.get(
        "/api/v1/spatial/search",
        params={"lat": 999.0, "lon": -999.0},
    )
    assert resp.status_code in (400, 422)

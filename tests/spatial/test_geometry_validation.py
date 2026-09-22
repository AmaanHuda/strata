"""Spatial & Geometry validation tests (2D and 3D)."""
import pytest
from app.core.errors import InvalidCRSError, InvalidGeometryError
from app.services.geometry_validation import GeometryValidationService


def test_validate_valid_2d_wkt():
    wkt = "POLYGON((77.2090 28.6139, 77.2095 28.6139, 77.2095 28.6145, 77.2090 28.6145, 77.2090 28.6139))"
    res = GeometryValidationService.validate_2d_wkt(wkt)
    assert res["is_valid"] is True
    assert res["geom_type"] == "Polygon"
    assert res["metric_area_sqm"] > 0
    assert "area_method" in res


def test_validate_invalid_wkt():
    with pytest.raises(InvalidGeometryError):
        GeometryValidationService.validate_2d_wkt("INVALID WKT STRING")


def test_validate_self_intersecting_polygon():
    # Bowtie self-intersecting polygon
    wkt = "POLYGON((0 0, 10 10, 0 10, 10 0, 0 0))"
    with pytest.raises(InvalidGeometryError):
        GeometryValidationService.validate_2d_wkt(wkt)


def test_validate_crs():
    assert GeometryValidationService.validate_crs("EPSG:4326") is True
    assert GeometryValidationService.validate_crs("EPSG:3857") is True
    with pytest.raises(InvalidCRSError):
        GeometryValidationService.validate_crs("EPSG:999999")


def test_validate_3d_hierarchy():
    floors = [
        {"floor_number": 0, "height_above_ground_m": 0.0, "ceiling_height_m": 3.0},
        {"floor_number": 1, "height_above_ground_m": 3.0, "ceiling_height_m": 3.0},
        {"floor_number": 2, "height_above_ground_m": 6.0, "ceiling_height_m": 3.0},
    ]
    res = GeometryValidationService.validate_3d_hierarchy(floor_count=3, height_m=9.0, floors_data=floors)
    assert res["is_valid"] is True


def test_validate_3d_negative_height():
    with pytest.raises(InvalidGeometryError):
        GeometryValidationService.validate_3d_hierarchy(floor_count=2, height_m=-5.0, floors_data=[])

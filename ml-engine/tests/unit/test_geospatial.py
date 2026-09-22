"""
Unit tests for geospatial CRS, operations, validation, and GeoJSON conversions.
SIH 2026 PS 26011 - ML Engine
"""
import pytest
import math
from src.geospatial.crs import (
    get_utm_zone_from_lon,
    get_utm_epsg_for_coordinates,
    is_within_india_bbox,
    lonlat_to_web_mercator,
    web_mercator_to_lonlat,
    approximate_utm_forward,
    transform_coordinates,
    EPSG_WGS84,
    EPSG_WEB_MERCATOR,
)
from src.geospatial.operations import (
    compute_bounding_box,
    calculate_polygon_area,
    calculate_perimeter,
    calculate_compactness,
    calculate_centroid,
    point_in_polygon,
)
from src.geospatial.validation import (
    validate_polygon_geometry,
    check_self_intersection,
)
from src.geospatial.conversion import (
    coords_to_geojson_polygon,
    coords_to_geojson_feature,
    create_geojson_feature_collection,
    geojson_feature_to_coords,
)


class TestCRS:
    def test_utm_zone_calculation(self):
        # Mumbai (lon ~72.87) -> Zone 43
        assert get_utm_zone_from_lon(72.87) == 43
        # Delhi (lon ~77.10) -> Zone 43/44
        assert get_utm_zone_from_lon(77.10) == 43
        # Kolkata (lon ~88.36) -> Zone 45
        assert get_utm_zone_from_lon(88.36) == 45
        # Guwahati (lon ~91.73) -> Zone 46
        assert get_utm_zone_from_lon(91.73) == 46

    def test_utm_epsg_string(self):
        assert get_utm_epsg_for_coordinates(72.87, 19.07) == "EPSG:32643"
        assert get_utm_epsg_for_coordinates(88.36, 22.57) == "EPSG:32645"

    def test_india_bounding_box_check(self):
        assert is_within_india_bbox(72.87, 19.07) is True   # Mumbai
        assert is_within_india_bbox(77.20, 28.61) is True   # Delhi
        assert is_within_india_bbox(0.0, 51.5) is False     # London
        assert is_within_india_bbox(120.0, 30.0) is False   # East Asia

    def test_web_mercator_roundtrip(self):
        lon, lat = 77.2090, 28.6139  # New Delhi
        x, y = lonlat_to_web_mercator(lon, lat)
        lon_back, lat_back = web_mercator_to_lonlat(x, y)
        assert math.isclose(lon, lon_back, rel_tol=1e-6)
        assert math.isclose(lat, lat_back, rel_tol=1e-6)

    def test_transform_coordinates(self):
        coords = [(72.85, 19.05), (72.86, 19.05)]
        merc = transform_coordinates(coords, "EPSG:4326", "EPSG:3857")
        assert len(merc) == 2
        assert merc[0][0] > 1000000.0  # Metric coordinates in Mercator


class TestSpatialOperations:
    def test_bounding_box(self):
        coords = [(72.8, 19.0), (72.9, 19.0), (72.9, 19.1), (72.8, 19.1)]
        bbox = compute_bounding_box(coords)
        assert bbox == (72.8, 19.0, 72.9, 19.1)

    def test_polygon_area_metric(self):
        # 100m x 100m square in UTM coordinates
        coords = [(500000, 2000000), (500100, 2000000), (500100, 2000100), (500000, 2000100), (500000, 2000000)]
        area = calculate_polygon_area(coords, crs="EPSG:32643")
        assert math.isclose(area, 10000.0, rel_tol=1e-3)

    def test_polygon_perimeter(self):
        # 100m x 100m square in UTM
        coords = [(500000, 2000000), (500100, 2000000), (500100, 2000100), (500000, 2000100), (500000, 2000000)]
        perimeter = calculate_perimeter(coords, crs="EPSG:32643")
        assert math.isclose(perimeter, 400.0, rel_tol=1e-3)

    def test_compactness_score(self):
        # Circle has compactness ~ 1.0, square ~ 0.785 (pi / 4)
        coords = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        compactness = calculate_compactness(coords, crs="EPSG:32643")
        assert math.isclose(compactness, math.pi / 4.0, rel_tol=1e-2)

    def test_centroid(self):
        coords = [(0, 0), (10, 0), (10, 10), (0, 10)]
        cx, cy = calculate_centroid(coords)
        assert math.isclose(cx, 5.0)
        assert math.isclose(cy, 5.0)

    def test_point_in_polygon(self):
        poly = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        assert point_in_polygon((5, 5), poly) is True
        assert point_in_polygon((15, 5), poly) is False


class TestValidation:
    def test_valid_polygon(self):
        # Building in Mumbai in lon/lat
        coords = [
            (72.8250, 18.9750),
            (72.8252, 18.9750),
            (72.8252, 18.9752),
            (72.8250, 18.9752),
            (72.8250, 18.9750)
        ]
        res = validate_polygon_geometry(coords, min_area_sqm=5.0, crs="EPSG:4326")
        assert res["is_valid"] is True
        assert res["status"] == "VALID"
        assert res["area_sqm"] > 10.0

    def test_self_intersecting_polygon(self):
        # Bowtie / figure-8 polygon
        coords = [(0, 0), (10, 10), (0, 10), (10, 0), (0, 0)]
        assert check_self_intersection(coords) is True
        res = validate_polygon_geometry(coords, crs="EPSG:32643", check_india_bounds=False)
        assert res["is_valid"] is False
        assert any("self-intersecting" in msg for msg in res["issues"])


class TestConversion:
    def test_geojson_conversions(self):
        coords = [(72.8, 19.0), (72.81, 19.0), (72.81, 19.01), (72.8, 19.01), (72.8, 19.0)]
        feat = coords_to_geojson_feature(coords, properties={"ulpin": "TEST-123"}, feature_id="BLD-01")
        assert feat["type"] == "Feature"
        assert feat["id"] == "BLD-01"
        assert feat["properties"]["ulpin"] == "TEST-123"

        coords_extracted = geojson_feature_to_coords(feat)
        assert len(coords_extracted) == len(coords)
        assert coords_extracted[0] == (72.8, 19.0)

        fc = create_geojson_feature_collection([feat])
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1

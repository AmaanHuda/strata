"""Unit tests for the GeoJSON building-import parsing helpers (DB-free).

These cover the shape-handling and repair logic in
app/api/v1/datasets.py so an import can be trusted before PostGIS is involved.
"""
import pytest

from app.api.v1.datasets import (
    _as_float,
    _as_int,
    _largest_polygon,
    _normalise_features,
)
from app.core.errors import ValidationError

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[72.8, 19.2], [72.81, 19.2], [72.81, 19.21], [72.8, 19.21], [72.8, 19.2]]],
}


def _feature(geometry, properties=None):
    return {"type": "Feature", "geometry": geometry, "properties": properties or {}}


class TestNormaliseFeatures:
    def test_feature_collection(self):
        payload = {"type": "FeatureCollection", "features": [_feature(SQUARE), _feature(SQUARE)]}
        assert len(_normalise_features(payload)) == 2

    def test_single_feature(self):
        assert len(_normalise_features(_feature(SQUARE))) == 1

    def test_bare_geometry_becomes_feature(self):
        features = _normalise_features(SQUARE)
        assert len(features) == 1
        assert features[0]["type"] == "Feature"
        assert features[0]["properties"] == {}

    def test_bare_multipolygon(self):
        mp = {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]}
        assert len(_normalise_features(mp)) == 1

    def test_list_of_features(self):
        assert len(_normalise_features([_feature(SQUARE), _feature(SQUARE), _feature(SQUARE)])) == 3

    def test_empty_feature_collection(self):
        assert _normalise_features({"type": "FeatureCollection", "features": []}) == []

    @pytest.mark.parametrize(
        "bad",
        [
            {"type": "Point", "coordinates": [0, 0]},
            {"type": "Unknown"},
            {"not": "geojson"},
            "a string",
            42,
        ],
    )
    def test_unsupported_payloads_raise(self, bad):
        with pytest.raises(ValidationError):
            _normalise_features(bad)


class TestLargestPolygon:
    def test_plain_polygon(self):
        poly = _largest_polygon(SQUARE)
        assert poly.geom_type == "Polygon"
        assert poly.area > 0

    def test_multipolygon_returns_largest_part(self):
        mp = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]],
            ],
        }
        poly = _largest_polygon(mp)
        assert poly.geom_type == "Polygon"
        assert poly.area == pytest.approx(25.0)

    def test_self_intersecting_polygon_is_repaired(self):
        # A "bow-tie" is invalid; buffer(0) repairs it into polygon(s).
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
        }
        poly = _largest_polygon(bowtie)
        assert poly.geom_type == "Polygon"
        assert poly.is_valid
        assert poly.area > 0

    @pytest.mark.parametrize(
        "bad",
        [
            {"type": "Polygon", "coordinates": []},
            {"type": "Point", "coordinates": [0, 0]},
            {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        ],
    )
    def test_rejects_non_polygonal_geometry(self, bad):
        with pytest.raises(ValueError):
            _largest_polygon(bad)


class TestCoercions:
    def test_as_int(self):
        assert _as_int("3") == 3
        assert _as_int(4) == 4
        assert _as_int("") is None
        assert _as_int(None) is None
        assert _as_int("not-a-number") is None
        assert _as_int("nope", 7) == 7

    def test_as_float(self):
        assert _as_float("12.5") == pytest.approx(12.5)
        assert _as_float(None) is None
        assert _as_float("") is None
        assert _as_float("abc", 0.6) == pytest.approx(0.6)

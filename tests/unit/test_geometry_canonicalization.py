"""
Deterministic geometry canonicalization + float bucketing (CANON_V1).

Covers spec test cases A-E:
  A. reversed vertex order -> identical canonical representation
  B. rotated start vertex -> identical canonical representation
  C. equivalent MultiPolygon component ordering -> identical
  D. 21.73 m vs 21.74 m -> same bucket (and therefore the same building ID)
  E. different height bucket -> different bucket key

These are pure-function tests: no database, no network.
"""
import pytest

from app.services.geometry_canonical import (
    CANONICALIZATION_VERSION,
    HEIGHT_BUCKET_M,
    GeometryCanonicalizationError,
    bucket,
    bucket_key,
    canonical_ring_vertices,
    canonicalize_geometry,
    geometry_digest,
    quantize_xy,
)

# A ~2.5 m square parcel near the Taj Mahal Palace Hotel, Apollo Bandar, Mumbai.
SQUARE = [
    [72.8331000, 18.9217000],
    [72.8331300, 18.9217000],
    [72.8331300, 18.9217300],
    [72.8331000, 18.9217300],
    [72.8331000, 18.9217000],
]


def polygon(ring):
    return {"type": "Polygon", "coordinates": [ring]}


# ---------------------------------------------------------------- A + B ----- #


def test_a_reversed_vertex_order_is_identical():
    reversed_ring = list(reversed(SQUARE))
    assert canonicalize_geometry(polygon(SQUARE)) == canonicalize_geometry(
        polygon(reversed_ring)
    )
    assert geometry_digest(polygon(SQUARE)) == geometry_digest(polygon(reversed_ring))


def test_b_rotated_start_vertex_is_identical():
    rotated = SQUARE[2:] + SQUARE[:2]  # start at a different vertex, order kept
    assert canonical_ring_vertices(polygon(SQUARE)) == canonical_ring_vertices(
        polygon(rotated)
    )
    assert canonicalize_geometry(polygon(SQUARE)) == canonicalize_geometry(
        polygon(rotated)
    )


def test_b2_reversed_and_rotated_is_identical():
    rotated_reversed = list(reversed(SQUARE[1:] + SQUARE[:1]))
    assert canonicalize_geometry(polygon(SQUARE)) == canonicalize_geometry(
        polygon(rotated_reversed)
    )


# --------------------------------------------------------------------- C ---- #

POLY_1 = [
    [72.8331000, 18.9217000],
    [72.8331200, 18.9217000],
    [72.8331200, 18.9217200],
    [72.8331000, 18.9217200],
    [72.8331000, 18.9217000],
]
POLY_2 = [
    [72.8331600, 18.9217600],
    [72.8331800, 18.9217600],
    [72.8331800, 18.9217800],
    [72.8331600, 18.9217800],
    [72.8331600, 18.9217600],
]


def multi(*rings):
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}


def test_c_multipolygon_component_order_is_irrelevant():
    a = canonicalize_geometry(multi(POLY_1, POLY_2))
    b = canonicalize_geometry(multi(POLY_2, POLY_1))
    assert a == b
    # Components reversed individually too.
    c = canonicalize_geometry(multi(list(reversed(POLY_2)), list(reversed(POLY_1))))
    assert a == c


# --------------------------------------------------------------- D + E ------ #


def test_d_heights_in_the_same_bucket_are_equal():
    assert bucket(21.73, HEIGHT_BUCKET_M) == bucket(21.74, HEIGHT_BUCKET_M)
    assert bucket_key(21.73, HEIGHT_BUCKET_M) == bucket_key(21.74, HEIGHT_BUCKET_M)
    assert bucket(21.73, HEIGHT_BUCKET_M) == pytest.approx(21.5)


def test_e_different_height_buckets_differ():
    assert bucket_key(21.74, HEIGHT_BUCKET_M) != bucket_key(22.01, HEIGHT_BUCKET_M)
    assert bucket(22.01, HEIGHT_BUCKET_M) == pytest.approx(22.0)
    assert bucket_key(19.21, 0.1) == bucket_key(19.24, 0.1)


def test_bucket_halves_round_away_from_zero_deterministically():
    assert bucket(21.75, 0.5) == pytest.approx(22.0)
    assert bucket(-21.75, 0.5) == pytest.approx(-22.0)
    assert bucket(0.0, 0.5) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        bucket(None, 0.5)
    with pytest.raises(ValueError):
        bucket(10.0, 0)


# ---------------------------------------------------- quantization / edges -- #


def test_xy_quantization_is_symmetric_and_collapses_negative_zero():
    assert quantize_xy(72.833100049999) == 72.8331
    assert quantize_xy(-0.0) == 0.0
    assert quantize_xy(0.0) == 0.0
    assert repr(quantize_xy(-0.0)) == repr(0.0)


def test_axis_order_is_longitude_then_latitude():
    """GeoJSON is [lon, lat]; a transposed geometry must NOT hash the same."""
    normal = polygon(SQUARE)
    transposed = polygon([[lat, lon] for lon, lat in SQUARE])
    assert canonicalize_geometry(normal) != canonicalize_geometry(transposed)


def test_make_valid_repairs_a_self_touching_bowtie():
    bowtie = polygon(
        [
            [72.8331, 18.9217],
            [72.8332, 18.9218],
            [72.8332, 18.9217],
            [72.8331, 18.9218],
            [72.8331, 18.9217],
        ]
    )
    assert "MULTIPOLYGON[" in canonicalize_geometry(bowtie)


def test_holes_are_ordered_deterministically():
    shell = [
        [72.8330, 18.9210],
        [72.8340, 18.9210],
        [72.8340, 18.9220],
        [72.8330, 18.9220],
        [72.8330, 18.9210],
    ]
    hole_a = [
        [72.8332, 18.9212],
        [72.8333, 18.9212],
        [72.8333, 18.9213],
        [72.8332, 18.9213],
        [72.8332, 18.9212],
    ]
    hole_b = [
        [72.8336, 18.9216],
        [72.8337, 18.9216],
        [72.8337, 18.9217],
        [72.8336, 18.9217],
        [72.8336, 18.9216],
    ]
    one = canonicalize_geometry({"type": "Polygon", "coordinates": [shell, hole_a, hole_b]})
    two = canonicalize_geometry(
        {"type": "Polygon", "coordinates": [shell, list(reversed(hole_b)), list(reversed(hole_a))]}
    )
    assert one == two


def test_wkt_and_geojson_agree():
    wkt = "POLYGON((72.8331 18.9217, 72.83313 18.9217, 72.83313 18.92173, 72.8331 18.92173, 72.8331 18.9217))"
    assert canonicalize_geometry(wkt) == canonicalize_geometry(polygon(SQUARE))


def test_empty_and_non_areal_geometry_raise():
    with pytest.raises(GeometryCanonicalizationError):
        canonicalize_geometry({"type": "Point", "coordinates": [72.83, 18.92]})
    with pytest.raises(GeometryCanonicalizationError):
        canonicalize_geometry(None)


def test_canonicalization_version_is_pinned():
    assert CANONICALIZATION_VERSION == "CANON_V1"

"""
Deterministic geometry canonicalization and continuous-value bucketing.

Why this module exists
----------------------
The 3D ULPIN (``app/services/ulpin_3d.py``) is a *deterministic* identifier: the
same physical object with the same inputs must always hash to the same value.
Real inputs, however, are noisy (ML inference, survey rounding, reprojection,
vertex ordering straight out of OSM/PostGIS). Hashing raw float coordinates
would produce a "new" object every time a vertex moved by 1e-12 degrees.

This module defines ONE explicit, versioned normalization contract
(``CANON_V1``) so that:

* the same geometry written in a different vertex order, a different ring start
  vertex, or a different MultiPolygon component order canonicalizes identically;
* continuous ML-derived values are snapped to documented buckets before hashing.

Documented contract (``CANON_V1``)
----------------------------------
CRS / axis order
    Input and output are WGS84 / EPSG:4326. GeoJSON axis order is
    ``[longitude, latitude]`` — this module NEVER swaps the axes.
XY quantization
    Coordinates are quantized to 1e-7 degrees (``XY_QUANTUM_DEG``), i.e. ~1.1 cm
    at the equator, with round-half-away-from-zero (Decimal ``ROUND_HALF_UP``).
    ``-0.0`` and ``0.0`` are normalized to a single representation.
Z / elevation
    Z is never carried inside the geometry hash. Vertical position is hashed
    through explicit ``bucket()`` calls (see below) so a caller must opt in.
Ring orientation
    Exterior rings are normalized counter-clockwise (positive shoelace area),
    interior rings (holes) clockwise. This makes a ring equal to its own
    reverse.
Ring rotation
    Each ring is rotated so the lexicographically smallest ``(lon, lat)``
    coordinate is first (first occurrence wins, to stay unambiguous).
Component ordering
    Polygon components of a MultiPolygon are sorted by their canonical
    serialization, so component order never changes the result.
Non-area components
    Points/lines (including those produced by ``make_valid`` on self-touching
    input) are dropped deterministically.

The canonical serialization is a plain ASCII string, so it can be hashed or
stored directly.
"""
from __future__ import annotations

import hashlib
import math
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from typing import Any, Iterable, Iterator, List, Optional, Sequence, Tuple

CANONICALIZATION_VERSION = "CANON_V1"

# One documented coordinate precision. Do not change without a new CANON version.
COORDINATE_DECIMALS = 7
XY_QUANTUM_DEG = Decimal(1).scaleb(-COORDINATE_DECIMALS)  # 1e-7 degrees

# Bucketing steps for continuous values that enter an identifier hash.
HEIGHT_BUCKET_M = 0.5
Z_BUCKET_M = 0.1
ELEVATION_BUCKET_M = 0.1

# Fixed-point formatting used inside the canonical string.
_XY_FORMAT = f"{{:.{COORDINATE_DECIMALS}f}}"

Coord = Tuple[float, float]


class GeometryCanonicalizationError(ValueError):
    """Raised when geometry cannot be canonicalized (missing/invalid input)."""


# --------------------------------------------------------------------------- #
# Bucketing (shared utility — spec section 9)
# --------------------------------------------------------------------------- #


def bucket(value: Any, step: Any) -> float:
    """
    Deterministically snap ``value`` onto a ``step`` grid and return the bucket
    floor as a float.

    Half-step rule (explicit and versioned): a value exactly halfway between two
    buckets rounds *away from zero* (Decimal ``ROUND_HALF_UP``). ``bucket()`` is
    pure and never uses the ambient float context, so ``21.73`` and ``21.74``
    with ``step=0.5`` both land in ``21.5``.
    """
    if value is None:
        raise ValueError("bucket() received None — a real value is required")
    try:
        d_step = Decimal(repr(float(step)))
        d_value = Decimal(repr(float(value)))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"bucket() received a non-numeric value: {value!r}") from exc
    if d_step <= 0:
        raise ValueError("bucket() step must be > 0")
    if not math.isfinite(float(value)) or not math.isfinite(float(step)):
        raise ValueError("bucket() requires finite inputs")
    with localcontext() as ctx:
        ctx.prec = 40
        steps = (d_value / d_step).to_integral_value(rounding=ROUND_HALF_UP)
        return float(steps * d_step)


def bucket_key(value: Any, step: Any) -> str:
    """Stable string form of ``bucket(value, step)`` for use inside a hash seed."""
    return f"{bucket(value, step):.6f}"


def quantize_xy(value: Any) -> float:
    """Quantize a single coordinate to the documented ``CANON_V1`` XY grid."""
    d = Decimal(repr(float(value))).quantize(XY_QUANTUM_DEG, rounding=ROUND_HALF_UP)
    out = float(d)
    return 0.0 if out == 0 else out  # collapse -0.0 -> 0.0


# --------------------------------------------------------------------------- #
# Geometry -> canonical string
# --------------------------------------------------------------------------- #


def _to_shapely(geometry: Any):
    """Coerce GeoJSON dict / WKT string / shapely geometry into a shapely geom."""
    from shapely.geometry import shape as shapely_shape
    from shapely.geometry.base import BaseGeometry
    from shapely import wkt as shapely_wkt

    if geometry is None:
        raise GeometryCanonicalizationError("no geometry supplied")
    if isinstance(geometry, BaseGeometry):
        return geometry
    if isinstance(geometry, dict):
        if not geometry.get("type"):
            raise GeometryCanonicalizationError("GeoJSON object has no 'type'")
        try:
            return shapely_shape(geometry)
        except Exception as exc:  # malformed GeoJSON
            raise GeometryCanonicalizationError(f"invalid GeoJSON: {exc}") from exc
    if isinstance(geometry, str):
        try:
            return shapely_wkt.loads(geometry)
        except Exception as exc:
            raise GeometryCanonicalizationError(f"invalid WKT: {exc}") from exc
    raise GeometryCanonicalizationError(f"unsupported geometry type: {type(geometry)!r}")


def _make_valid(geom):
    """Run ``make_valid`` where available, falling back to a zero-width buffer."""
    try:
        from shapely import make_valid as shapely_make_valid
    except Exception:  # pragma: no cover - older shapely
        shapely_make_valid = None
    if shapely_make_valid is not None:
        try:
            fixed = shapely_make_valid(geom)
            if fixed is not None and not fixed.is_empty:
                return fixed
        except Exception:
            pass
    try:
        buffered = geom.buffer(0)
        if buffered is not None and not buffered.is_empty:
            return buffered
    except Exception:
        pass
    return geom


def _iter_polygons(geom) -> Iterator[Any]:
    """Yield polygon components deterministically, flattening collections."""
    gtype = getattr(geom, "geom_type", "")
    if gtype == "Polygon":
        yield geom
    elif gtype == "MultiPolygon":
        yield from geom.geoms
    elif gtype == "GeometryCollection":
        for part in geom.geoms:
            yield from _iter_polygons(part)
    # Points / LineStrings / LinearRings carry no cadastral area -> dropped.


def _canonical_ring(coords: Iterable[Sequence[float]], *, ccw: bool) -> List[Coord]:
    """Quantize, de-duplicate, orient and rotate one ring deterministically."""
    points: List[Coord] = []
    for raw in coords:
        if raw is None or len(raw) < 2:
            continue
        pt = (quantize_xy(raw[0]), quantize_xy(raw[1]))
        if not points or points[-1] != pt:
            points.append(pt)
    # Drop the closing duplicate vertex; rings are treated as vertex lists.
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        return []

    # Orient: exterior CCW (positive area), holes CW.
    area2 = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    is_ccw = area2 > 0
    if is_ccw != ccw:
        points = points[::-1]

    # Rotate so the lexicographically smallest coordinate is first.
    start = min(range(len(points)), key=lambda i: points[i])
    if start:
        points = points[start:] + points[:start]
    return points


def _ring_str(ring: Sequence[Coord]) -> str:
    return ",".join(_XY_FORMAT.format(x) + "," + _XY_FORMAT.format(y) for x, y in ring)


def _canonical_polygon(exterior: Sequence[Sequence[float]], holes: Iterable[Any]) -> Optional[str]:
    shell = _canonical_ring(exterior, ccw=True)
    if not shell:
        return None
    hole_rings: List[List[Coord]] = []
    for raw_hole in holes:
        ring = _canonical_ring(raw_hole, ccw=False)
        if ring:
            hole_rings.append(ring)
    hole_rings.sort(key=_ring_str)
    parts = [_ring_str(shell)] + [_ring_str(h) for h in hole_rings]
    return "(" + ",".join(parts) + ")"


def canonicalize_geometry(geometry: Any) -> str:
    """
    Return the deterministic ``CANON_V1`` canonical string for ``geometry``.

    ``geometry`` may be a GeoJSON dict (Polygon/MultiPolygon/GeometryCollection),
    a WKT string, or a shapely geometry. Raises
    :class:`GeometryCanonicalizationError` when no polygonal area survives.
    """
    geom = _to_shapely(geometry)
    if geom.is_empty:
        raise GeometryCanonicalizationError("geometry is empty")
    geom = _make_valid(geom)

    polygons: List[str] = []
    for poly in _iter_polygons(geom):
        canonical = _canonical_polygon(poly.exterior.coords, [r.coords for r in poly.interiors])
        if canonical:
            polygons.append(canonical)
    if not polygons:
        raise GeometryCanonicalizationError(
            "geometry contains no polygonal area after canonicalization"
        )
    polygons.sort()
    return "MULTIPOLYGON[" + ";".join(polygons) + "]"


def geometry_digest(geometry: Any, version: str = CANONICALIZATION_VERSION) -> str:
    """SHA-256 of ``version:canonical`` — a stable, non-identifying geometry hash."""
    canonical = canonicalize_geometry(geometry)
    return hashlib.sha256(f"{version}:{canonical}".encode("utf-8")).hexdigest()


def canonical_ring_vertices(geometry: Any) -> List[List[float]]:
    """
    Canonical exterior vertices of the largest polygon, as ``[[lon, lat], ...]``.

    Used by tests and diagnostics to prove vertex-order independence without
    re-parsing the canonical string.
    """
    geom = _make_valid(_to_shapely(geometry))
    best: List[Coord] = []
    best_area = -1.0
    for poly in _iter_polygons(geom):
        ring = _canonical_ring(poly.exterior.coords, ccw=True)
        if not ring:
            continue
        area2 = 0.0
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            area2 += x1 * y2 - x2 * y1
        if abs(area2) > best_area:
            best_area = abs(area2)
            best = ring
    return [[x, y] for x, y in best]


def height_bucket_key(height_m: Any) -> str:
    """Bucket key for a building height (0.5 m) — the ``3D_GEOMETRY_HASH_V1`` rule."""
    return bucket_key(height_m, HEIGHT_BUCKET_M)


def z_bucket_key(z_value: Any) -> str:
    """Bucket key for a vertical position (0.1 m)."""
    return bucket_key(z_value, Z_BUCKET_M)


__all__ = [
    "CANONICALIZATION_VERSION",
    "COORDINATE_DECIMALS",
    "XY_QUANTUM_DEG",
    "HEIGHT_BUCKET_M",
    "Z_BUCKET_M",
    "ELEVATION_BUCKET_M",
    "GeometryCanonicalizationError",
    "bucket",
    "bucket_key",
    "quantize_xy",
    "canonicalize_geometry",
    "geometry_digest",
    "canonical_ring_vertices",
    "height_bucket_key",
    "z_bucket_key",
]

"""
Spatial operations and geometric calculations for building footprints and parcels.
SIH 2026 PS 26011 - ML Engine
"""
import math
from typing import List, Tuple, Dict, Any
from src.geospatial.crs import approximate_utm_forward


def compute_bounding_box(coords: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    if not coords:
        raise ValueError("Cannot compute bounding box of empty coordinates.")
    xs = [pt[0] for pt in coords]
    ys = [pt[1] for pt in coords]
    return (min(xs), min(ys), max(xs), max(ys))


def calculate_polygon_area(coords: List[Tuple[float, float]], crs: str = "EPSG:4326") -> float:
    if len(coords) < 3:
        return 0.0

    pts = list(coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    if crs.upper() == "EPSG:4326":
        metric_pts = [approximate_utm_forward(lon, lat) for lon, lat in pts]
    else:
        metric_pts = pts

    n = len(metric_pts)
    area = 0.0
    for i in range(n - 1):
        x1, y1 = metric_pts[i]
        x2, y2 = metric_pts[i + 1]
        area += (x1 * y2 - x2 * y1)

    return abs(area) / 2.0


def calculate_perimeter(coords: List[Tuple[float, float]], crs: str = "EPSG:4326") -> float:
    if len(coords) < 2:
        return 0.0

    pts = list(coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    if crs.upper() == "EPSG:4326":
        metric_pts = [approximate_utm_forward(lon, lat) for lon, lat in pts]
    else:
        metric_pts = pts

    perimeter = 0.0
    for i in range(len(metric_pts) - 1):
        x1, y1 = metric_pts[i]
        x2, y2 = metric_pts[i + 1]
        perimeter += math.hypot(x2 - x1, y2 - y1)

    return perimeter


def calculate_compactness(coords: List[Tuple[float, float]], crs: str = "EPSG:4326") -> float:
    area = calculate_polygon_area(coords, crs=crs)
    perimeter = calculate_perimeter(coords, crs=crs)
    if perimeter <= 0.0:
        return 0.0
    return min(1.0, max(0.0, (4.0 * math.pi * area) / (perimeter * perimeter)))


def calculate_centroid(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
    if not coords:
        raise ValueError("Cannot calculate centroid of empty coordinate list.")
    pts = list(coords)
    if pts[0] == pts[-1] and len(pts) > 1:
        pts = pts[:-1]

    n = len(pts)
    if n == 1:
        return pts[0]

    area_accum = 0.0
    cx_accum = 0.0
    cy_accum = 0.0

    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        area_accum += cross
        cx_accum += (x0 + x1) * cross
        cy_accum += (y0 + y1) * cross

    if abs(area_accum) < 1e-12:
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)

    a = area_accum * 3.0
    return (cx_accum / a, cy_accum / a)


def _on_segment(
    point: Tuple[float, float],
    a: Tuple[float, float],
    b: Tuple[float, float],
    tolerance: float,
) -> bool:
    """True when `point` lies on the segment a-b within `tolerance`."""
    px, py = point
    ax, ay = a
    bx, by = b
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > tolerance * max(1.0, abs(bx - ax) + abs(by - ay)):
        return False
    return (
        min(ax, bx) - tolerance <= px <= max(ax, bx) + tolerance
        and min(ay, by) - tolerance <= py <= max(ay, by) + tolerance
    )


def point_in_polygon(
    point: Tuple[float, float],
    polygon_coords: List[Tuple[float, float]],
    tolerance: float = 1e-9,
) -> bool:
    """
    Ray-casting containment test.

    Points that lie exactly on the boundary (a shared vertex or edge — e.g. a
    footprint derived from its own parcel) count as inside. The previous
    implementation iterated ``range(n + 1)`` over an already-closed ring, so
    every edge after the first was traversed twice and the inside/outside parity
    flipped back; a polygon was then reported as having its own vertices outside
    itself.
    """
    x, y = point
    ring = list(polygon_coords)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    n = len(ring)
    if n < 3:
        return False

    inside = False
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if _on_segment((x, y), (x1, y1), (x2, y2), tolerance):
            return True
        if (y1 > y) != (y2 > y):
            xinters = (y - y1) * (x2 - x1) / (y2 - y1) + x1
            if x <= xinters:
                inside = not inside

    return inside

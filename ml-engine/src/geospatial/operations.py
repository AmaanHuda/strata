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


def point_in_polygon(point: Tuple[float, float], polygon_coords: List[Tuple[float, float]]) -> bool:
    x, y = point
    pts = list(polygon_coords)
    n = len(pts)
    inside = False

    p1x, p1y = pts[0]
    for i in range(n + 1):
        p2x, p2y = pts[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside

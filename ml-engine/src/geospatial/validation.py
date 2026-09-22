"""
Spatial & topological validation of building and unit polygons.
SIH 2026 PS 26011 - ML Engine
"""
import math
from typing import List, Tuple, Dict, Any
from src.geospatial.operations import calculate_polygon_area
from src.geospatial.crs import is_within_india_bbox


def _segments_intersect(p1: Tuple[float, float], p2: Tuple[float, float],
                        p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))


def check_self_intersection(coords: List[Tuple[float, float]]) -> bool:
    pts = list(coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    n = len(pts) - 1
    if n < 4:
        return False

    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_intersect(pts[i], pts[i+1], pts[j], pts[j+1]):
                return True
    return False


def validate_polygon_geometry(
    coords: List[Tuple[float, float]],
    min_area_sqm: float = 1.0,
    crs: str = "EPSG:4326",
    check_india_bounds: bool = True
) -> Dict[str, Any]:
    issues = []
    status = "VALID"

    if not coords or len(coords) < 3:
        return {
            "status": "INVALID",
            "is_valid": False,
            "issues": ["Polygon must contain at least 3 distinct vertices."],
            "area_sqm": 0.0
        }

    pts = list(coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    if len(pts) < 4:
        return {
            "status": "INVALID",
            "is_valid": False,
            "issues": ["Closed polygon must have at least 4 coordinate entries."],
            "area_sqm": 0.0
        }

    for i, (x, y) in enumerate(pts):
        if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
            issues.append(f"Vertex {i} contains NaN or Inf.")

    if check_india_bounds and crs.upper() == "EPSG:4326":
        for i, (lon, lat) in enumerate(pts[:-1]):
            if not is_within_india_bbox(lon, lat):
                issues.append(f"Vertex {i} ({lon}, {lat}) is outside India geographic envelope.")
                break

    if check_self_intersection(pts):
        issues.append("Polygon perimeter is self-intersecting.")

    area = calculate_polygon_area(pts, crs=crs)
    if area < min_area_sqm:
        issues.append(f"Polygon area ({area:.2f} m^2) is below minimum threshold ({min_area_sqm:.2f} m^2).")

    is_valid = len(issues) == 0
    if not is_valid:
        status = "INVALID"

    return {
        "status": status,
        "is_valid": is_valid,
        "issues": issues,
        "area_sqm": round(area, 4)
    }

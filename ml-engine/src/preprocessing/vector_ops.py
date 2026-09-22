"""
Vector polygon simplification, orthogonalization, and topology repair.
SIH 2026 PS 26011 - ML Engine
"""
import math
from typing import List, Tuple


def _perpendicular_distance(point: Tuple[float, float], line_start: Tuple[float, float], line_end: Tuple[float, float]) -> float:
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def simplify_polygon_rdp(coords: List[Tuple[float, float]], tolerance: float = 1.0) -> List[Tuple[float, float]]:
    if len(coords) < 4:
        return list(coords)

    is_closed = (coords[0] == coords[-1])
    pts = list(coords[:-1]) if is_closed else list(coords)

    def _rdp(point_list):
        if len(point_list) < 3:
            return point_list
        dmax = 0.0
        index = 0
        for i in range(1, len(point_list) - 1):
            d = _perpendicular_distance(point_list[i], point_list[0], point_list[-1])
            if d > dmax:
                index = i
                dmax = d
        if dmax > tolerance:
            rec_results1 = _rdp(point_list[:index + 1])
            rec_results2 = _rdp(point_list[index:])
            return rec_results1[:-1] + rec_results2
        else:
            return [point_list[0], point_list[-1]]

    simplified = _rdp(pts)
    if is_closed and (simplified[0] != simplified[-1]):
        simplified.append(simplified[0])
    return simplified


def remove_duplicate_consecutive_vertices(coords: List[Tuple[float, float]], eps: float = 1e-7) -> List[Tuple[float, float]]:
    if not coords:
        return []
    result = [coords[0]]
    for pt in coords[1:]:
        last = result[-1]
        if math.hypot(pt[0] - last[0], pt[1] - last[1]) > eps:
            result.append(pt)
    return result

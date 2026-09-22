import json
from typing import List, Tuple, Dict, Any, Optional


def export_to_geojson_polygonz(
    building_id: str,
    ulpin: str,
    footprint_coords: List[Tuple[float, float]],
    height_m: float,
    base_elevation_m: float = 0.0,
    crs: str = "EPSG:4326"
) -> Dict[str, Any]:
    pts_base = [[float(pt[0]), float(pt[1]), round(base_elevation_m, 2)] for pt in footprint_coords]
    pts_top = [[float(pt[0]), float(pt[1]), round(base_elevation_m + height_m, 2)] for pt in footprint_coords]

    return {
        "type": "Feature",
        "id": building_id,
        "properties": {
            "official_ulpin": ulpin,
            "height_m": round(height_m, 2),
            "base_elevation_m": round(base_elevation_m, 2),
            "top_elevation_m": round(base_elevation_m + height_m, 2),
            "geometry_crs": crs
        },
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [pts_base],
                [pts_top]
            ]
        }
    }


def export_to_cityjson(
    building_id: str,
    ulpin: str,
    footprint_coords: List[Tuple[float, float]],
    height_m: float,
    base_elevation_m: float = 0.0,
    crs_epsg: int = 4326
) -> Dict[str, Any]:
    pts = list(footprint_coords)
    if pts[0] == pts[-1] and len(pts) > 1:
        pts = pts[:-1]

    n = len(pts)
    z_base = round(base_elevation_m, 2)
    z_top = round(base_elevation_m + height_m, 2)

    vertices = []
    for x, y in pts:
        vertices.append([float(x), float(y), z_base])
    for x, y in pts:
        vertices.append([float(x), float(y), z_top])

    boundaries = []
    boundaries.append([[i for i in reversed(range(n))]])
    boundaries.append([[n + i for i in range(n)]])
    for i in range(n):
        next_i = (i + 1) % n
        boundaries.append([[i, next_i, n + next_i, n + i]])

    cityjson = {
        "type": "CityJSON",
        "version": "1.1",
        "metadata": {
            "referenceSystem": f"https://www.opengis.net/def/crs/EPSG/0/{crs_epsg}",
            "title": f"3D Cadastral LoD1 Building Model - ULPIN {ulpin}"
        },
        "CityObjects": {
            building_id: {
                "type": "Building",
                "attributes": {
                    "official_ulpin": ulpin,
                    "measuredHeight": round(height_m, 2),
                    "storeysAboveGround": max(1, int(round(height_m / 3.0)))
                },
                "geometry": [
                    {
                        "type": "Solid",
                        "lod": "1.2",
                        "boundaries": [boundaries]
                    }
                ]
            }
        },
        "vertices": vertices
    }
    return cityjson


def export_to_wavefront_obj(
    footprint_coords: List[Tuple[float, float]],
    height_m: float,
    base_elevation_m: float = 0.0,
    object_name: str = "CadastralBuilding"
) -> str:
    pts = list(footprint_coords)
    if pts[0] == pts[-1] and len(pts) > 1:
        pts = pts[:-1]

    n = len(pts)
    z_base = base_elevation_m
    z_top = base_elevation_m + height_m

    lines = [f"# SIH 2026 PS 26011 - 3D Property Volume", f"o {object_name}"]

    for x, y in pts:
        lines.append(f"v {x:.6f} {y:.6f} {z_base:.2f}")
    for x, y in pts:
        lines.append(f"v {x:.6f} {y:.6f} {z_top:.2f}")

    bottom_indices = " ".join(str(i) for i in reversed(range(1, n + 1)))
    lines.append(f"f {bottom_indices}")

    top_indices = " ".join(str(n + i) for i in range(1, n + 1))
    lines.append(f"f {top_indices}")

    for i in range(1, n + 1):
        next_i = 1 if i == n else (i + 1)
        lines.append(f"f {i} {next_i} {n + next_i} {n + i}")

    return chr(10).join(lines)

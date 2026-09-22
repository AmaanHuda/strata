"""
Metadata parser for point cloud data (LAS/LAZ/DEM).
SIH 2026 PS 26011 - ML Engine
"""
from typing import Dict, Any


def create_pointcloud_metadata_summary(
    point_count: int,
    bbox: tuple,
    crs: str = "EPSG:32643",
    point_format: int = 3,
    version: str = "1.4"
) -> Dict[str, Any]:
    min_x, min_y, min_z, max_x, max_y, max_z = bbox
    area_sqm = max(1.0, (max_x - min_x) * (max_y - min_y))
    density = point_count / area_sqm

    return {
        "point_count": int(point_count),
        "point_format": int(point_format),
        "version": version,
        "crs": crs,
        "bounds": {
            "min_x": float(min_x),
            "max_x": float(max_x),
            "min_y": float(min_y),
            "max_y": float(max_y),
            "min_z": float(min_z),
            "max_z": float(max_z),
        },
        "density_points_per_sqm": round(density, 4),
        "coverage_area_sqm": round(area_sqm, 2)
    }

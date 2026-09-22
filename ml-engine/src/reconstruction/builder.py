"""
3D Property Volume Geometry Reconstruction Engine.
SIH 2026 PS 26011 - ML Engine
"""
from typing import List, Tuple, Dict, Any, Optional
import uuid
from src.geospatial.validation import validate_polygon_geometry
from src.geospatial.crs import get_utm_epsg_for_coordinates, transform_coordinates
from src.geospatial.operations import calculate_polygon_area


class VolumeReconstructionEngine:
    """
    Reconstructs candidate 3D volumes (PolygonZ / extrusions) with explicit CRS,
    elevation ranges, and strict geometric validity checking.
    """
    def __init__(self, floor_height_m: float = 3.0):
        self.floor_height_m = floor_height_m

    def build_building_volume(
        self,
        ulpin: str,
        building_id: str,
        footprint_coords: List[Tuple[float, float]],
        height_m: float,
        base_elevation_m: float = 0.0,
        source_crs: str = "EPSG:4326",
        output_crs: Optional[str] = None
    ) -> Dict[str, Any]:
        target_output_crs = output_crs or source_crs
        
        # 1. Geometry validity check
        geom_val = validate_polygon_geometry(footprint_coords, crs=source_crs)
        if not geom_val["is_valid"]:
            return {
                "type": "BuildingVolume",
                "official_ulpin": ulpin,
                "building_id": building_id,
                "status": "INVALID_GEOMETRY",
                "issues": geom_val["issues"],
                "source_crs": source_crs,
                "processing_crs": None,
                "output_crs": target_output_crs,
                "geometry": None
            }

        # 2. Determine local projected processing CRS for metric volume calculations
        if source_crs.upper() == "EPSG:4326":
            center_lon = sum(p[0] for p in footprint_coords) / len(footprint_coords)
            center_lat = sum(p[1] for p in footprint_coords) / len(footprint_coords)
            processing_crs = get_utm_epsg_for_coordinates(center_lon, center_lat)
        else:
            processing_crs = source_crs

        # 3. Calculate metric area and volume in projected CRS
        metric_area = geom_val.get("area_sqm", 0.0)
        volume_m3 = round(metric_area * height_m, 2)

        z_min = round(base_elevation_m, 2)
        z_max = round(base_elevation_m + height_m, 2)

        # Coordinate transformation if output CRS differs from source CRS
        if target_output_crs.upper() != source_crs.upper():
            out_coords = transform_coordinates(footprint_coords, source_crs, target_output_crs)
        else:
            out_coords = list(footprint_coords)

        pts_3d = []
        for pt in out_coords:
            pts_3d.append([float(pt[0]), float(pt[1]), z_max])

        return {
            "type": "BuildingVolume",
            "official_ulpin": ulpin,
            "building_id": building_id,
            "source_crs": source_crs,
            "processing_crs": processing_crs,
            "output_crs": target_output_crs,
            "crs": target_output_crs,
            "base_elevation_m": z_min,
            "top_elevation_m": z_max,
            "height_m": round(height_m, 2),
            "footprint_area_sqm": round(metric_area, 2),
            "volume_m3": volume_m3,
            "geometry_status": "VALID",
            "geometry": {
                "type": "Polygon",
                "coordinates": [pts_3d]
            }
        }

    def generate_candidate_volume_id(self, ulpin: str, floor_id: Optional[str] = None, unit_id: Optional[str] = None) -> str:
        parts = ["VOL", ulpin.replace(" ", "-")]
        if floor_id:
            parts.append(floor_id)
        if unit_id:
            parts.append(unit_id)
        return "-".join(parts)


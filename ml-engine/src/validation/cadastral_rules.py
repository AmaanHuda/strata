"""
Cadastral & Spatial Rule Engine.
SIH 2026 PS 26011 - ML Engine
"""
from typing import List, Tuple, Dict, Any, Optional
from src.geospatial.validation import validate_polygon_geometry
from src.geospatial.operations import point_in_polygon, calculate_polygon_area


class CadastralRuleEngine:
    """
    Validates spatial and topological constraints between building, parcel, and unit geometries.
    """
    def __init__(self, min_building_area_sqm: float = 10.0):
        self.min_building_area_sqm = min_building_area_sqm

    def validate_building_against_parcel(
        self,
        building_coords: List[Tuple[float, float]],
        parcel_coords: List[Tuple[float, float]],
        crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        issues = []

        # 1. Validate building geometry
        bldg_val = validate_polygon_geometry(building_coords, min_area_sqm=self.min_building_area_sqm, crs=crs)
        if not bldg_val["is_valid"]:
            issues.extend(bldg_val["issues"])

        # 2. Check if building vertices are inside parcel
        outside_count = 0
        for pt in building_coords[:-1]:
            if not point_in_polygon(pt, parcel_coords):
                outside_count += 1

        if outside_count > 0:
            issues.append(f"Building footprint encroaches outside parcel boundary ({outside_count} vertices outside).")

        status = "VALID" if not issues else ("REVIEW_REQUIRED" if outside_count > 0 else "INVALID")

        return {
            "status": status,
            "is_valid": len(issues) == 0,
            "issues": issues,
            "building_area_sqm": bldg_val.get("area_sqm", 0.0)
        }

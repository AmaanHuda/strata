"""
3D Strata Property Unit Spatial Partitioner.
SIH 2026 PS 26011 - Task 5: 3D Unit Delineation & Cadastral Subdivision
"""
from typing import List, Tuple, Dict, Any, Optional
import math
from src.geospatial.operations import calculate_polygon_area, compute_bounding_box


class StrataUnitPartitioner:
    """
    Partitions building floor volumes into individual 3D strata units, common areas, and vertical access.
    """
    def __init__(self, floor_height_m: float = 3.0):
        self.floor_height_m = floor_height_m

    def partition_floor_into_units(
        self,
        ulpin: str,
        building_id: str,
        floor_level: int,
        footprint_coords: List[Tuple[float, float]],
        unit_count_per_floor: int = 2,
        base_elevation_m: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Subdivides a floor into candidate 3D apartment/strata unit volumes with elevation bounds [z_min, z_max].
        """
        z_min = round(base_elevation_m + (floor_level - 1) * self.floor_height_m, 2)
        z_max = round(z_min + self.floor_height_m, 2)
        floor_id = f"FL-{floor_level:02d}"

        pts = list(footprint_coords)
        if pts[0] == pts[-1] and len(pts) > 1:
            pts = pts[:-1]

        min_x, min_y, max_x, max_y = compute_bounding_box(pts)
        dx = max_x - min_x
        dy = max_y - min_y

        units = []

        if unit_count_per_floor <= 1:
            # Single unit takes full floor
            unit_id = f"UNIT-{floor_level:02d}01"
            volume_id = f"VOL-{ulpin}-{floor_id}-{unit_id}"
            units.append({
                "official_ulpin": ulpin,
                "building_id": building_id,
                "floor_id": floor_id,
                "floor_level": floor_level,
                "unit_id": unit_id,
                "volume_id": volume_id,
                "unit_type": "RESIDENTIAL_FULL_FLOOR",
                "z_min_m": z_min,
                "z_max_m": z_max,
                "height_m": self.floor_height_m,
                "geometry": footprint_coords,
                "evidence": "FULL_FLOOR_FOOTPRINT_EXTRUSION",
                "confidence": 0.65,
                "validation_status": "VALID",
                "source_status": "CANDIDATE_VERTICAL_UNIT_GENERATION",
                "unit_ground_truth_status": "UNAVAILABLE",
                "data_status": "INFERRED"
            })
            return units

        # Split bounding box along major axis
        for u in range(unit_count_per_floor):
            unit_no = f"{floor_level:02d}{u+1:02d}"
            unit_id = f"UNIT-{unit_no}"
            volume_id = f"VOL-{ulpin}-{floor_id}-{unit_id}"

            if dx >= dy:
                # Split along X axis
                ux1 = min_x + (u / unit_count_per_floor) * dx
                ux2 = min_x + ((u + 1) / unit_count_per_floor) * dx
                uy1, uy2 = min_y, max_y
            else:
                # Split along Y axis
                ux1, ux2 = min_x, max_x
                uy1 = min_y + (u / unit_count_per_floor) * dy
                uy2 = min_y + ((u + 1) / unit_count_per_floor) * dy

            unit_poly = [(ux1, uy1), (ux2, uy1), (ux2, uy2), (ux1, uy2), (ux1, uy1)]
            area = calculate_polygon_area(unit_poly)

            units.append({
                "official_ulpin": ulpin,
                "building_id": building_id,
                "floor_id": floor_id,
                "floor_level": floor_level,
                "unit_id": unit_id,
                "volume_id": volume_id,
                "unit_type": f"RESIDENTIAL_UNIT_{u+1}",
                "z_min_m": z_min,
                "z_max_m": z_max,
                "height_m": self.floor_height_m,
                "estimated_area_sqm": round(area, 2),
                "geometry": unit_poly,
                "evidence": "MAJOR_AXIS_BBOX_SUBDIVISION",
                "confidence": 0.55,
                "validation_status": "VALID",
                "source_status": "CANDIDATE_VERTICAL_UNIT_GENERATION",
                "unit_ground_truth_status": "UNAVAILABLE",
                "data_status": "INFERRED"
            })

        return units


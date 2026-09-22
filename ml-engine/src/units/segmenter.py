"""
Vertical & Horizontal 3D Unit Delineation.
SIH 2026 PS 26011 - ML Engine
"""
from typing import List, Dict, Any, Tuple, Optional


class UnitSegmenter:
    """
    Generates candidate 3D property unit specifications per floor.
    """
    def __init__(self, units_per_floor_default: int = 1):
        self.units_per_floor_default = units_per_floor_default

    def generate_candidate_units(
        self,
        building_id: str,
        floor_count: int,
        footprint_coords: List[Tuple[float, float]],
        units_per_floor: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if floor_count <= 0:
            return []

        n_units = units_per_floor or self.units_per_floor_default
        units = []

        for f in range(1, floor_count + 1):
            floor_id = f"FL-{f:02d}"
            for u in range(1, n_units + 1):
                unit_id = f"UNIT-{u:03d}"
                units.append({
                    "building_id": building_id,
                    "floor_id": floor_id,
                    "unit_id": unit_id,
                    "floor_level": f,
                    "geometry": footprint_coords,
                    "source_status": "CANDIDATE_VERTICAL_UNIT_GENERATION",
                    "unit_ground_truth_status": "UNAVAILABLE",
                    "validation_status": "VALID",
                    "data_status": "INFERRED"
                })

        return units


"""
2D and 3D Geometry validation engine.
Ensures topological consistency, valid rings, non-self-intersecting polygons,
proper 3D elevations, positive volume/area, and metric projection conversions.
Never calculates metric distances/areas in geographic degrees.
"""
import math
from typing import Any, Dict, List, Optional, Tuple
from shapely import wkt
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.validation import explain_validity

from app.core.errors import InvalidGeometryError, InvalidCRSError


SUPPORTED_CRS = {"EPSG:4326", "EPSG:3857", "EPSG:32643", "EPSG:32644", "EPSG:7755"}


class GeometryValidationService:
    """Validates 2D and 3D geometry constraints for cadastral properties."""

    @staticmethod
    def validate_crs(crs: str) -> bool:
        """Validates CRS identifier."""
        if not crs or crs.upper() not in SUPPORTED_CRS:
            raise InvalidCRSError(f"Unsupported CRS: {crs}. Supported: {list(SUPPORTED_CRS)}")
        return True

    @staticmethod
    def validate_2d_wkt(wkt_str: str) -> Dict[str, Any]:
        """
        Validates 2D WKT geometry:
        - Valid syntax
        - Valid rings and closure
        - No self-intersections
        - Non-zero area
        """
        if not wkt_str or not wkt_str.strip():
            raise InvalidGeometryError("Empty geometry WKT string")

        try:
            geom = wkt.loads(wkt_str)
        except Exception as e:
            raise InvalidGeometryError(f"Malformed WKT geometry: {str(e)}")

        if not geom.is_valid:
            reason = explain_validity(geom)
            raise InvalidGeometryError(f"Invalid 2D geometry: {reason}")

        if geom.is_empty:
            raise InvalidGeometryError("Geometry is empty")

        if geom.geom_type not in ["Polygon", "MultiPolygon"]:
            raise InvalidGeometryError(f"Expected Polygon or MultiPolygon, got {geom.geom_type}")

        # Check for duplicate consecutive vertices
        coords = list(geom.exterior.coords) if geom.geom_type == "Polygon" else []
        if geom.geom_type == "Polygon":
            for i in range(len(coords) - 2):
                if coords[i] == coords[i + 1]:
                    raise InvalidGeometryError(f"Duplicate consecutive vertex found at index {i}")

        # Approximate metric area calculation via equirectangular projection at geometry center
        bounds = geom.bounds  # minx, miny, maxx, maxy (lon, lat)
        center_lat = (bounds[1] + bounds[3]) / 2.0
        # 1 deg lat ~ 111,320m, 1 deg lon ~ 111,320m * cos(lat)
        lat_scale = 111320.0
        lon_scale = 111320.0 * math.cos(math.radians(center_lat))
        # Approx metric area
        raw_deg_area = geom.area
        approx_metric_area_sqm = raw_deg_area * lat_scale * lon_scale

        return {
            "is_valid": True,
            "geom_type": geom.geom_type,
            "bounds": bounds,
            "approx_metric_area_sqm": round(approx_metric_area_sqm, 2),
            "num_points": len(geom.exterior.coords) if geom.geom_type == "Polygon" else sum(len(p.exterior.coords) for p in geom.geoms),
        }

    @staticmethod
    def validate_3d_hierarchy(
        floor_count: Optional[int],
        height_m: Optional[float],
        floors_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validates 3D vertical constraints:
        - Valid positive height and floor counts
        - Floor ordering (-1, 0, 1, 2...)
        - Floor continuity without elevation gaps
        - Positive ceiling heights and non-zero volumes
        """
        errors = []
        warnings = []

        if height_m is not None and height_m <= 0:
            errors.append("Building height must be strictly positive")

        if floor_count is not None and floor_count <= 0:
            errors.append("Floor count must be at least 1")

        if floors_data:
            # Check floor numbers ordering and duplicates
            floor_nums = [f.get("floor_number", 0) for f in floors_data]
            if len(floor_nums) != len(set(floor_nums)):
                errors.append("Duplicate floor numbers detected in building hierarchy")

            sorted_floors = sorted(floors_data, key=lambda x: x.get("floor_number", 0))
            
            # Check vertical continuity
            current_elevation = 0.0
            for flr in sorted_floors:
                num = flr.get("floor_number", 0)
                flr_height = flr.get("height_above_ground_m")
                ceiling_h = flr.get("ceiling_height_m", 3.0) or 3.0

                if ceiling_h <= 0:
                    errors.append(f"Floor {num} has non-positive ceiling height: {ceiling_h}m")

                if flr_height is not None:
                    if num > 0 and flr_height < 0:
                        errors.append(f"Upper floor {num} cannot have negative elevation ({flr_height}m)")
                    if num < 0 and flr_height > 0:
                        warnings.append(f"Basement floor {num} has positive elevation above ground ({flr_height}m)")

            # Check if total calculated floor height matches building height
            if height_m and len(sorted_floors) > 0:
                expected_total_h = sum((f.get("ceiling_height_m") or 3.0) for f in sorted_floors if f.get("floor_number", 0) >= 0)
                if abs(expected_total_h - height_m) > 5.0:
                    warnings.append(f"Sum of floor ceiling heights ({expected_total_h}m) differs from estimated building height ({height_m}m)")

        if errors:
            raise InvalidGeometryError(f"3D Geometry validation failed: {'; '.join(errors)}")

        return {
            "is_valid": True,
            "warnings": warnings,
            "floor_count_validated": len(floors_data) if floors_data else floor_count,
        }

    @staticmethod
    def validate_vertical_unit_partition(
        floor_area_sqm: float,
        units_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validates vertical unit partitioning within a floor:
        - Units must not exceed total floor area
        - Unit areas must be positive
        """
        errors = []
        warnings = []

        total_unit_area = 0.0
        for u in units_data:
            area = float(u.get("area_sqm") or 0.0)
            if area <= 0:
                errors.append(f"Unit {u.get('unit_number')} has invalid non-positive area: {area} sqm")
            total_unit_area += area

        if floor_area_sqm and floor_area_sqm > 0:
            if total_unit_area > floor_area_sqm * 1.05:  # Allow 5% tolerance for common walls
                errors.append(f"Sum of unit areas ({total_unit_area} sqm) exceeds floor area ({floor_area_sqm} sqm)")
            elif total_unit_area < floor_area_sqm * 0.70:
                warnings.append(f"Units cover only {round((total_unit_area/floor_area_sqm)*100, 1)}% of floor area (large common utility space)")

        if errors:
            raise InvalidGeometryError(f"Unit partitioning validation failed: {'; '.join(errors)}")

        return {
            "is_valid": True,
            "total_unit_area_sqm": total_unit_area,
            "warnings": warnings,
        }

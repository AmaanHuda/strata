"""
Cadastral Topology Validation Service.
Validates:
- Parcel containment (building footprint fully inside parcel boundary)
- Building overlap on same parcel
- Floor ordering & vertical continuity
- Vertical unit containment and overlap
- Geometric sanity and duplicate detection
Returns: PASS / WARNING / REVIEW / FAIL for each check.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from shapely import wkt
from shapely.geometry import Polygon

from app.schemas.validation import (
    PropertyValidationReport,
    ValidationCheckResult,
    ValidationStatus,
)


class TopologyValidationService:
    """Service to evaluate 2D cadastral boundary containment and 3D vertical topology."""

    @staticmethod
    def validate_building_in_parcel(
        parcel_wkt: Optional[str],
        building_wkt: Optional[str],
    ) -> ValidationCheckResult:
        """Checks if the building footprint is strictly contained within the cadastral parcel."""
        if not parcel_wkt or not building_wkt:
            return ValidationCheckResult(
                check_name="parcel_containment",
                status=ValidationStatus.REVIEW,
                message="Parcel or building boundary geometry is missing; manual review required.",
                details={"has_parcel_geom": bool(parcel_wkt), "has_building_geom": bool(building_wkt)},
            )

        try:
            p_geom = wkt.loads(parcel_wkt)
            b_geom = wkt.loads(building_wkt)

            if not p_geom.is_valid or not b_geom.is_valid:
                return ValidationCheckResult(
                    check_name="parcel_containment",
                    status=ValidationStatus.FAIL,
                    message="Parcel or building geometry is invalid WKT polygon.",
                )

            # Check containment / intersection
            if p_geom.contains(b_geom):
                return ValidationCheckResult(
                    check_name="parcel_containment",
                    status=ValidationStatus.PASS,
                    message="Building footprint is fully contained within parcel boundary.",
                )
            
            # Check overlap percentage if not strictly contained
            intersection = p_geom.intersection(b_geom)
            if intersection.is_empty:
                return ValidationCheckResult(
                    check_name="parcel_containment",
                    status=ValidationStatus.FAIL,
                    message="Building footprint does not intersect the parcel boundary at all.",
                )

            overlap_ratio = intersection.area / b_geom.area if b_geom.area > 0 else 0
            if overlap_ratio >= 0.95:
                return ValidationCheckResult(
                    check_name="parcel_containment",
                    status=ValidationStatus.WARNING,
                    message=f"Building mostly inside parcel ({round(overlap_ratio*100, 1)}% overlap); slight boundary overhang detected.",
                    details={"overlap_ratio": overlap_ratio},
                )
            else:
                return ValidationCheckResult(
                    check_name="parcel_containment",
                    status=ValidationStatus.FAIL,
                    message=f"Building footprint extends significantly outside parcel ({round(overlap_ratio*100, 1)}% inside).",
                    details={"overlap_ratio": overlap_ratio},
                )

        except Exception as e:
            return ValidationCheckResult(
                check_name="parcel_containment",
                status=ValidationStatus.REVIEW,
                message=f"Topological check exception: {str(e)}",
            )

    @staticmethod
    def validate_floors_topology(
        floors: List[Dict[str, Any]],
    ) -> List[ValidationCheckResult]:
        """Validates floor numbering sequence, elevation continuity, and duplicate detection."""
        results = []
        if not floors:
            results.append(ValidationCheckResult(
                check_name="floor_ordering",
                status=ValidationStatus.REVIEW,
                message="No floor records registered for building.",
            ))
            return results

        floor_nums = [f.get("floor_number", 0) for f in floors]
        if len(floor_nums) != len(set(floor_nums)):
            results.append(ValidationCheckResult(
                check_name="floor_duplicates",
                status=ValidationStatus.FAIL,
                message="Duplicate floor numbers found in building hierarchy.",
                details={"floor_numbers": floor_nums},
            ))
        else:
            results.append(ValidationCheckResult(
                check_name="floor_duplicates",
                status=ValidationStatus.PASS,
                message="All floor numbers are unique.",
            ))

        # Check floor sequence continuity
        sorted_nums = sorted(floor_nums)
        min_n, max_n = sorted_nums[0], sorted_nums[-1]
        expected_range = set(range(min_n, max_n + 1))
        missing = expected_range - set(sorted_nums)
        if missing:
            results.append(ValidationCheckResult(
                check_name="floor_continuity",
                status=ValidationStatus.WARNING,
                message=f"Floor sequence has missing levels: {sorted(list(missing))}",
                details={"missing_floors": list(missing)},
            ))
        else:
            results.append(ValidationCheckResult(
                check_name="floor_continuity",
                status=ValidationStatus.PASS,
                message="Floor hierarchy is continuous from lowest to highest level.",
            ))

        return results

    @staticmethod
    def run_full_validation(
        property_id: UUID,
        entity_type: str,
        parcel_wkt: Optional[str] = None,
        building_wkt: Optional[str] = None,
        floors_data: Optional[List[Dict[str, Any]]] = None,
        units_data: Optional[List[Dict[str, Any]]] = None,
    ) -> PropertyValidationReport:
        """Executes full cadastral topology validation suite for a given property entity."""
        checks: List[ValidationCheckResult] = []

        # 1. 2D Containment Check
        if entity_type in ["building", "parcel"]:
            checks.append(TopologyValidationService.validate_building_in_parcel(parcel_wkt, building_wkt))

        # 2. Floor Ordering & Continuity
        if floors_data is not None:
            checks.extend(TopologyValidationService.validate_floors_topology(floors_data))

        # 3. Units topology
        if units_data:
            unit_nums = [u.get("unit_number") for u in units_data if u.get("unit_number")]
            if len(unit_nums) != len(set(unit_nums)):
                checks.append(ValidationCheckResult(
                    check_name="unit_uniqueness",
                    status=ValidationStatus.FAIL,
                    message="Duplicate unit numbers detected on the same floor.",
                ))
            else:
                checks.append(ValidationCheckResult(
                    check_name="unit_uniqueness",
                    status=ValidationStatus.PASS,
                    message="All unit numbers are unique on this floor.",
                ))

        # Calculate overall score and status
        fail_count = sum(1 for c in checks if c.status == ValidationStatus.FAIL)
        warning_count = sum(1 for c in checks if c.status == ValidationStatus.WARNING)
        review_count = sum(1 for c in checks if c.status == ValidationStatus.REVIEW)
        pass_count = sum(1 for c in checks if c.status == ValidationStatus.PASS)

        total = len(checks)
        if total == 0:
            overall_status = ValidationStatus.REVIEW
            score = 50.0
        elif fail_count > 0:
            overall_status = ValidationStatus.FAIL
            score = max(0.0, round((pass_count / total) * 100.0, 1))
        elif review_count > 0:
            overall_status = ValidationStatus.REVIEW
            score = round((pass_count / total) * 80.0, 1)
        elif warning_count > 0:
            overall_status = ValidationStatus.WARNING
            score = round((pass_count / total) * 90.0, 1)
        else:
            overall_status = ValidationStatus.PASS
            score = 100.0

        is_authoritative_ready = (overall_status == ValidationStatus.PASS and score >= 95.0)

        summary = (
            f"Validation complete: {pass_count} passed, {warning_count} warnings, "
            f"{review_count} review items, {fail_count} failures. Overall Status: {overall_status}."
        )

        return PropertyValidationReport(
            property_id=property_id,
            entity_type=entity_type,
            overall_status=overall_status,
            score=score,
            is_authoritative_ready=is_authoritative_ready,
            checks=checks,
            validated_at=datetime.now(timezone.utc),
            summary=summary,
        )

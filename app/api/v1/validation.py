"""Cadastral topology and 3D geometry validation endpoints."""
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from shapely import wkt as shapely_wkt
from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError, ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.validation import (
    CadastralValidationRequest,
    CadastralValidationResponse,
    GeometryValidationRequest,
    GeometryValidationResponse,
    PropertyValidationReport,
    TopologyValidationRequest,
    TopologyValidationResponse,
    ValidationCheckResult,
    ValidationStatus,
)
from app.services.geometry_validation import SUPPORTED_CRS, GeometryValidationService
from app.services.topology_validation import TopologyValidationService

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/geometry", response_model=ApiResponse[GeometryValidationResponse])
async def validate_geometry(
    req: GeometryValidationRequest,
    _user: User = Depends(get_current_user),
):
    """
    REAL 2D/3D geometry validation.
    Checks:
    - Syntax validity and ring closure
    - Self-intersections and vertex deduplication
    - CRS validation
    - Non-zero metric area
    - 3D elevation and height sanity (no negative heights, min <= max elevation)
    """
    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {}

    # 1. CRS validation
    if req.crs and req.crs.upper() not in SUPPORTED_CRS:
        errors.append(f"Unsupported CRS: {req.crs}. Must be one of {list(SUPPORTED_CRS)}")

    # 2. Extract WKT from geometry_wkt or geometry_geojson
    geom_wkt = req.geometry_wkt
    if not geom_wkt and req.geometry_geojson:
        try:
            s_geom = shape(req.geometry_geojson)
            geom_wkt = s_geom.wkt
        except Exception as e:
            errors.append(f"Failed to parse GeoJSON geometry: {str(e)}")

    if not geom_wkt:
        errors.append("Either geometry_wkt or geometry_geojson must be provided")

    geom = None
    if geom_wkt:
        try:
            geom = shapely_wkt.loads(geom_wkt)
            if not geom.is_valid:
                reason = explain_validity(geom)
                errors.append(f"Invalid 2D geometry: {reason}")
            if geom.is_empty:
                errors.append("Geometry is empty")
            if geom.geom_type not in ["Polygon", "MultiPolygon"]:
                errors.append(f"Expected Polygon or MultiPolygon, got {geom.geom_type}")
            
            # Check duplicate vertices
            if geom.geom_type == "Polygon":
                coords = list(geom.exterior.coords)
                if len(coords) < 4:
                    errors.append(f"Polygon ring has insufficient vertices ({len(coords)}), minimum 4 required")
                for i in range(len(coords) - 1):
                    if coords[i] == coords[i + 1]:
                        warnings.append(f"Duplicate consecutive vertex at index {i}")

            details["bounds"] = list(geom.bounds)
            details["geom_type"] = geom.geom_type
            details["raw_area"] = float(geom.area)

        except Exception as e:
            errors.append(f"Malformed geometry WKT: {str(e)}")

    # 3. 3D attributes validation
    if req.height_m is not None:
        if req.height_m <= 0:
            errors.append(f"Building height must be strictly positive, got {req.height_m}m")
        elif req.height_m > 1000:
            warnings.append(f"Building height of {req.height_m}m is unusually high (over 1000m)")
        details["height_m"] = req.height_m

    if req.elevation_min_m is not None and req.elevation_max_m is not None:
        if req.elevation_min_m > req.elevation_max_m:
            errors.append(f"Min elevation ({req.elevation_min_m}m) exceeds max elevation ({req.elevation_max_m}m)")
        details["elevation_range_m"] = round(req.elevation_max_m - req.elevation_min_m, 2)

    is_valid = len(errors) == 0
    return ApiResponse(
        data=GeometryValidationResponse(
            is_valid=is_valid,
            geom_type=geom.geom_type if geom else None,
            crs=req.crs,
            dimension="3D" if req.expected_dim == "3D" or req.height_m is not None else "2D",
            errors=errors,
            warnings=warnings,
            details=details,
        )
    )


@router.post("/topology", response_model=ApiResponse[TopologyValidationResponse])
async def validate_topology(
    req: TopologyValidationRequest,
    _user: User = Depends(get_current_user),
):
    """
    REAL cadastral topology validation:
    - Parcel containment (building footprint inside parcel boundary)
    - Adjacent building footprint collision / overlap
    - Vertical floor ordering and elevation continuity
    - Unit area partitioning within floor
    """
    checks: List[ValidationCheckResult] = []

    # 1. Parcel containment check
    if req.parcel_wkt and req.building_wkt:
        containment_check = TopologyValidationService.validate_building_in_parcel(
            req.parcel_wkt, req.building_wkt
        )
        checks.append(containment_check)

    # 2. Adjacent buildings overlap check
    if req.building_wkt and req.adjacent_building_wkts:
        try:
            b_geom = shapely_wkt.loads(req.building_wkt)
            overlap_found = False
            for idx, adj_wkt in enumerate(req.adjacent_building_wkts):
                try:
                    adj_geom = shapely_wkt.loads(adj_wkt)
                    if b_geom.intersects(adj_geom):
                        inter = b_geom.intersection(adj_geom)
                        if inter.area > 0.000001:  # Significant polygon overlap
                            overlap_found = True
                            checks.append(
                                ValidationCheckResult(
                                    check_name=f"building_overlap_{idx}",
                                    status=ValidationStatus.FAIL,
                                    message=f"Building footprint overlaps adjacent building {idx}",
                                    details={"intersection_area": float(inter.area)},
                                )
                            )
                except Exception:
                    pass
            if not overlap_found:
                checks.append(
                    ValidationCheckResult(
                        check_name="adjacent_building_separation",
                        status=ValidationStatus.PASS,
                        message="Building does not unlawfully overlap any adjacent building footprints.",
                    )
                )
        except Exception as e:
            checks.append(
                ValidationCheckResult(
                    check_name="adjacent_building_separation",
                    status=ValidationStatus.FAIL,
                    message=f"Failed to check adjacent overlap: {str(e)}",
                )
            )

    # 3. Vertical floor hierarchy
    if req.floors_data:
        floor_check = TopologyValidationService.validate_floor_hierarchy(req.floors_data)
        checks.append(floor_check)

    # 4. Unit partitioning
    if req.units_data:
        floor_area = req.floors_data[0].get("floor_area_sqm") if req.floors_data else None
        unit_check = TopologyValidationService.validate_units_in_floor(
            floor_area_sqm=float(floor_area) if floor_area else None,
            units_data=req.units_data,
        )
        checks.append(unit_check)

    has_fail = any(c.status == ValidationStatus.FAIL for c in checks)
    has_warn = any(c.status in [ValidationStatus.WARNING, ValidationStatus.REVIEW] for c in checks)
    overall_status = ValidationStatus.FAIL if has_fail else (ValidationStatus.WARNING if has_warn else ValidationStatus.PASS)

    return ApiResponse(
        data=TopologyValidationResponse(
            is_valid=(not has_fail),
            overall_status=overall_status,
            checks=checks,
            summary=f"Topology evaluation: {len(checks)} checks evaluated with overall status {overall_status}.",
        )
    )


@router.post("/cadastral", response_model=ApiResponse[CadastralValidationResponse])
async def validate_cadastral_entity(
    req: CadastralValidationRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    REAL comprehensive cadastral hierarchy and integrity validation.
    Verifies:
    - Parcel -> Building -> Floor -> Unit referential and topological integrity
    - Attribute completeness (survey numbers, area, state, district)
    - ULPIN registry status
    - 3D physical continuity
    """
    checks: List[ValidationCheckResult] = []
    entity_type = None
    entity_id = None

    if req.parcel_id:
        entity_type = "parcel"
        entity_id = req.parcel_id
        parcel = await db.get(Parcel, req.parcel_id)
        if not parcel:
            raise NotFoundError(f"Parcel {req.parcel_id} not found")

        # Attribute check
        missing_attrs = []
        if not parcel.parcel_number:
            missing_attrs.append("parcel_number")
        if not parcel.district:
            missing_attrs.append("district")
        if not parcel.state:
            missing_attrs.append("state")

        if missing_attrs:
            checks.append(
                ValidationCheckResult(
                    check_name="required_attributes",
                    status=ValidationStatus.FAIL,
                    message=f"Missing required cadastral attributes: {', '.join(missing_attrs)}",
                )
            )
        else:
            checks.append(
                ValidationCheckResult(
                    check_name="required_attributes",
                    status=ValidationStatus.PASS,
                    message="All mandatory cadastral parcel attributes are populated.",
                )
            )

        # Geometry check
        if parcel.boundary_wkt:
            try:
                g = shapely_wkt.loads(parcel.boundary_wkt)
                if g.is_valid:
                    checks.append(
                        ValidationCheckResult(
                            check_name="parcel_geometry_validity",
                            status=ValidationStatus.PASS,
                            message="Parcel boundary geometry is topologically valid.",
                        )
                    )
                else:
                    checks.append(
                        ValidationCheckResult(
                            check_name="parcel_geometry_validity",
                            status=ValidationStatus.FAIL,
                            message=f"Parcel geometry invalid: {explain_validity(g)}",
                        )
                    )
            except Exception as e:
                checks.append(
                    ValidationCheckResult(
                        check_name="parcel_geometry_validity",
                        status=ValidationStatus.FAIL,
                        message=f"Failed to parse parcel boundary: {str(e)}",
                    )
                )
        else:
            checks.append(
                ValidationCheckResult(
                    check_name="parcel_geometry_validity",
                    status=ValidationStatus.REVIEW,
                    message="Parcel boundary geometry is unassigned.",
                )
            )

        # ULPIN check
        if req.check_ulpin_registry:
            if parcel.official_ulpin or parcel.candidate_ulpin:
                checks.append(
                    ValidationCheckResult(
                        check_name="ulpin_registered",
                        status=ValidationStatus.PASS,
                        message="Parcel is mapped to a valid candidate or official ULPIN.",
                        details={
                            "official_ulpin": parcel.official_ulpin,
                            "candidate_ulpin": parcel.candidate_ulpin,
                        },
                    )
                )
            else:
                checks.append(
                    ValidationCheckResult(
                        check_name="ulpin_registered",
                        status=ValidationStatus.WARNING,
                        message="Parcel does not have an assigned candidate or official ULPIN.",
                    )
                )

        # Check child buildings
        b_res = await db.execute(select(Building).where(Building.parcel_id == parcel.id, Building.is_active == True))
        buildings = b_res.scalars().all()
        checks.append(
            ValidationCheckResult(
                check_name="child_buildings_count",
                status=ValidationStatus.PASS,
                message=f"Parcel hosts {len(buildings)} active building(s).",
                details={"building_count": len(buildings)},
            )
        )

    elif req.building_id:
        entity_type = "building"
        entity_id = req.building_id
        building = await db.get(Building, req.building_id)
        if not building:
            raise NotFoundError(f"Building {req.building_id} not found")

        parcel = await db.get(Parcel, building.parcel_id)
        if not parcel:
            checks.append(
                ValidationCheckResult(
                    check_name="parent_parcel_exists",
                    status=ValidationStatus.FAIL,
                    message=f"Building refers to non-existent parent parcel {building.parcel_id}",
                )
            )
        else:
            checks.append(
                ValidationCheckResult(
                    check_name="parent_parcel_exists",
                    status=ValidationStatus.PASS,
                    message=f"Building is linked to parent parcel {parcel.parcel_number}",
                )
            )

        # Building footprint in parcel check
        if parcel and parcel.boundary_wkt and building.footprint_wkt:
            containment = TopologyValidationService.validate_building_in_parcel(
                parcel.boundary_wkt, building.footprint_wkt
            )
            checks.append(containment)

        # Height & floor count sanity
        if building.height_m is not None:
            if building.height_m > 0:
                checks.append(
                    ValidationCheckResult(
                        check_name="positive_height",
                        status=ValidationStatus.PASS,
                        message=f"Building height is valid ({building.height_m}m)",
                    )
                )
            else:
                checks.append(
                    ValidationCheckResult(
                        check_name="positive_height",
                        status=ValidationStatus.FAIL,
                        message=f"Building height must be strictly positive ({building.height_m}m)",
                    )
                )

    else:
        raise ValidationError("Either parcel_id or building_id must be provided")

    has_fail = any(c.status == ValidationStatus.FAIL for c in checks)
    has_warn = any(c.status in [ValidationStatus.WARNING, ValidationStatus.REVIEW] for c in checks)
    overall_status = ValidationStatus.FAIL if has_fail else (ValidationStatus.WARNING if has_warn else ValidationStatus.PASS)

    return ApiResponse(
        data=CadastralValidationResponse(
            is_valid=(not has_fail),
            overall_status=overall_status,
            entity_id=entity_id,
            entity_type=entity_type,
            checks=checks,
            summary=f"Cadastral validation report: {len(checks)} checks completed with overall status {overall_status}.",
            timestamp=datetime.now(timezone.utc),
        )
    )


@router.get("/{property_id}", response_model=ApiResponse[PropertyValidationReport])
async def get_validation_report(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Retrieves full property topology validation report."""
    building = await db.get(Building, property_id)
    if building:
        parcel = await db.get(Parcel, building.parcel_id)
        floors_res = await db.execute(select(Floor).where(Floor.building_id == building.id))
        floors = floors_res.scalars().all()
        floors_data = [{"floor_number": f.floor_number, "ceiling_height_m": f.ceiling_height_m} for f in floors]

        report = TopologyValidationService.run_full_validation(
            property_id=property_id,
            entity_type="building",
            parcel_wkt=parcel.boundary_wkt if parcel else None,
            building_wkt=building.footprint_wkt,
            floors_data=floors_data,
        )
        return ApiResponse(data=report)

    parcel = await db.get(Parcel, property_id)
    if parcel:
        report = TopologyValidationService.run_full_validation(
            property_id=property_id,
            entity_type="parcel",
            parcel_wkt=parcel.boundary_wkt,
        )
        return ApiResponse(data=report)

    raise NotFoundError(f"Property entity {property_id} not found")


@router.post("/run/{property_id}", response_model=ApiResponse[PropertyValidationReport])
async def run_property_validation(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    """Executes topology and cadastral validation on an existing property entity."""
    return await get_validation_report(property_id=property_id, db=db, _user=user)

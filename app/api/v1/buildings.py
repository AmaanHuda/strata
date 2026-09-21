"""Building CRUD, Floor listing, history, and ML trigger endpoints."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Building, Floor
from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.integrations.ml_engine.adapter import MLAdapter
from app.schemas.common import ApiResponse
from app.schemas.property import (
    BuildingCreate,
    BuildingGeometryOut,
    BuildingOut,
    BuildingStructureOut,
    BuildingUpdate,
    CentroidPoint,
    FloorOut,
    FloorStructureOut,
    PropertyHistoryOut,
    UnitStructureOut,
)

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("", response_model=ApiResponse[BuildingOut], status_code=status.HTTP_201_CREATED)
async def create_building(
    data: BuildingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    repo = BaseRepository(Building, db)
    building = await repo.create(data.model_dump(exclude_unset=True))
    return ApiResponse(data=BuildingOut.model_validate(building), meta={"message": "Building created"})


@router.get("", response_model=ApiResponse[List[BuildingOut]])
async def list_buildings(
    parcel_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = select(Building).where(Building.is_active == True).limit(limit).offset(offset)
    if parcel_id:
        stmt = stmt.where(Building.parcel_id == parcel_id)
    res = await db.execute(stmt)
    buildings = res.scalars().all()
    return ApiResponse(data=[BuildingOut.model_validate(b) for b in buildings], meta={"count": len(buildings)})


@router.get("/{building_id}", response_model=ApiResponse[BuildingOut])
async def get_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(Building, db)
    building = await repo.get(building_id)
    if not building:
        raise NotFoundError(f"Building {building_id} not found")
    return ApiResponse(data=BuildingOut.model_validate(building))


@router.get("/{building_id}/floors", response_model=ApiResponse[List[FloorOut]])
async def get_building_floors(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Floor).where(Floor.building_id == building_id, Floor.is_active == True).order_by(Floor.floor_number)
    )
    floors = res.scalars().all()
    return ApiResponse(data=[FloorOut.model_validate(f) for f in floors], meta={"count": len(floors)})


@router.put("/{building_id}", response_model=ApiResponse[BuildingOut])
async def update_building(
    building_id: UUID,
    data: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    repo = BaseRepository(Building, db)
    building = await repo.get(building_id)
    if not building or not building.is_active:
        raise NotFoundError(f"Building {building_id} not found or inactive")
    
    new_building = building.create_new_version()
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(new_building, k, v)
    
    db.add(new_building)
    await db.commit()
    await db.refresh(new_building)
    return ApiResponse(data=BuildingOut.model_validate(new_building), meta={"message": "Building version updated"})


@router.get("/{building_id}/history", response_model=ApiResponse[List[BuildingOut]])
async def get_building_history(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(Building, db)
    building = await repo.get(building_id)
    if not building:
        raise NotFoundError(f"Building {building_id} not found")
    
    # Without a stable natural key, history is just the current object (or we can query by parcel_id and building name)
    return ApiResponse(data=[BuildingOut.model_validate(building)])


@router.get("/{building_id}/structure", response_model=ApiResponse[BuildingStructureOut])
async def get_building_structure(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Optimized building structure endpoint for STRATA frontend:
    Returns complete nested hierarchy: Building -> Floors -> Units
    along with centroid, validation status, and provenance in a single query.
    """
    from sqlalchemy.orm import selectinload
    from app.db.models.property import Parcel

    stmt = (
        select(Building)
        .options(selectinload(Building.floors).selectinload(Floor.units))
        .where(Building.id == building_id, Building.is_active == True)
    )
    res = await db.execute(stmt)
    building = res.scalar_one_or_none()
    if not building:
        raise NotFoundError(f"Building {building_id} not found")

    parcel = await db.get(Parcel, building.parcel_id)

    centroid = None
    if building.footprint_2d is not None:
        c_res = await db.execute(select(func.ST_AsGeoJSON(func.ST_Centroid(Building.footprint_2d))).where(Building.id == building_id))
        c_str = c_res.scalar()
        if c_str:
            try:
                c_data = json.loads(c_str)
                coords = c_data.get("coordinates", [])
                if len(coords) >= 2:
                    centroid = CentroidPoint(lon=float(coords[0]), lat=float(coords[1]))
            except Exception:
                pass

    floor_structures = []
    for flr in sorted(building.floors, key=lambda f: f.floor_number):
        if not flr.is_active:
            continue
        unit_structures = [
            UnitStructureOut(
                id=u.id,
                floor_id=u.floor_id,
                unit_number=u.unit_number,
                unit_type=u.unit_type,
                area_sqm=u.area_sqm,
                volume_cum=u.volume_cum,
                is_occupied=u.is_occupied,
                official_ulpin=u.official_ulpin,
                candidate_ulpin=u.candidate_ulpin,
                status=u.status,
                is_verified=u.is_verified,
            )
            for u in sorted(flr.units, key=lambda x: x.unit_number)
            if u.is_active
        ]
        floor_structures.append(
            FloorStructureOut(
                id=flr.id,
                building_id=flr.building_id,
                floor_number=flr.floor_number,
                floor_label=flr.floor_label,
                floor_use=flr.floor_use,
                height_above_ground_m=flr.height_above_ground_m,
                ceiling_height_m=flr.ceiling_height_m,
                floor_area_sqm=flr.floor_area_sqm,
                volume_cum=flr.volume_cum,
                official_ulpin=flr.official_ulpin,
                candidate_ulpin=flr.candidate_ulpin,
                status=flr.status,
                is_verified=flr.is_verified,
                units=unit_structures,
            )
        )

    structure_data = BuildingStructureOut(
        id=building.id,
        building_id=building.id,
        parcel_id=building.parcel_id,
        building_name=building.building_name,
        building_type=building.building_type,
        floor_count=building.floor_count,
        height_m=building.height_m,
        footprint_area_sqm=building.footprint_area_sqm,
        official_ulpin=building.official_ulpin,
        candidate_ulpin=building.candidate_ulpin,
        status=building.status,
        is_verified=building.is_verified,
        centroid=centroid,
        address=f"{building.building_name or 'Building'}, Parcel {parcel.parcel_number if parcel else ''}",
        district=parcel.district if parcel else None,
        state=parcel.state if parcel else None,
        provenance={
            "ml_derived": building.ml_derived,
            "ml_model_version": building.ml_model_version,
            "ml_confidence_score": building.ml_confidence_score,
            "version": building.version,
            "created_at": building.created_at.isoformat() if building.created_at else None,
            "updated_at": building.updated_at.isoformat() if building.updated_at else None,
        },
        floors=floor_structures,
    )
    return ApiResponse(data=structure_data)


@router.get("/{building_id}/geometry", response_model=ApiResponse[BuildingGeometryOut])
async def get_building_geometry(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Returns full building 2D/3D geometry, centroid, bounds, and CRS details.
    """
    from shapely import wkt as shapely_wkt

    stmt = select(
        Building.id,
        Building.parcel_id,
        Building.height_m,
        Building.footprint_wkt,
        Building.source_crs,
        Building.processing_crs,
        func.ST_AsGeoJSON(Building.footprint_2d).label("geojson"),
        func.ST_AsGeoJSON(func.ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
        func.ST_AsGeoJSON(Building.geometry_3d_lod2).label("lod2_geojson"),
    ).where(Building.id == building_id, Building.is_active == True)

    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundError(f"Building {building_id} not found or inactive")

    b_id, p_id, height, fp_wkt, s_crs, p_crs, geo_str, cent_str, lod2_str = row

    centroid = None
    if cent_str:
        try:
            c_data = json.loads(cent_str)
            coords = c_data.get("coordinates", [])
            if len(coords) >= 2:
                centroid = CentroidPoint(lon=float(coords[0]), lat=float(coords[1]))
        except Exception:
            pass

    fp_geojson = json.loads(geo_str) if geo_str else None
    lod2_geojson = json.loads(lod2_str) if lod2_str else None

    bounds = None
    if fp_wkt:
        try:
            geom = shapely_wkt.loads(fp_wkt)
            bounds = list(geom.bounds)
        except Exception:
            pass

    return ApiResponse(
        data=BuildingGeometryOut(
            building_id=b_id,
            parcel_id=p_id,
            centroid=centroid,
            height_m=height,
            elevation_m=None,
            footprint_wkt=fp_wkt,
            footprint_geojson=fp_geojson,
            bounds=bounds,
            geometry_3d_lod2=lod2_geojson,
            source_crs=s_crs,
            processing_crs=p_crs,
        )
    )


@router.get("/{building_id}/geojson")
async def get_building_geojson(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(func.ST_AsGeoJSON(Building.footprint_2d)).where(Building.id == building_id, Building.is_active == True)
    )
    geojson_str = res.scalar()
    if not geojson_str:
        raise NotFoundError("Geometry not found or building inactive")
    return ApiResponse(data=json.loads(geojson_str))


@router.post("/{building_id}/estimate-height", response_model=ApiResponse[BuildingOut])
async def estimate_building_height(
    building_id: UUID,
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    adapter = MLAdapter(db)
    await adapter.trigger_height_estimation(building_id, lat=lat, lon=lon)
    repo = BaseRepository(Building, db)
    building = await repo.get(building_id)
    return ApiResponse(data=BuildingOut.model_validate(building), meta={"message": "Height estimated via ML pipeline"})

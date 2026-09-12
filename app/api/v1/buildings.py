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
    BuildingOut,
    BuildingUpdate,
    FloorOut,
    PropertyHistoryOut,
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

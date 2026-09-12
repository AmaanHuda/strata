"""Building CRUD + ML trigger endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.db.models.property import Building
from app.db.repositories.base import BaseRepository
from app.schemas.property import BuildingCreate, BuildingOut
from app.integrations.ml_engine.adapter import MLAdapter

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("", response_model=BuildingOut, status_code=201)
async def create_building(
    data: BuildingCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    repo = BaseRepository(Building, db)
    create_data = data.model_dump(exclude_none=True, by_alias=False)
    create_data.pop("footprint_wkt", None)
    return await repo.create(create_data)


@router.get("/{building_id}", response_model=BuildingOut)
async def get_building(building_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    repo = BaseRepository(Building, db)
    b = await repo.get(building_id)
    if not b:
        from fastapi import HTTPException
        raise HTTPException(404, "Building not found")
    return b


@router.post("/{building_id}/ml/height")
async def trigger_height_estimation(
    building_id: UUID,
    lat: float, lon: float,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.SURVEYOR)),
):
    """Trigger ML height estimation for a building."""
    adapter = MLAdapter(db)
    return await adapter.run_height_estimation(building_id, lat, lon)


@router.post("/{building_id}/ml/floors")
async def trigger_floor_count(
    building_id: UUID,
    height_m: float = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.SURVEYOR)),
):
    adapter = MLAdapter(db)
    return await adapter.run_floor_count(building_id, height_m)

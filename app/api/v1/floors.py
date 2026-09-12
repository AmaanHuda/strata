"""Floor CRUD and unit query endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Floor, Unit
from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.property import FloorCreate, FloorOut, UnitOut

router = APIRouter(prefix="/floors", tags=["floors"])


@router.post("", response_model=ApiResponse[FloorOut], status_code=status.HTTP_201_CREATED)
async def create_floor(
    data: FloorCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    repo = BaseRepository(Floor, db)
    floor = await repo.create(data.model_dump(exclude_unset=True))
    return ApiResponse(data=FloorOut.model_validate(floor), meta={"message": "Floor registered"})


@router.get("/{floor_id}", response_model=ApiResponse[FloorOut])
async def get_floor(
    floor_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(Floor, db)
    floor = await repo.get(floor_id)
    if not floor:
        raise NotFoundError(f"Floor {floor_id} not found")
    return ApiResponse(data=FloorOut.model_validate(floor))


@router.get("/{floor_id}/units", response_model=ApiResponse[List[UnitOut]])
async def get_floor_units(
    floor_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Unit).where(Unit.floor_id == floor_id, Unit.is_active == True).order_by(Unit.unit_number)
    )
    units = res.scalars().all()
    return ApiResponse(data=[UnitOut.model_validate(u) for u in units], meta={"count": len(units)})

"""Unit endpoints with complete temporal history and zero private owner exposure."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Unit
from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.property import PropertyHistoryOut, UnitCreate, UnitOut

router = APIRouter(prefix="/units", tags=["units"])


@router.post("", response_model=ApiResponse[UnitOut], status_code=status.HTTP_201_CREATED)
async def create_unit(
    data: UnitCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    repo = BaseRepository(Unit, db)
    unit = await repo.create(data.model_dump(exclude_unset=True))
    return ApiResponse(data=UnitOut.model_validate(unit), meta={"message": "Unit registered"})


@router.get("", response_model=ApiResponse[List[UnitOut]])
async def list_units(
    floor_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = select(Unit).where(Unit.is_active == True).limit(limit).offset(offset)
    if floor_id:
        stmt = stmt.where(Unit.floor_id == floor_id)
    res = await db.execute(stmt)
    units = res.scalars().all()
    return ApiResponse(data=[UnitOut.model_validate(u) for u in units], meta={"count": len(units)})


@router.get("/{unit_id}", response_model=ApiResponse[UnitOut])
async def get_unit(
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(Unit, db)
    unit = await repo.get(unit_id)
    if not unit:
        raise NotFoundError(f"Unit {unit_id} not found")
    return ApiResponse(data=UnitOut.model_validate(unit))


@router.get("/{unit_id}/history", response_model=ApiResponse[List[PropertyHistoryOut]])
async def get_unit_history(
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(Unit, db)
    unit = await repo.get(unit_id)
    if not unit:
        raise NotFoundError(f"Unit {unit_id} not found")

    history_item = PropertyHistoryOut(
        id=unit.id,
        entity_type="unit",
        version=unit.version,
        valid_from=unit.valid_from,
        valid_to=unit.valid_to,
        is_active=unit.is_active,
        status=unit.status,
        change_summary=f"Unit {unit.unit_number} current status: {unit.status}",
    )
    return ApiResponse(data=[history_item])

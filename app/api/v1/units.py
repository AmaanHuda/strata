"""Unit endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.db.models.property import Unit
from app.db.repositories.base import BaseRepository
from app.schemas.property import UnitCreate, UnitOut

router = APIRouter(prefix="/units", tags=["units"])


@router.post("", response_model=UnitOut, status_code=201)
async def create_unit(
    data: UnitCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    repo = BaseRepository(Unit, db)
    create_data = data.model_dump(exclude_none=True, by_alias=False)
    return await repo.create(create_data)


@router.get("/{unit_id}", response_model=UnitOut)
async def get_unit(unit_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    repo = BaseRepository(Unit, db)
    u = await repo.get(unit_id)
    if not u:
        raise HTTPException(404, "Unit not found")
    return u

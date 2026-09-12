"""Floor endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.db.models.property import Floor
from app.db.repositories.base import BaseRepository
from app.schemas.property import FloorCreate, FloorOut

router = APIRouter(prefix="/floors", tags=["floors"])


@router.post("", response_model=FloorOut, status_code=201)
async def create_floor(
    data: FloorCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    repo = BaseRepository(Floor, db)
    return await repo.create(data.model_dump(exclude_none=True))


@router.get("/{floor_id}", response_model=FloorOut)
async def get_floor(floor_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    repo = BaseRepository(Floor, db)
    f = await repo.get(floor_id)
    if not f:
        from fastapi import HTTPException
        raise HTTPException(404, "Floor not found")
    return f

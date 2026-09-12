"""Parcel CRUD and spatial query endpoints."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Building, Parcel
from app.db.models.user import User, UserRole
from app.db.repositories.parcel import ParcelRepository
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.property import BuildingOut, ParcelCreate, ParcelOut
from app.services.parcel import ParcelService

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.post("", response_model=ApiResponse[ParcelOut], status_code=status.HTTP_201_CREATED)
async def create_parcel(
    data: ParcelCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    svc = ParcelService(db)
    parcel = await svc.create_parcel(data)
    return ApiResponse(data=ParcelOut.model_validate(parcel), meta={"message": "Parcel registered"})


@router.get("", response_model=ApiResponse[List[ParcelOut]])
async def list_parcels(
    district: Optional[str] = Query(None),
    village: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    parcels = await svc.list_parcels(district=district, village=village, limit=limit, offset=offset)
    return ApiResponse(data=[ParcelOut.model_validate(p) for p in parcels], meta={"count": len(parcels)})


@router.get("/{parcel_id}", response_model=ApiResponse[ParcelOut])
async def get_parcel(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    parcel = await svc.get_parcel(parcel_id)
    if not parcel:
        raise NotFoundError(f"Parcel {parcel_id} not found")
    return ApiResponse(data=ParcelOut.model_validate(parcel))


@router.get("/{parcel_id}/buildings", response_model=ApiResponse[List[BuildingOut]])
async def get_parcel_buildings(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Building).where(Building.parcel_id == parcel_id, Building.is_active == True)
    )
    buildings = res.scalars().all()
    return ApiResponse(data=[BuildingOut.model_validate(b) for b in buildings], meta={"count": len(buildings)})

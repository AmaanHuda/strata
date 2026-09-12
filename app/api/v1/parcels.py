"""Parcel CRUD + spatial search endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.property import ParcelCreate, ParcelOut
from app.services.parcel import ParcelService

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.post("", response_model=ParcelOut, status_code=201)
async def create_parcel(
    data: ParcelCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    svc = ParcelService(db)
    return await svc.create_parcel(data)


@router.get("", response_model=List[ParcelOut])
async def list_parcels(
    district: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    return await svc.list_parcels(district=district, offset=offset, limit=limit)


@router.get("/{parcel_id}", response_model=ParcelOut)
async def get_parcel(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    return await svc.get_parcel(parcel_id)


@router.get("/spatial/bbox", response_model=List[ParcelOut])
async def search_bbox(
    min_lon: float = Query(...), min_lat: float = Query(...),
    max_lon: float = Query(...), max_lat: float = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    return await svc.spatial_search_bbox(min_lon, min_lat, max_lon, max_lat)


@router.get("/spatial/radius", response_model=List[ParcelOut])
async def search_radius(
    lon: float = Query(...), lat: float = Query(...),
    radius_m: float = Query(500.0, gt=0, le=50000),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = ParcelService(db)
    return await svc.spatial_search_radius(lon, lat, radius_m)

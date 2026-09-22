"""Parcel CRUD, spatial query, and ML processing endpoints."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Building, Parcel
from app.db.models.user import User, UserRole
from app.db.repositories.parcel import ParcelRepository
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.property import BuildingOut, ParcelCreate, ParcelOut, ParcelUpdate
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


@router.put("/{parcel_id}", response_model=ApiResponse[ParcelOut])
async def update_parcel(
    parcel_id: UUID,
    data: ParcelUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    svc = ParcelService(db)
    parcel = await svc.get_parcel(parcel_id)
    if not parcel or not parcel.is_active:
        raise NotFoundError(f"Parcel {parcel_id} not found or inactive")
    
    new_parcel = parcel.create_new_version()
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(new_parcel, k, v)
    
    db.add(new_parcel)
    await db.commit()
    await db.refresh(new_parcel)
    return ApiResponse(data=ParcelOut.model_validate(new_parcel), meta={"message": "Parcel version updated"})


@router.get("/{parcel_id}/history", response_model=ApiResponse[List[ParcelOut]])
async def get_parcel_history(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    parcel = await db.get(Parcel, parcel_id)
    if not parcel:
        raise NotFoundError("Parcel not found")
    
    res = await db.execute(
        select(Parcel).where(Parcel.parcel_number == parcel.parcel_number).order_by(Parcel.version.desc())
    )
    versions = res.scalars().all()
    return ApiResponse(data=[ParcelOut.model_validate(v) for v in versions])


@router.get("/{parcel_id}/geojson")
async def get_parcel_geojson(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(func.ST_AsGeoJSON(Parcel.geometry_2d)).where(Parcel.id == parcel_id, Parcel.is_active == True)
    )
    geojson_str = res.scalar()
    if not geojson_str:
        raise NotFoundError("Geometry not found or parcel inactive")
    return ApiResponse(data=json.loads(geojson_str))


@router.post("/{parcel_id}/process-ml", response_model=ApiResponse[Dict[str, Any]])
async def process_parcel_ml(
    parcel_id: UUID,
    height_m: Optional[float] = Query(None, description="Optional measured height in meters"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    """
    Triggers end-to-end ML Engine pipeline for a parcel:
    Invokes MLEnginePipeline.process_parcel(), validates ML output contract v1.0.0,
    maps building/floor/unit entities, and persists with full ML provenance.
    """
    from app.integrations.ml_engine.adapter import MLAdapter
    adapter = MLAdapter(db)
    result = await adapter.process_parcel_with_ml(parcel_id=parcel_id, height_m=height_m)
    return ApiResponse(data=result, meta={"message": "ML parcel processing completed and persisted"})

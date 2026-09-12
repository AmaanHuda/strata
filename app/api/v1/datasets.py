"""Spatial dataset registry endpoints."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.dataset import DatasetOut, DatasetRegisterRequest
from app.services.dataset import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/register", response_model=ApiResponse[DatasetOut], status_code=status.HTTP_201_CREATED)
async def register_dataset(
    req: DatasetRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = DatasetService(db)
    ds = await svc.register_dataset(req, user)
    return ApiResponse(data=DatasetOut.model_validate(ds), meta={"message": "Dataset registered in catalog"})


@router.get("", response_model=ApiResponse[List[DatasetOut]])
async def list_datasets(
    modality: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = DatasetService(db)
    datasets = await svc.list_datasets(modality=modality)
    return ApiResponse(data=[DatasetOut.model_validate(d) for d in datasets], meta={"count": len(datasets)})


@router.get("/{dataset_id}", response_model=ApiResponse[DatasetOut])
async def get_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = DatasetService(db)
    ds = await svc.get_dataset(dataset_id)
    return ApiResponse(data=DatasetOut.model_validate(ds))

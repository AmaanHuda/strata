"""ULPIN generation and lookup endpoints."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.ulpin import (
    ULPINGenerateRequest,
    ULPINLookupResponse,
    ULPINOut,
    ULPINValidateRequest,
    ULPINValidateResponse,
)
from app.services.ulpin import ULPINService

router = APIRouter(prefix="/ulpin", tags=["ulpin"])


@router.post("/generate", response_model=ApiResponse[ULPINOut], status_code=status.HTTP_201_CREATED)
async def generate_ulpin(
    req: ULPINGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = ULPINService(db)
    record = await svc.generate_and_store(req, created_by=user.id)
    return ApiResponse(data=ULPINOut.model_validate(record), meta={"message": "Candidate ULPIN generated"})


@router.post("/validate", response_model=ApiResponse[ULPINValidateResponse])
async def validate_ulpin(
    req: ULPINValidateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Validates ULPIN format, registry status, and entity linkage.
    Distinguishes clearly between CANDIDATE, VALIDATED, and OFFICIAL states.
    """
    svc = ULPINService(db)
    result = await svc.validate_ulpin(
        ulpin=req.ulpin,
        entity_id=req.entity_id,
        entity_type=req.entity_type,
    )
    return ApiResponse(data=result)


@router.get("/{ulpin_str}", response_model=ApiResponse[ULPINLookupResponse])
async def lookup_ulpin(
    ulpin_str: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(ULPINRecord).where(
            (ULPINRecord.candidate_ulpin == ulpin_str) | (ULPINRecord.official_ulpin == ulpin_str)
        )
    )
    rec = res.scalar_one_or_none()
    if not rec:
        raise NotFoundError(f"ULPIN '{ulpin_str}' not found in registry")

    return ApiResponse(
        data=ULPINLookupResponse(
            ulpin=rec.official_ulpin or rec.candidate_ulpin,
            is_official=bool(rec.official_ulpin),
            status=rec.status,
            entity_type=rec.entity_type,
            entity_id=rec.parcel_id or rec.building_id or rec.floor_id or rec.unit_id,
            entity_details={
                "parcel_id": str(rec.parcel_id) if rec.parcel_id else None,
                "building_id": str(rec.building_id) if rec.building_id else None,
                "floor_id": str(rec.floor_id) if rec.floor_id else None,
                "unit_id": str(rec.unit_id) if rec.unit_id else None,
            },
            legal_disclaimer=rec.legal_disclaimer,
        )
    )

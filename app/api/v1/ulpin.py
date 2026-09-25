"""ULPIN generation and lookup endpoints.

Includes the deterministic, versioned 3D ULPIN system
(``app/services/ulpin_3d.py``, algorithm ``3D_GEOMETRY_HASH_V1``). 3D ULPINs are
SYSTEM-GENERATED analytical identifiers and are never presented as, or written
to, ``official_ulpin``.
"""
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError, ValidationError
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
from app.services.ulpin_3d import (
    ALGORITHM_VERSION as ULPIN_3D_ALGORITHM_VERSION,
    CANONICALIZATION_VERSION as ULPIN_3D_CANON_VERSION,
    ULPIN3DService,
    parse_3d_ulpin,
    validate_3d_ulpin,
)

router = APIRouter(prefix="/ulpin", tags=["ulpin"])


# --------------------------------------------------------------------------- #
# Deterministic 3D ULPIN (SYSTEM GENERATED — never an official ULPIN)
# --------------------------------------------------------------------------- #


@router.get("/3d/validate/{ulpin_str}", response_model=ApiResponse[Dict[str, Any]])
async def validate_3d_ulpin_endpoint(
    ulpin_str: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Recompute the checksum of a 3D ULPIN and report registry match.

    Returns ``valid=False`` for any single-character mutation.
    """
    valid = validate_3d_ulpin(ulpin_str)
    segments = parse_3d_ulpin(ulpin_str)
    registered = None
    if valid:
        record = (
            await db.execute(
                select(ULPINRecord).where(ULPINRecord.candidate_ulpin == ulpin_str.strip())
            )
        ).scalars().first()
        if record is not None:
            registered = {
                "entity_type": record.entity_type,
                "entity_id": str(record.parcel_id or record.building_id or record.floor_id or record.unit_id),
                "status": record.status,
                "is_authoritative": record.is_authoritative,
                "official_ulpin": record.official_ulpin,
                "algorithm_version": record.algorithm_version,
                "canonicalization_version": record.canonicalization_version,
                "object_type": record.object_type,
            }
    return ApiResponse(
        data={
            "ulpin": ulpin_str,
            "valid": valid,
            "is_3d_ulpin": True,
            "segments": segments,
            "matched_in_registry": registered is not None,
            "registry": registered,
            "algorithm_version": ULPIN_3D_ALGORITHM_VERSION,
            "canonicalization_version": ULPIN_3D_CANON_VERSION,
            "status_label": "3D ULPIN — SYSTEM GENERATED",
            "official_ulpin": None,
        }
    )


@router.post(
    "/3d/sync/{building_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
)
async def sync_3d_ulpins(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    """
    Materialise (idempotently) the deterministic 3D ULPINs for a building's
    parcel/building/floor/unit hierarchy.

    Entities lacking real geometry or real vertical information are reported in
    ``skipped`` with a reason — no identifier is invented for them.
    """
    svc = ULPIN3DService(db)
    result = await svc.sync_building(building_id, created_by=user.id)
    return ApiResponse(data=result, meta={"message": "3D ULPIN hierarchy synced"})


@router.get("/3d/{ulpin_str}", response_model=ApiResponse[Dict[str, Any]])
async def lookup_3d_ulpin(
    ulpin_str: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Look up a 3D ULPIN in the registry (with a live checksum re-verification)."""
    if not validate_3d_ulpin(ulpin_str):
        raise ValidationError("Not a valid 3D ULPIN (checksum or segment shape failed).")
    record = (
        await db.execute(
            select(ULPINRecord).where(ULPINRecord.candidate_ulpin == ulpin_str.strip())
        )
    ).scalars().first()
    if record is None:
        raise NotFoundError(f"3D ULPIN '{ulpin_str}' is well-formed but not registered")
    return ApiResponse(
        data={
            "ulpin": record.candidate_ulpin,
            "entity_type": record.entity_type,
            "entity_id": str(record.parcel_id or record.building_id or record.floor_id or record.unit_id),
            "status": record.status,
            "is_authoritative": record.is_authoritative,
            "official_ulpin": record.official_ulpin,
            "algorithm_version": record.algorithm_version,
            "canonicalization_version": record.canonicalization_version,
            "object_type": record.object_type,
            "metadata": record.metadata_,
            "status_label": "3D ULPIN — SYSTEM GENERATED",
        }
    )


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

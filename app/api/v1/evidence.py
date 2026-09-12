"""Evidence and legal statutory traceability endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.evidence import EvidenceDecisionRecord, LegalValidationRecord
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.evidence import (
    EvidenceDecisionRecordCreate,
    EvidenceDecisionRecordOut,
    LegalValidationRecordCreate,
    LegalValidationRecordOut,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("/decisions", response_model=ApiResponse[EvidenceDecisionRecordOut], status_code=status.HTTP_201_CREATED)
async def create_evidence_decision(
    data: EvidenceDecisionRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    record = EvidenceDecisionRecord(**data.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=EvidenceDecisionRecordOut.model_validate(record))


@router.get("/decisions/{entity_id}", response_model=ApiResponse[List[EvidenceDecisionRecordOut]])
async def list_evidence_decisions(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(EvidenceDecisionRecord).where(EvidenceDecisionRecord.property_entity_id == entity_id).order_by(EvidenceDecisionRecord.timestamp.desc())
    )
    records = res.scalars().all()
    return ApiResponse(data=[EvidenceDecisionRecordOut.model_validate(r) for r in records])


@router.post("/legal-validation", response_model=ApiResponse[LegalValidationRecordOut], status_code=status.HTTP_201_CREATED)
async def create_legal_validation(
    data: LegalValidationRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR)),
):
    record = LegalValidationRecord(**data.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=LegalValidationRecordOut.model_validate(record))


@router.get("/legal-validation/{entity_id}", response_model=ApiResponse[List[LegalValidationRecordOut]])
async def list_legal_validations(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(LegalValidationRecord).where(LegalValidationRecord.property_entity_id == entity_id).order_by(LegalValidationRecord.validation_timestamp.desc())
    )
    records = res.scalars().all()
    return ApiResponse(data=[LegalValidationRecordOut.model_validate(r) for r in records])

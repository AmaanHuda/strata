"""ULPIN generation and lookup endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.db.models.user import User, UserRole
from app.db.models.ulpin import ULPINRecord
from app.db.session import get_db
from app.schemas.ulpin import ULPINGenerateRequest, ULPINOut, ULPINLookupResponse
from app.services.ulpin import ULPINService

router = APIRouter(prefix="/ulpin", tags=["ulpin"])


@router.post("/generate", response_model=ULPINOut, status_code=201)
async def generate_ulpin(
    req: ULPINGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = ULPINService(db)
    return await svc.generate(req, user.id)


@router.get("/lookup/{ulpin}", response_model=ULPINLookupResponse)
async def lookup_ulpin(
    ulpin: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = (await db.execute(select(ULPINRecord).where(ULPINRecord.ulpin == ulpin))).scalar_one_or_none()
    if not result:
        from fastapi import HTTPException
        raise HTTPException(404, f"ULPIN {ulpin} not found")
    return ULPINLookupResponse(
        ulpin=result.ulpin,
        entity_type=result.entity_type,
        entity_id=getattr(result, f"{result.entity_type}_id", None),
        is_provisional=result.is_provisional,
        is_authoritative=result.is_authoritative,
        legal_disclaimer=result.legal_disclaimer,
    )

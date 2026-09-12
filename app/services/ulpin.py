"""ULPIN generation service."""
import hashlib
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Parcel, Building, Floor, Unit
from app.db.models.ulpin import ULPINRecord
from app.schemas.ulpin import ULPINGenerateRequest


ENTITY_CODE = {"parcel": "P", "building": "B", "floor": "F", "unit": "U"}


def _compute_ulpin(entity_type: str, entity_id: UUID, district: str = "XX", taluk: str = "XXX", village: str = "XXXXXX") -> str:
    """
    Compute a deterministic ULPIN.
    Format: ST(2) + DT(2) + TK(3) + VL(6) + TYPE(1) + SEQ(8) + CHK(2)
    This is a candidate ULPIN â€” NOT an authoritative government ULPIN.
    """
    raw = f"{entity_type}:{str(entity_id)}"
    seq = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
    chk = hashlib.md5(raw.encode()).hexdigest()[:2].upper()
    state = "IN"
    dt = district[:2].upper().ljust(2, "X")
    tk = taluk[:3].upper().ljust(3, "X")
    vl = village[:6].upper().ljust(6, "X")
    code = ENTITY_CODE.get(entity_type, "X")
    return f"{state}{dt}{tk}{vl}{code}{seq}{chk}"


class ULPINService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, req: ULPINGenerateRequest, actor_id: UUID) -> ULPINRecord:
        # Validate entity exists
        entity_type = req.entity_type
        if entity_type == "parcel":
            obj = (await self.db.execute(select(Parcel).where(Parcel.id == req.entity_id))).scalar_one_or_none()
            district = obj.district if obj else "XX"
            taluk = (obj.taluk or "XXX") if obj else "XXX"
            village = (obj.village or "XXXXXX") if obj else "XXXXXX"
        elif entity_type == "building":
            obj = (await self.db.execute(select(Building).where(Building.id == req.entity_id))).scalar_one_or_none()
            district = "XX"; taluk = "XXX"; village = "XXXXXX"
        elif entity_type == "floor":
            obj = (await self.db.execute(select(Floor).where(Floor.id == req.entity_id))).scalar_one_or_none()
            district = "XX"; taluk = "XXX"; village = "XXXXXX"
        elif entity_type == "unit":
            obj = (await self.db.execute(select(Unit).where(Unit.id == req.entity_id))).scalar_one_or_none()
            district = "XX"; taluk = "XXX"; village = "XXXXXX"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown entity_type: {entity_type}")

        if not obj:
            raise HTTPException(status_code=404, detail=f"{entity_type} {req.entity_id} not found")

        ulpin_str = _compute_ulpin(entity_type, req.entity_id, district, taluk, village)

        # Check idempotency
        existing = (await self.db.execute(select(ULPINRecord).where(ULPINRecord.ulpin == ulpin_str))).scalar_one_or_none()
        if existing:
            return existing

        record = ULPINRecord(
            ulpin=ulpin_str,
            entity_type=entity_type,
            generation_method=req.generation_method,
            confidence_score="MEDIUM" if req.generation_method == "ml_derived" else "HIGH",
            is_provisional=(req.generation_method != "survey"),
            is_authoritative=False,
            created_by=actor_id,
        )
        setattr(record, f"{entity_type}_id", req.entity_id)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

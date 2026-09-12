"""
ULPIN generation and management service.
Differentiates between Official ULPIN (Government/Survey of India)
and Candidate/Proposed ULPINs (AI/System generated - Non-authoritative).
"""
import hashlib
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.schemas.ulpin import ULPINGenerateRequest


class ULPINService:
    """Service to generate and verify candidate and official ULPIN records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_parcel_ulpin(
        state: str = "DL",
        district: str = "01",
        taluk: Optional[str] = "001",
        village: Optional[str] = "000001",
        survey_number: str = "001",
    ) -> str:
        """
        Generates candidate parcel ULPIN:
        Format: <STATE(2)>-<DISTRICT(2)>-<TALUK(3)>-<VILLAGE(6)>-P-<SEQ(8)>
        """
        st = (state or "DL")[:2].upper().ljust(2, "X")
        dt = (district or "01")[:2].upper().ljust(2, "0")
        tk = (taluk or "001")[:3].upper().ljust(3, "0")
        vl = (village or "000001")[:6].upper().ljust(6, "0")
        
        raw_seed = f"{st}:{dt}:{tk}:{vl}:{survey_number}"
        seq = hashlib.sha256(raw_seed.encode()).hexdigest()[:8].upper()
        return f"{st}-{dt}-{tk}-{vl}-P-{seq}"

    @staticmethod
    def generate_vertical_unit_ulpin(
        parent_ulpin: str,
        floor_number: int,
        unit_number: str,
    ) -> str:
        """Generates candidate 3D vertical unit identifier."""
        flr_tag = f"F{floor_number}" if floor_number >= 0 else f"B{abs(floor_number)}"
        return f"{parent_ulpin}-{flr_tag}-U{unit_number}"

    async def generate_and_store(
        self,
        req: ULPINGenerateRequest,
        created_by: Optional[UUID] = None,
    ) -> ULPINRecord:
        """Generates candidate ULPIN and saves it to the registry."""
        entity_type = req.entity_type.lower()
        
        if entity_type == "parcel":
            parcel = await self.db.get(Parcel, req.entity_id)
            if not parcel:
                raise NotFoundError(f"Parcel {req.entity_id} not found")
            candidate = self.generate_parcel_ulpin(
                state=req.state,
                district=req.district,
                taluk=req.taluk or parcel.taluk,
                village=req.village or parcel.village,
                survey_number=parcel.parcel_number,
            )
            parcel.candidate_ulpin = candidate
            
            record = ULPINRecord(
                candidate_ulpin=candidate,
                official_ulpin=None,
                entity_type="parcel",
                parcel_id=parcel.id,
                status=ULPINStatus.CANDIDATE,
                generation_method="ml_derived",
                confidence_score="MEDIUM",
                is_authoritative=False,
                created_by=created_by,
            )
            self.db.add(record)
            await self.db.flush()
            return record

        elif entity_type in ["building", "floor", "unit"]:
            # Lookup parent hierarchy
            candidate = f"CAND-{req.state}-{req.district}-{entity_type.upper()[:1]}-{str(req.entity_id)[:8].upper()}"
            if entity_type == "floor" and req.floor_number is not None:
                candidate = f"{candidate}-F{req.floor_number}"
            elif entity_type == "unit" and req.unit_number:
                candidate = f"{candidate}-U{req.unit_number}"

            record = ULPINRecord(
                candidate_ulpin=candidate,
                official_ulpin=None,
                entity_type=entity_type,
                status=ULPINStatus.CANDIDATE,
                generation_method="ml_derived",
                confidence_score="MEDIUM",
                is_authoritative=False,
                created_by=created_by,
            )
            setattr(record, f"{entity_type}_id", req.entity_id)
            self.db.add(record)
            await self.db.flush()
            return record

        else:
            raise ValidationError(f"Unsupported entity type: {entity_type}")

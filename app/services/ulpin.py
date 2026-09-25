"""
ULPIN generation and management service.
Differentiates between Official ULPIN (Government/Survey of India - 14 alphanumeric Bhu-Aadhaar)
and Candidate/Proposed ULPINs (AI/System generated - Non-authoritative).
Strictly enforces:
- CANDIDATE vs VALIDATED vs OFFICIAL / EXTERNAL_REFERENCE states.
- Never fabricates official government ULPINs.
- Idempotent generation.
"""
import hashlib
import re
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.schemas.ulpin import ULPINGenerateRequest, ULPINValidateResponse


# Standard official Bhu-Aadhaar ULPIN pattern (14 alphanumeric characters)
OFFICIAL_ULPIN_REGEX = re.compile(r"^[A-Z0-9]{14}$")

# Candidate ULPIN pattern
CANDIDATE_ULPIN_REGEX = re.compile(
    r"^(CAND-[A-Z0-9\-]+|[A-Z]{2}-[0-9]{2}-[0-9]{3}-[0-9]{6}-[PBFU]-[A-Z0-9]+(?:-F-?[0-9]+)?(?:-U[A-Z0-9]+)?)$"
)


class ULPINService:
    """Service to generate, lookup, and validate candidate and official ULPIN records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def is_official_format(ulpin: str) -> bool:
        """Checks if string matches official 14-character Bhu-Aadhaar format."""
        return bool(OFFICIAL_ULPIN_REGEX.match(ulpin.strip().upper()))

    @staticmethod
    def is_candidate_format(ulpin: str) -> bool:
        """Checks if string matches candidate ULPIN format."""
        return bool(CANDIDATE_ULPIN_REGEX.match(ulpin.strip()))

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

    async def _derive_candidate_ulpin(self, entity_type: str, entity_id: UUID) -> str:
        """
        Derives a candidate identifier from the entity's cadastral parent chain.

        The internal entity UUID is NEVER embedded in the identifier and no
        official ULPIN is fabricated. Raises when no cadastral parent identifier
        exists yet so callers can never receive a made-up value.
        """
        if entity_type == "building":
            parent = await self.db.get(Building, entity_id)
            if not parent:
                raise NotFoundError(f"Building {entity_id} not found")
            parcel = (
                await self.db.get(Parcel, parent.parcel_id) if parent.parcel_id else None
            )
            prefix = (parcel.candidate_ulpin or parcel.official_ulpin) if parcel else None
            if not prefix:
                raise ValidationError(
                    f"Cannot derive a candidate ULPIN for building {entity_id}: its parcel "
                    "has no cadastral identifier yet. No identifier was fabricated."
                )
            ordinal = (
                await self.db.execute(
                    select(func.count())
                    .select_from(Building)
                    .where(Building.parcel_id == parent.parcel_id)
                )
            ).scalar() or 0
            return f"{prefix}-B{ordinal}"

        if entity_type == "floor":
            parent = await self.db.get(Floor, entity_id)
            if not parent:
                raise NotFoundError(f"Floor {entity_id} not found")
            building = (
                await self.db.get(Building, parent.building_id) if parent.building_id else None
            )
            prefix = (
                (building.candidate_ulpin or building.official_ulpin) if building else None
            )
            if not prefix:
                raise ValidationError(
                    f"Cannot derive a candidate ULPIN for floor {entity_id}: its building "
                    "has no candidate identifier yet. No identifier was fabricated."
                )
            return f"{prefix}-F{parent.floor_number}"

        parent = await self.db.get(Unit, entity_id)
        if not parent:
            raise NotFoundError(f"Unit {entity_id} not found")
        floor = await self.db.get(Floor, parent.floor_id) if parent.floor_id else None
        prefix = (floor.candidate_ulpin or floor.official_ulpin) if floor else None
        if not prefix:
            raise ValidationError(
                f"Cannot derive a candidate ULPIN for unit {entity_id}: its floor has no "
                "candidate identifier yet. No identifier was fabricated."
            )
        return f"{prefix}-U{parent.unit_number}"

    async def generate_and_store(
        self,
        req: ULPINGenerateRequest,
        created_by: Optional[UUID] = None,
    ) -> ULPINRecord:
        """
        Generates candidate ULPIN and saves it to the registry.
        Idempotent: returns existing record if already generated for entity.
        Never fabricates official government ULPIN.
        """
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

            # Check if existing record exists (Idempotency)
            res = await self.db.execute(
                select(ULPINRecord).where(
                    or_(
                        ULPINRecord.candidate_ulpin == candidate,
                        ULPINRecord.parcel_id == parcel.id,
                    )
                )
            )
            existing = res.scalar_one_or_none()
            if existing:
                return existing

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
            await self.db.commit()
            await self.db.refresh(record)
            return record

        elif entity_type in ["building", "floor", "unit"]:
            # Check existing
            col = getattr(ULPINRecord, f"{entity_type}_id")
            res = await self.db.execute(select(ULPINRecord).where(col == req.entity_id))
            existing = res.scalar_one_or_none()
            if existing:
                return existing

            # Candidate identifiers are derived from the cadastral parent chain
            # (parcel -> building -> floor -> unit), never from the internal UUID.
            candidate = await self._derive_candidate_ulpin(entity_type, req.entity_id)

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

            # Update entity's candidate_ulpin attribute if model exists
            model_cls = {"building": Building, "floor": Floor, "unit": Unit}[entity_type]
            entity_obj = await self.db.get(model_cls, req.entity_id)
            if entity_obj:
                entity_obj.candidate_ulpin = candidate

            self.db.add(record)
            await self.db.commit()
            await self.db.refresh(record)
            return record

        else:
            raise ValidationError(f"Unsupported entity type: {entity_type}")

    async def validate_ulpin(
        self,
        ulpin: str,
        entity_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
    ) -> ULPINValidateResponse:
        """
        Validates a candidate or official ULPIN string.
        Verifies:
        1. Syntax and pattern format.
        2. Registry lookup (matches ULPINRecord).
        3. Entity reference integrity (if entity_id provided).
        4. State classification: CANDIDATE | VALIDATED | OFFICIAL | EXTERNAL_REFERENCE | INVALID.
        """
        clean_ulpin = ulpin.strip()
        is_official = self.is_official_format(clean_ulpin)
        is_candidate = self.is_candidate_format(clean_ulpin)
        is_valid_format = is_official or is_candidate

        checks: Dict[str, Any] = {
            "format_valid": is_valid_format,
            "format_type": "official_bhu_aadhaar" if is_official else ("candidate_ulpin" if is_candidate else "unknown"),
            "character_length": len(clean_ulpin),
            "registry_matched": False,
            "entity_linkage_valid": False,
        }

        # Registry lookup
        stmt = select(ULPINRecord).where(
            or_(
                ULPINRecord.official_ulpin == clean_ulpin,
                ULPINRecord.candidate_ulpin == clean_ulpin,
            )
        )
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()

        status_result = ULPINStatus.INVALID
        matched_entity_id = None
        matched_entity_type = None
        is_officially_verified = False
        official_ulpin_val: Optional[str] = None
        candidate_property_id: Optional[str] = None

        if record:
            checks["registry_matched"] = True
            matched_entity_id = (
                record.parcel_id or record.building_id or record.floor_id or record.unit_id
            )
            matched_entity_type = record.entity_type
            
            if entity_id:
                checks["entity_linkage_valid"] = (matched_entity_id == entity_id)
            else:
                checks["entity_linkage_valid"] = True

            # If it's official and authoritative -> OFFICIAL
            if record.official_ulpin == clean_ulpin and record.is_authoritative:
                status_result = ULPINStatus.OFFICIAL
                is_officially_verified = True
                official_ulpin_val = clean_ulpin
                candidate_property_id = record.candidate_ulpin
            elif record.status == ULPINStatus.VALIDATED:
                status_result = ULPINStatus.VALIDATED
                candidate_property_id = record.candidate_ulpin
            else:
                # If format is valid and linkage holds, mark as VALIDATED candidate
                status_result = ULPINStatus.VALIDATED if checks["entity_linkage_valid"] else ULPINStatus.CANDIDATE
                candidate_property_id = record.candidate_ulpin
        else:
            # Not in registry
            if is_official:
                status_result = ULPINStatus.EXTERNAL_REFERENCE
                checks["notes"] = "Valid official format, but not yet verified or linked in local cadastral registry."
                candidate_property_id = clean_ulpin
            elif is_candidate:
                status_result = ULPINStatus.CANDIDATE
                checks["notes"] = "Syntactically valid candidate identifier, unregistered."
                candidate_property_id = clean_ulpin
            else:
                status_result = ULPINStatus.INVALID
                checks["errors"] = ["Identifier does not match official 14-char or candidate ULPIN syntax."]

        disclaimer = (
            "Official ULPINs represent legally gazetted cadastral identifiers. "
            "Candidate identifiers are analytical outputs and do not constitute legal property title."
        )

        return ULPINValidateResponse(
            ulpin=clean_ulpin,
            is_valid_format=is_valid_format,
            status=status_result,
            is_official=is_officially_verified,
            candidate_property_id=candidate_property_id,
            official_ulpin=official_ulpin_val,
            ulpin_format_valid=is_valid_format,
            ulpin_officially_verified=is_officially_verified,
            entity_type=matched_entity_type or entity_type,
            entity_id=matched_entity_id or entity_id,
            matched_in_registry=checks["registry_matched"],
            validation_checks=checks,
            legal_disclaimer=disclaimer,
        )


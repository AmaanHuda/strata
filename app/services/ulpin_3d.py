"""
Deterministic, versioned 3D ULPIN generation (``3D_GEOMETRY_HASH_V1``).

What this is
------------
A **SYSTEM-GENERATED** 3D cadastral identifier for a land parcel, the building
on it, each floor, and (when real unit geometry exists) each unit:

   3DULPIN-01-IN-{STATE}-{DISTRICT}-{PARCEL_ID}-{BUILDING_ID}-{FLOOR_CODE}-{UNIT_ID}-{CHECKSUM}

Example (illustrative):

   3DULPIN-01-IN-MH-MUM-P7K4X2Q9ABCDE-B3F8D1A2-F05-U001A7C2-X7KD

What this is NOT
----------------
It is *not* an official government Bhu-Aadhaar ULPIN. ``official_ulpin`` stays
NULL and ``is_authoritative`` stays False for everything this module produces.
The legacy service (:mod:`app.services.ulpin`) is untouched and keeps working;
this generator is additive and coexists with it.

Determinism
-----------
Every segment is a pure function of real, canonicalized inputs:

* ``PARCEL_ID``   = ``"P"`` + Base32(SHA256(country+state+district+context+canonical parcel geometry))[..12]
* ``BUILDING_ID`` = ``"B"`` + Base32(SHA256(parcel_id+canonical footprint+bucket(height,0.5)))[..8]
* ``FLOOR_CODE``  = ``F00`` ground, ``F01..`` above ground, ``B01..`` basement, ``E01..`` elevated
* ``UNIT_ID``     = ``"U"`` + Base32(SHA256(building_id+floor_code+canonical unit geometry+bucket(z_min,0.1)+bucket(z_max,0.1)))[..8]
* ``CHECKSUM``    = Base32(SHA256(full id without checksum))[..4]

No random UUIDs, timestamps, auto-increment ids, request ids or ML run ids ever
enter an identifier. The ML ``volume_id`` is provenance metadata only — it is
never used as a 3D ULPIN.

Aggregate sentinels
-------------------
The format has a fixed seven-segment shape, so aggregate levels use reserved
tokens that no real hash or floor derivation can produce (they contain ``0``,
which is not in the Base32 alphabet ``A-Z2-7``, and ``X00`` is not a derived
floor code):

* no building : ``B00000000``
* no floor    : ``X00``
* no unit     : ``U00000000``
* no parcel   : ``P000000000000``

Collision handling
------------------
A collision is never resolved by appending ``-2``. Instead the database UNIQUE
constraint is authoritative, the collision is logged at CRITICAL, and the
identifier is deterministically *widened* (longer hash segments) so it remains
a pure function of the same inputs. Nothing is ever overwritten or randomized.
"""
from __future__ import annotations

import base64
import hashlib
import re
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.services.geometry_canonical import (
    CANONICALIZATION_VERSION,
    GeometryCanonicalizationError,
    canonicalize_geometry,
    geometry_digest,
    height_bucket_key,
    z_bucket_key,
)

# --------------------------------------------------------------------------- #
# Versioned constants — never mutate these in place. Add a new version instead.
# --------------------------------------------------------------------------- #

ALGORITHM_VERSION = "3D_GEOMETRY_HASH_V1"
ULPIN_3D_FORMAT = "3DULPIN"
ULPIN_3D_FORMAT_VERSION = "01"
ULPIN_3D_COUNTRY = "IN"

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"  # RFC 4648, no padding

PARCEL_HASH_CHARS = 12
BUILDING_HASH_CHARS = 8
UNIT_HASH_CHARS = 8
CHECKSUM_CHARS = 4

# Widening ladder used only when a genuine hash collision is detected.
COLLISION_HASH_BONUS = (0, 4, 8, 12)

PARCEL_SENTINEL = "P" + "0" * PARCEL_HASH_CHARS
BUILDING_SENTINEL = "B" + "0" * BUILDING_HASH_CHARS
FLOOR_SENTINEL = "X00"
UNIT_SENTINEL = "U" + "0" * UNIT_HASH_CHARS

# Extensible object taxonomy (spec section 14). Not apartments-only.
OBJECT_LAND_PARCEL = "LAND_PARCEL"
OBJECT_BUILDING = "BUILDING"
OBJECT_APARTMENT = "APARTMENT"
OBJECT_OFFICE = "OFFICE"
OBJECT_PARKING = "PARKING"
OBJECT_UNDERGROUND = "UNDERGROUND"
OBJECT_ELEVATED = "ELEVATED"
OBJECT_AIR_RIGHT = "AIR_RIGHT"
OBJECT_UTILITY = "UTILITY"

OBJECT_TYPES: Tuple[str, ...] = (
    OBJECT_LAND_PARCEL,
    OBJECT_BUILDING,
    OBJECT_APARTMENT,
    OBJECT_OFFICE,
    OBJECT_PARKING,
    OBJECT_UNDERGROUND,
    OBJECT_ELEVATED,
    OBJECT_AIR_RIGHT,
    OBJECT_UTILITY,
)

FLOOR_CATEGORY_ABOVE = "above_ground"
FLOOR_CATEGORY_BELOW = "basement"
FLOOR_CATEGORY_ELEVATED = "elevated"

_ULPIN_3D_DISCLAIMER = (
    "SYSTEM-GENERATED 3D ULPIN (3D_GEOMETRY_HASH_V1). This is a deterministic analytical "
    "identifier derived from real source geometry and vertical information. It is NOT a "
    "government-issued Bhu-Aadhaar ULPIN, carries no legal title, and becomes a cadastral "
    "record only once verified and gazetted by a competent authority."
)

# Segment validation is keyed by the ``parse_3d_ulpin`` field names so a
# single-character mutation of any real segment is rejected.
_SEGMENT_PATTERNS = {
    "state": re.compile(r"^[A-Z0-9]{1,10}$"),
    "district": re.compile(r"^[A-Z0-9]{1,10}$"),
    "parcel_id": re.compile(rf"^(P[A-Z2-7]{{{PARCEL_HASH_CHARS}}}|P0{{{PARCEL_HASH_CHARS}}})$"),
    "building_id": re.compile(rf"^(B[A-Z2-7]{{{BUILDING_HASH_CHARS}}}|B0{{{BUILDING_HASH_CHARS}}})$"),
    "floor_code": re.compile(r"^([FBE]\d{2}|X00)$"),
    "unit_id": re.compile(rf"^(U[A-Z2-7]{{{UNIT_HASH_CHARS}}}|U0{{{UNIT_HASH_CHARS}}})$"),
    "checksum": re.compile(rf"^[A-Z2-7]{{{CHECKSUM_CHARS}}}$"),
}


class ULPIN3DError(ValueError):
    """Raised when a 3D ULPIN cannot be generated from the inputs supplied."""


class ULPIN3DCollisionError(RuntimeError):
    """Raised when a collision cannot be resolved deterministically."""


# --------------------------------------------------------------------------- #
# Primitive helpers
# --------------------------------------------------------------------------- #


def _base32(data: str, length: int) -> str:
    """First ``length`` Base32 (RFC 4648, no padding) characters of SHA-256(data)."""
    if length <= 0:
        raise ULPIN3DError("hash length must be > 0")
    digest = hashlib.sha256(data.encode("utf-8")).digest()
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")
    return encoded[:length]


def checksum(full_id_without_checksum: str) -> str:
    """4 Base32 characters over the full identifier with the checksum removed."""
    return _base32(full_id_without_checksum, CHECKSUM_CHARS)


# --------------------------------------------------------------------------- #
# Deterministic segments
# --------------------------------------------------------------------------- #


def parcel_id(
    *,
    country: str = ULPIN_3D_COUNTRY,
    state: str,
    district: str,
    admin_context: str = "",
    canonical_geometry: str,
    length: int = PARCEL_HASH_CHARS,
) -> str:
    """``P`` + Base32(SHA256(country+state+district+context+canonical geometry))."""
    if not canonical_geometry:
        raise ULPIN3DError("parcel geometry is required to derive a parcel id")
    seed = "|".join(
        [ALGORITHM_VERSION, "PARCEL", country, state, district, admin_context or "", canonical_geometry]
    )
    return "P" + _base32(seed, length)


def building_id(
    *,
    parent_parcel_id: str,
    canonical_footprint: str,
    height_m: Any,
    length: int = BUILDING_HASH_CHARS,
) -> str:
    """``B`` + Base32(SHA256(parcel_id+canonical footprint+bucket(height,0.5)))."""
    if not canonical_footprint:
        raise ULPIN3DError("building footprint is required to derive a building id")
    if height_m is None:
        raise ULPIN3DError(
            "building height is required: vertical information must exist before a "
            "3D ULPIN is generated (no value is invented)"
        )
    seed = "|".join(
        [
            ALGORITHM_VERSION,
            "BUILDING",
            parent_parcel_id,
            canonical_footprint,
            height_bucket_key(height_m),
        ]
    )
    return "B" + _base32(seed, length)


def floor_code(floor_number: int, category: str = FLOOR_CATEGORY_ABOVE) -> str:
    """
    Encode a floor deterministically (not hashed).

    ``F00`` ground, ``F01..F99`` above ground, ``B01..B99`` basement,
    ``E01..E99`` elevated/detached structures.
    """
    number = int(floor_number)
    if category == FLOOR_CATEGORY_ELEVATED:
        if number < 1:
            raise ULPIN3DError("elevated structures are numbered from 1")
        return f"E{number:02d}"
    if category == FLOOR_CATEGORY_BELOW or number < 0:
        if number == 0:
            return "F00"
        return f"B{abs(number):02d}"
    if number > 99:
        raise ULPIN3DError("floor number exceeds the two-digit F/B/E code space")
    return f"F{number:02d}"


def unit_id(
    *,
    parent_building_id: str,
    parent_floor_code: str,
    canonical_unit_geometry: str,
    z_min: Any,
    z_max: Any,
    length: int = UNIT_HASH_CHARS,
) -> str:
    """``U`` + Base32(SHA256(building_id+floor_code+canonical unit geometry+z buckets))."""
    if not canonical_unit_geometry:
        raise ULPIN3DError("unit geometry is required to derive a unit id")
    if z_min is None or z_max is None:
        raise ULPIN3DError(
            "unit z_min/z_max are required: no unit 3D ULPIN is generated without a "
            "real vertical range"
        )
    seed = "|".join(
        [
            ALGORITHM_VERSION,
            "UNIT",
            parent_building_id,
            parent_floor_code,
            canonical_unit_geometry,
            z_bucket_key(z_min),
            z_bucket_key(z_max),
        ]
    )
    return "U" + _base32(seed, length)


# --------------------------------------------------------------------------- #
# Assembly / validation
# --------------------------------------------------------------------------- #


def assemble_3d_ulpin(
    *,
    state: str,
    district: str,
    parcel: Optional[str],
    building: Optional[str],
    floor: Optional[str],
    unit: Optional[str],
) -> str:
    """Assemble the canonical 7-segment 3D ULPIN and append its checksum."""
    body = "-".join(
        [
            ULPIN_3D_FORMAT,
            ULPIN_3D_FORMAT_VERSION,
            ULPIN_3D_COUNTRY,
            (state or "").upper(),
            (district or "").upper(),
            parcel or PARCEL_SENTINEL,
            building or BUILDING_SENTINEL,
            floor or FLOOR_SENTINEL,
            unit or UNIT_SENTINEL,
        ]
    )
    return f"{body}-{checksum(body)}"


def parse_3d_ulpin(ulpin: str) -> Optional[Dict[str, str]]:
    """Split a 3D ULPIN into its segments, or ``None`` when malformed."""
    if not isinstance(ulpin, str):
        return None
    parts = ulpin.strip().split("-")
    if len(parts) != 10:
        return None
    keys = (
        "format",
        "format_version",
        "country",
        "state",
        "district",
        "parcel_id",
        "building_id",
        "floor_code",
        "unit_id",
        "checksum",
    )
    return dict(zip(keys, parts))


def validate_3d_ulpin(ulpin: str) -> bool:
    """
    Recompute the checksum and verify the shape of every segment.

    Returns ``False`` for any single-character mutation of a valid identifier.
    """
    segments = parse_3d_ulpin(ulpin)
    if segments is None:
        return False
    if segments["format"] != ULPIN_3D_FORMAT:
        return False
    if segments["format_version"] != ULPIN_3D_FORMAT_VERSION:
        return False
    if segments["country"] != ULPIN_3D_COUNTRY:
        return False
    for key in ("state", "district", "parcel_id", "building_id", "floor_code", "unit_id", "checksum"):
        pattern = _SEGMENT_PATTERNS[key]
        if not pattern.match(segments[key]):
            return False
    body = "-".join(ulpin.strip().split("-")[:-1])
    return checksum(body) == segments["checksum"]


def is_3d_ulpin(value: Optional[str]) -> bool:
    """Cheap prefix test used by the model/registry layer."""
    return isinstance(value, str) and value.startswith(f"{ULPIN_3D_FORMAT}-")


def canonical_geometry_hash(geometry: Any) -> str:
    """Thin pass-through so callers do not import the canonical module directly."""
    return geometry_digest(geometry)


# --------------------------------------------------------------------------- #
# Registry integration (reuses ULPINRecord — no duplicate table)
# --------------------------------------------------------------------------- #


class ULPIN3DService:
    """Materialise and reuse 3D ULPINs in the existing ``ulpin_records`` registry."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------------- queries

    async def _existing_for_entity(self, entity_type: str, entity_id: UUID) -> Optional[ULPINRecord]:
        link_col = {
            "parcel": ULPINRecord.parcel_id,
            "building": ULPINRecord.building_id,
            "floor": ULPINRecord.floor_id,
            "unit": ULPINRecord.unit_id,
        }[entity_type]
        res = await self.db.execute(
            select(ULPINRecord).where(
                link_col == entity_id,
                ULPINRecord.algorithm_version == ALGORITHM_VERSION,
            )
        )
        return res.scalars().first()

    async def _by_candidate(self, candidate: str) -> Optional[ULPINRecord]:
        res = await self.db.execute(
            select(ULPINRecord).where(ULPINRecord.candidate_ulpin == candidate)
        )
        return res.scalars().first()

    @staticmethod
    def _record_entity_id(record: ULPINRecord) -> Optional[UUID]:
        """
        The entity a record identifies.

        Records also carry their cadastral ancestors (a building record stores its
        ``parcel_id`` for provenance), so the *entity_type* column decides which id
        is the identity — falling back to the ancestor order only when it is unset.
        """
        by_type = {
            "parcel": record.parcel_id,
            "building": record.building_id,
            "floor": record.floor_id,
            "unit": record.unit_id,
        }
        return (
            by_type.get(record.entity_type)
            or record.parcel_id
            or record.building_id
            or record.floor_id
            or record.unit_id
        )

    # ------------------------------------------------------------ persistence

    async def _upsert(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        links: Dict[str, Optional[UUID]],
        candidate_factory: Callable[[int], str],
        geometry_hash: str,
        object_type: str,
        provenance: Dict[str, Any],
        created_by: Optional[UUID] = None,
        confidence: str = "MEDIUM",
    ) -> Tuple[ULPINRecord, bool]:
        """
        Create or refresh the 3D ULPIN record for one entity.

        Returns ``(record, created)``. Reuses the stored record when the canonical
        geometry hash and algorithm version are unchanged (spec section 35).
        """
        metadata: Dict[str, Any] = {
            "algorithm_version": ALGORITHM_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "object_type": object_type,
            "geometry_hash": geometry_hash,
            "provenance": provenance,
            "is_authoritative": False,
            "status_label": "3D ULPIN — SYSTEM GENERATED",
        }

        existing = await self._existing_for_entity(entity_type, entity_id)
        bonus = 0
        candidate = candidate_factory(0)

        if existing is not None:
            prior_meta = existing.metadata_ or {}
            if prior_meta.get("geometry_hash") == geometry_hash and not prior_meta.get(
                "collision_escalation"
            ):
                return existing, False  # unchanged inputs -> reuse the stored ID
            # Inputs changed: recompute deterministically, re-running collision widening.
            candidate, _ = await self._resolve_candidate_with_flag(
                candidate_factory, entity_type, entity_id
            )
            existing.candidate_ulpin = candidate
            existing.metadata_ = metadata
            existing.object_type = object_type
            existing.algorithm_version = ALGORITHM_VERSION
            existing.canonicalization_version = CANONICALIZATION_VERSION
            return existing, False

        candidate, collision = await self._resolve_candidate_with_flag(
            candidate_factory, entity_type, entity_id
        )
        if collision["escalated"]:
            metadata["collision_escalation"] = collision
            metadata["geometry_hash"] = geometry_hash
        metadata["id_segments"] = _segment_summary(candidate)

        record = ULPINRecord(
            candidate_ulpin=candidate,
            official_ulpin=None,  # never fabricated
            entity_type=entity_type,
            status=ULPINStatus.CANDIDATE,
            parcel_id=links.get("parcel_id"),
            building_id=links.get("building_id"),
            floor_id=links.get("floor_id"),
            unit_id=links.get("unit_id"),
            generation_method=ALGORITHM_VERSION,
            confidence_score=confidence,
            is_authoritative=False,
            legal_disclaimer=_ULPIN_3D_DISCLAIMER,
            algorithm_version=ALGORITHM_VERSION,
            canonicalization_version=CANONICALIZATION_VERSION,
            object_type=object_type,
            metadata_=metadata,
            created_by=created_by,
        )
        self.db.add(record)
        return record, True

    async def _resolve_candidate_with_flag(
        self,
        candidate_factory: Callable[[int], str],
        entity_type: str,
        entity_id: UUID,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Walk the widening ladder until the candidate does not clash with another
        entity. Never appends ``-2``; never randomizes; never overwrites silently.
        """
        report: Dict[str, Any] = {"escalated": False, "attempts": []}
        for bonus in COLLISION_HASH_BONUS:
            candidate = candidate_factory(bonus)
            clash = await self._by_candidate(candidate)
            if clash is None:
                if bonus:
                    report["escalated"] = True
                    report["resolved_at_bonus"] = bonus
                    report["resolved_with"] = candidate
                    report["reason"] = (
                        "Truncated hash collision with an existing different entity; "
                        "identifier deterministically widened (no -2 suffix, no random value)."
                    )
                return candidate, report
            if self._record_entity_id(clash) == entity_id:
                return candidate, report  # already ours (idempotent re-run)
            report["attempts"].append(
                {"bonus": bonus, "candidate": candidate, "collides_with_entity": str(self._record_entity_id(clash))}
            )
            logger.critical(
                "3D ULPIN collision detected — escalating hash width",
                algorithm_version=ALGORITHM_VERSION,
                entity_type=entity_type,
                entity_id=str(entity_id),
                candidate=candidate,
                colliding_entity=str(self._record_entity_id(clash)),
                hash_bonus=bonus,
            )
        raise ULPIN3DCollisionError(
            "Unresolvable 3D ULPIN collision after widening the hash to "
            f"{COLLISION_HASH_BONUS[-1]} extra characters for {entity_type} {entity_id}. "
            "No identifier was overwritten and no random value was generated."
        )

    # ------------------------------------------------------- public entrypoints

    async def sync_building(
        self,
        building_uuid: UUID,
        *,
        created_by: Optional[UUID] = None,
        state_code: Optional[str] = None,
        district_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Materialise the parcel/building/floor (and, with real geometry, unit)
        3D ULPINs for one building. Idempotent and reuse-friendly.

        Entities whose real geometry/vertical inputs are missing are reported in
        ``skipped`` with a reason — no identifier is invented for them.
        """
        stmt = (
            select(Building)
            .options(selectinload(Building.floors).selectinload(Floor.units))
            .where(Building.id == building_uuid, Building.is_active == True)  # noqa: E712
        )
        building = (await self.db.execute(stmt)).scalar_one_or_none()
        if building is None:
            raise ULPIN3DError(f"Building {building_uuid} not found or inactive")

        parcel = await self.db.get(Parcel, building.parcel_id) if building.parcel_id else None
        codes = _resolve_codes(parcel, state_code, district_code)

        result: Dict[str, Any] = {
            "algorithm_version": ALGORITHM_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "parcel": None,
            "building": None,
            "floors": {},
            "units": {},
            "skipped": [],
        }

        # --- parcel ---------------------------------------------------------- #
        parcel_segment: Optional[str] = None
        if parcel is None:
            result["skipped"].append({"entity": "parcel", "reason": "building has no parcel"})
        else:
            parcel_geojson = await self._parcel_geometry(parcel)
            if parcel_geojson is None:
                result["skipped"].append(
                    {"entity": "parcel", "id": str(parcel.id), "reason": "no parcel geometry"}
                )
            else:
                try:
                    canonical = canonicalize_geometry(parcel_geojson)
                except GeometryCanonicalizationError as exc:
                    result["skipped"].append(
                        {"entity": "parcel", "id": str(parcel.id), "reason": str(exc)}
                    )
                else:
                    context = f"{parcel.state or ''}/{parcel.district or ''}/{parcel.village or ''}/{parcel.parcel_number or ''}"

                    def _parcel_factory(bonus: int, _c=canonical, _ctx=context) -> str:
                        seg = parcel_id(
                            state=codes["state_code"],
                            district=codes["district_code"],
                            admin_context=_ctx,
                            canonical_geometry=_c,
                            length=PARCEL_HASH_CHARS + bonus,
                        )
                        return assemble_3d_ulpin(
                            state=codes["state_code"], district=codes["district_code"],
                            parcel=seg, building=None, floor=None, unit=None,
                        )

                    record, created = await self._upsert(
                        entity_type="parcel",
                        entity_id=parcel.id,
                        links={"parcel_id": parcel.id},
                        candidate_factory=_parcel_factory,
                        geometry_hash=geometry_digest(parcel_geojson),
                        object_type=OBJECT_LAND_PARCEL,
                        provenance=_parcel_provenance(parcel, codes),
                        created_by=created_by,
                        confidence="MEDIUM",
                    )
                    parcel_segment = _segment_summary(record.candidate_ulpin)["parcel_id"]
                    result["parcel"] = _record_summary(record, created)
                    # NOTE: the entities' own ``candidate_ulpin`` columns (varchar(50))
                    # keep their LEGACY cadastral identifiers. The 3D ULPIN is
                    # deliberately NOT copied into them — it lives in ulpin_records and
                    # is served as ``three_d_ulpin``, so legacy IDs stay reproducible.

        # --- building -------------------------------------------------------- #
        building_segment: Optional[str] = None
        footprint_geojson = await self._building_geometry(building)
        if footprint_geojson is None:
            result["skipped"].append(
                {"entity": "building", "id": str(building.id), "reason": "no building footprint"}
            )
        elif building.height_m is None:
            result["skipped"].append(
                {
                    "entity": "building",
                    "id": str(building.id),
                    "reason": "no real height (m) — no 3D ULPIN is generated without vertical information",
                }
            )
        else:
            try:
                canonical = canonicalize_geometry(footprint_geojson)
            except GeometryCanonicalizationError as exc:
                result["skipped"].append(
                    {"entity": "building", "id": str(building.id), "reason": str(exc)}
                )
            else:
                anchor_parcel = parcel_segment or PARCEL_SENTINEL

                def _building_factory(bonus: int, _c=canonical, _p=anchor_parcel) -> str:
                    seg = building_id(
                        parent_parcel_id=_p,
                        canonical_footprint=_c,
                        height_m=building.height_m,
                        length=BUILDING_HASH_CHARS + bonus,
                    )
                    return assemble_3d_ulpin(
                        state=codes["state_code"], district=codes["district_code"],
                        parcel=parcel_segment, building=seg, floor=None, unit=None,
                    )

                record, created = await self._upsert(
                    entity_type="building",
                    entity_id=building.id,
                    links={"building_id": building.id, "parcel_id": building.parcel_id},
                    candidate_factory=_building_factory,
                    geometry_hash=geometry_digest(footprint_geojson),
                    object_type=_building_object_type(building),
                    provenance=_building_provenance(building, codes),
                    created_by=created_by,
                    confidence="MEDIUM" if (building.height_confidence or 0) else "LOW",
                )
                building_segment = _segment_summary(record.candidate_ulpin)["building_id"]
                result["building"] = _record_summary(record, created)

        # --- floors ---------------------------------------------------------- #
        for floor in sorted(building.floors or [], key=lambda f: f.floor_number):
            if not floor.is_active:
                continue
            z_min, z_max = _floor_z_range(floor)
            if building_segment is None:
                result["skipped"].append(
                    {"entity": "floor", "id": str(floor.id), "reason": "no building 3D ULPIN"}
                )
                continue
            if z_min is None or z_max is None:
                result["skipped"].append(
                    {
                        "entity": "floor",
                        "id": str(floor.id),
                        "reason": "floor has no stored vertical range (height_above_ground_m/ceiling_height_m)",
                    }
                )
                continue
            code = floor_code(floor.floor_number)
            floor_geom = _floor_geometry_geojson(footprint_geojson, floor)
            geometry_hash = (
                geometry_digest(floor_geom)
                if floor_geom is not None
                else f"{CANONICALIZATION_VERSION}:vertical:{z_bucket_key(z_min)}:{z_bucket_key(z_max)}"
            )

            def _floor_factory(bonus: int, _code=code) -> str:
                # Floor codes are not hashed; the building segment carries identity,
                # and widening extends the building segment on collision.
                seg = _code
                if bonus:
                    seg = _code + _base32(f"{building_segment}|{_code}", bonus)
                return assemble_3d_ulpin(
                    state=codes["state_code"], district=codes["district_code"],
                    parcel=parcel_segment, building=building_segment, floor=seg, unit=None,
                )

            record, created = await self._upsert(
                entity_type="floor",
                entity_id=floor.id,
                links={
                    "floor_id": floor.id,
                    "building_id": building.id,
                    "parcel_id": building.parcel_id,
                },
                candidate_factory=_floor_factory,
                geometry_hash=geometry_hash,
                object_type=OBJECT_APARTMENT if floor.floor_use != "parking" else OBJECT_PARKING,
                provenance={
                    **_floor_provenance(floor),
                    "z_min_m": z_min,
                    "z_max_m": z_max,
                    "z_bucket_m": z_bucket_key(z_min),
                },
                created_by=created_by,
                confidence="MEDIUM" if floor.ml_confidence_score is not None else "LOW",
            )
            summary = _record_summary(record, created)
            summary["floor_code"] = code
            summary["z_min_m"] = z_min
            summary["z_max_m"] = z_max
            result["floors"][str(floor.id)] = summary

            # --- units (only when real unit geometry exists) ----------------- #
            for unit in sorted(floor.units or [], key=lambda u: u.unit_number):
                if not unit.is_active:
                    continue
                unit_geojson = await self._unit_geometry(unit)
                u_z_min, u_z_max = _unit_z_range(unit, floor)
                if unit_geojson is None:
                    result["skipped"].append(
                        {
                            "entity": "unit",
                            "id": str(unit.id),
                            "reason": "unit geometry_3d is not stored — no fabricated unit hash",
                        }
                    )
                    continue
                if u_z_min is None or u_z_max is None:
                    result["skipped"].append(
                        {"entity": "unit", "id": str(unit.id), "reason": "unit has no vertical range"}
                    )
                    continue
                try:
                    unit_canonical = canonicalize_geometry(unit_geojson)
                except GeometryCanonicalizationError as exc:
                    result["skipped"].append(
                        {"entity": "unit", "id": str(unit.id), "reason": str(exc)}
                    )
                    continue

                def _unit_factory(bonus: int, _c=unit_canonical, _fc=code, _zmin=u_z_min, _zmax=u_z_max) -> str:
                    seg = unit_id(
                        parent_building_id=building_segment or BUILDING_SENTINEL,
                        parent_floor_code=_fc,
                        canonical_unit_geometry=_c,
                        z_min=_zmin,
                        z_max=_zmax,
                        length=UNIT_HASH_CHARS + bonus,
                    )
                    return assemble_3d_ulpin(
                        state=codes["state_code"], district=codes["district_code"],
                        parcel=parcel_segment, building=building_segment, floor=_fc, unit=seg,
                    )

                record, created = await self._upsert(
                    entity_type="unit",
                    entity_id=unit.id,
                    links={
                        "unit_id": unit.id,
                        "floor_id": floor.id,
                        "building_id": building.id,
                        "parcel_id": building.parcel_id,
                    },
                    candidate_factory=_unit_factory,
                    geometry_hash=geometry_digest(unit_geojson),
                    object_type=OBJECT_APARTMENT,
                    provenance={
                        **_unit_provenance(unit),
                        "z_min_m": u_z_min,
                        "z_max_m": u_z_max,
                        "volume_id": (unit.metadata_ or {}).get("volume_id"),
                    },
                    created_by=created_by,
                    confidence="MEDIUM" if unit.ml_confidence_score is not None else "LOW",
                )
                summary = _record_summary(record, created)
                summary["z_min_m"] = u_z_min
                summary["z_max_m"] = u_z_max
                result["units"][str(unit.id)] = summary

        try:
            await self.db.commit()
        except Exception as exc:  # UNIQUE violation is authoritative (spec section 11)
            await self.db.rollback()
            raise ULPIN3DCollisionError(
                "Registry rejected a 3D ULPIN write (likely a UNIQUE collision). "
                "Nothing was overwritten. Re-run after inspecting ulpin_records."
            ) from exc

        return result

    # ------------------------------------------------------------ geometry IO

    async def _geojson_from_column(self, model, column, entity_id: UUID) -> Optional[Dict[str, Any]]:
        from sqlalchemy import func as sql_func

        res = await self.db.execute(
            select(sql_func.ST_AsGeoJSON(column)).where(model.id == entity_id)
        )
        raw = res.scalar()
        if not raw:
            return None
        import json

        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def _parcel_geometry(self, parcel: Parcel) -> Optional[Dict[str, Any]]:
        geojson = await self._geojson_from_column(Parcel, Parcel.geometry_2d, parcel.id)
        if geojson is not None:
            return geojson
        if parcel.boundary_wkt:
            try:
                from shapely import wkt as shapely_wkt
                from shapely.geometry import mapping

                return mapping(shapely_wkt.loads(parcel.boundary_wkt))
            except Exception:
                return None
        return None

    async def _building_geometry(self, building: Building) -> Optional[Dict[str, Any]]:
        geojson = await self._geojson_from_column(Building, Building.footprint_2d, building.id)
        if geojson is not None:
            return geojson
        if building.footprint_wkt:
            try:
                from shapely import wkt as shapely_wkt
                from shapely.geometry import mapping

                return mapping(shapely_wkt.loads(building.footprint_wkt))
            except Exception:
                return None
        return None

    async def _unit_geometry(self, unit: Unit) -> Optional[Dict[str, Any]]:
        if unit.geometry_3d is None:
            return None
        geojson = await self._geojson_from_column(Unit, Unit.geometry_3d, unit.id)
        if geojson is None and isinstance(unit.geometry_3d, str):
            # Fall back to parsing the stored WKT directly (mirrors parcel/building).
            try:
                from shapely import wkt as shapely_wkt
                from shapely.geometry import mapping

                parsed = shapely_wkt.loads(unit.geometry_3d)
                gtype = getattr(parsed, "geom_type", "")
                if gtype in {"Polygon", "MultiPolygon"}:
                    geojson = mapping(parsed)
                elif gtype in {"GeometryCollection", "MultiSurface"}:
                    geojson = mapping(parsed)
            except Exception:
                return None
        if geojson is None:
            return None
        # Only polygonal volume geometry can carry a canonical footprint.
        if geojson.get("type") in {"Polygon", "MultiPolygon"}:
            return geojson
        return None


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _resolve_codes(
    parcel: Optional[Parcel], state_code: Optional[str], district_code: Optional[str]
) -> Dict[str, str]:
    from app.services.cadastral_codes import assign_cadastral_codes

    meta_codes = ((parcel.metadata_ or {}).get("cadastral_codes") if parcel and parcel.metadata_ else None) or {}
    codes = assign_cadastral_codes(
        state=(parcel.state if parcel else None),
        district=(parcel.district if parcel else None),
        taluk=(parcel.taluk if parcel else None),
        village=(parcel.village if parcel else None),
    )
    return {
        "state_code": (state_code or meta_codes.get("state_code") or codes.state_code or "IN").upper(),
        "district_code": (district_code or meta_codes.get("district_code") or codes.district_code or "00").upper(),
        "district_name": codes.district_name,
        "state_name": codes.state_name,
    }


def _segment_summary(candidate: str) -> Dict[str, Any]:
    return parse_3d_ulpin(candidate) or {"raw": candidate}


def _floor_z_range(floor: Floor) -> Tuple[Optional[float], Optional[float]]:
    if floor.height_above_ground_m is None:
        return None, None
    z_min = float(floor.height_above_ground_m)
    ceiling = floor.ceiling_height_m
    if ceiling is None:
        return None, None
    return z_min, z_min + float(ceiling)


def _unit_z_range(unit: Unit, floor: Floor) -> Tuple[Optional[float], Optional[float]]:
    meta = unit.metadata_ or {}
    z_min = meta.get("z_min_m")
    z_max = meta.get("z_max_m")
    if z_min is not None and z_max is not None:
        return float(z_min), float(z_max)
    # Fall back to the enclosing floor's stored vertical range (real, not invented).
    return _floor_z_range(floor)


def _floor_geometry_geojson(
    building_footprint: Optional[Dict[str, Any]], floor: Floor
) -> Optional[Dict[str, Any]]:
    """A floor's plan geometry is the real footprint; vertical range is separate."""
    return building_footprint


def _building_object_type(building: Building) -> str:
    return OBJECT_BUILDING


def _parcel_provenance(parcel: Parcel, codes: Dict[str, str]) -> Dict[str, Any]:
    meta = parcel.metadata_ or {}
    return {
        "source": "cadastral_parcel_geometry",
        "source_id": meta.get("osm_reference") or parcel.parcel_number,
        "geometry_source": "parcels.geometry_2d",
        "state": codes.get("state_name"),
        "district": codes.get("district_name"),
        "parcel_number": parcel.parcel_number,
    }


def _building_provenance(building: Building, codes: Dict[str, str]) -> Dict[str, Any]:
    meta = building.metadata_ or {}
    return {
        "source": meta.get("source_url") or "buildings.footprint_2d",
        "source_id": meta.get("osm_reference"),
        "geometry_source": "buildings.footprint_2d",
        "height_source": meta.get("height_source"),
        "floor_source": meta.get("floor_source"),
        "ml_model_version": building.ml_model_version,
        "ml_confidence": building.ml_confidence_score,
        "ml_volume_id": (meta.get("ml") or {}).get("volume_id"),
        "render_volume_id": meta.get("volume_id"),
        "state": codes.get("state_name"),
        "district": codes.get("district_name"),
    }


def _floor_provenance(floor: Floor) -> Dict[str, Any]:
    meta = floor.metadata_ or {}
    return {
        "source": "floors",
        "source_id": str(floor.id),
        "geometry_source": "building footprint extent over the stored vertical range",
        "floor_source": meta.get("floor_source"),
        "height_basis": meta.get("height_basis"),
    }


def _unit_provenance(unit: Unit) -> Dict[str, Any]:
    meta = unit.metadata_ or {}
    return {
        "source": "units",
        "source_id": str(unit.id),
        "geometry_source": "units.geometry_3d",
        "unit_delineation": meta.get("unit_delineation"),
        "volume_id": meta.get("volume_id"),
    }


def _record_summary(record: ULPINRecord, created: bool) -> Dict[str, Any]:
    return {
        "ulpin": record.candidate_ulpin,
        "entity_type": record.entity_type,
        "object_type": record.object_type,
        "algorithm_version": record.algorithm_version,
        "canonicalization_version": record.canonicalization_version,
        "is_authoritative": record.is_authoritative,
        "official_ulpin": record.official_ulpin,
        "status": record.status,
        "created": created,
    }


__all__ = [
    "ALGORITHM_VERSION",
    "CANONICALIZATION_VERSION",
    "ULPIN_3D_FORMAT",
    "ULPIN_3D_FORMAT_VERSION",
    "BASE32_ALPHABET",
    "PARCEL_HASH_CHARS",
    "BUILDING_HASH_CHARS",
    "UNIT_HASH_CHARS",
    "CHECKSUM_CHARS",
    "COLLISION_HASH_BONUS",
    "PARCEL_SENTINEL",
    "BUILDING_SENTINEL",
    "FLOOR_SENTINEL",
    "UNIT_SENTINEL",
    "OBJECT_TYPES",
    "ULPIN3DError",
    "ULPIN3DCollisionError",
    "ULPIN3DService",
    "checksum",
    "parcel_id",
    "building_id",
    "floor_code",
    "unit_id",
    "assemble_3d_ulpin",
    "parse_3d_ulpin",
    "validate_3d_ulpin",
    "is_3d_ulpin",
    "canonical_geometry_hash",
]

"""One-off repair for candidate ULPINs that were derived from the internal UUID.

Historically two code paths built candidate identifiers by slicing the entity's
internal UUID, e.g. ``CAND-MA-MU-B-D59E7AED`` for building
``d59e7aed-d00e-4d64-bacb-a1793df26794``. That is wrong: an internal UUID must
never be presented as a ULPIN.

This script rewrites ONLY such identifiers, deriving the replacement from the
cadastral parent chain exactly like the fixed pipeline does:

* building -> ``<parcel candidate ULPIN>-B<n>``  (n = ordinal within parcel)
* floor    -> ``<building candidate ULPIN>-F<floor_number>``
* unit     -> ``<floor candidate ULPIN>-U<unit_number>``

It never invents an official ULPIN and never touches ``official_ulpin`` columns
or any ``is_authoritative`` record. If a parcel has no candidate identifier yet,
the deterministic cadastral candidate is derived from the parcel's own
attributes (same function the import pipeline uses) - no randomness involved.

Run without ``--apply`` first to preview, then with ``--apply`` to persist.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord
from app.db.session import AsyncSessionLocal
from app.services.ulpin import ULPINService


def _uuid_prefix(entity_id) -> str:
    return str(entity_id).split("-")[0].upper()


def _is_uuid_derived(value, entity_id, tag: str) -> bool:
    """True when ``value`` looks like ``CAND-<ST>-<DT>-<tag>-<uuid8>...`` for this entity."""
    if not value:
        return False
    parts = value.split("-")
    if len(parts) < 5 or parts[0] != "CAND" or parts[3] != tag:
        return False
    return parts[4].upper() == _uuid_prefix(entity_id)


async def _repoint_records(db, old_value: str, new_value: str, column: str, entity_id) -> int:
    """Repoints the non-authoritative ULPINRecord carrying ``old_value`` to ``new_value``."""
    stmt = select(ULPINRecord).where(
        ULPINRecord.candidate_ulpin == old_value,
        ULPINRecord.is_authoritative.is_(False),
        getattr(ULPINRecord, column) == entity_id,
    )
    records = (await db.execute(stmt)).scalars().all()
    for rec in records:
        rec.candidate_ulpin = new_value
    return len(records)


async def _parcel_prefix(db, parcel: Parcel, changed: list) -> str:
    """Returns the parcel's cadastral candidate ULPIN, deriving it deterministically if absent."""
    if parcel.candidate_ulpin:
        return parcel.candidate_ulpin
    derived = ULPINService.generate_parcel_ulpin(
        state=(parcel.state or "IN")[:2].upper(),
        district=(parcel.district or "00")[:2].upper(),
        taluk=parcel.taluk,
        village=parcel.village,
        survey_number=parcel.parcel_number,
    )
    parcel.candidate_ulpin = derived
    changed.append(f"parcel {parcel.id}: candidate_ulpin -> {derived}")
    return derived


async def repair(apply: bool) -> int:
    changed: list = []
    async with AsyncSessionLocal() as db:
        # 1. Buildings (needs the parcel prefix). Ordinal = position within the parcel.
        buildings = (
            await db.execute(select(Building).order_by(Building.created_at, Building.id))
        ).scalars().all()
        ordinals: dict = {}
        for bldg in buildings:
            key = str(bldg.parcel_id)
            ordinals[key] = ordinals.get(key, 0) + 1
            old = bldg.candidate_ulpin
            if not _is_uuid_derived(old, bldg.id, "B"):
                continue
            parcel = await db.get(Parcel, bldg.parcel_id) if bldg.parcel_id else None
            if parcel is None:
                changed.append(f"building {bldg.id}: SKIPPED (no parcel) - stays {old}")
                continue
            new = f"{await _parcel_prefix(db, parcel, changed)}-B{ordinals[key]}"
            bldg.candidate_ulpin = new
            n = await _repoint_records(db, old, new, "building_id", bldg.id)
            changed.append(f"building {bldg.id}: {old} -> {new} ({n} registry record(s))")

        # 2. Floors (needs the repaired building prefix)
        floors = (
            await db.execute(select(Floor).order_by(Floor.created_at, Floor.id))
        ).scalars().all()
        for flr in floors:
            old = flr.candidate_ulpin
            if not _is_uuid_derived(old, flr.id, "F"):
                continue
            bldg = await db.get(Building, flr.building_id) if flr.building_id else None
            prefix = (bldg.candidate_ulpin or bldg.official_ulpin) if bldg else None
            if not prefix:
                changed.append(f"floor {flr.id}: SKIPPED (building has no identifier) - stays {old}")
                continue
            new = f"{prefix}-F{flr.floor_number}"
            flr.candidate_ulpin = new
            n = await _repoint_records(db, old, new, "floor_id", flr.id)
            changed.append(f"floor {flr.id}: {old} -> {new} ({n} registry record(s))")

        # 3. Units (needs the repaired floor prefix)
        units = (
            await db.execute(select(Unit).order_by(Unit.created_at, Unit.id))
        ).scalars().all()
        for unit in units:
            old = unit.candidate_ulpin
            if not _is_uuid_derived(old, unit.id, "U"):
                continue
            flr = await db.get(Floor, unit.floor_id) if unit.floor_id else None
            prefix = (flr.candidate_ulpin or flr.official_ulpin) if flr else None
            if not prefix:
                changed.append(f"unit {unit.id}: SKIPPED (floor has no identifier) - stays {old}")
                continue
            new = f"{prefix}-U{unit.unit_number}"
            unit.candidate_ulpin = new
            n = await _repoint_records(db, old, new, "unit_id", unit.id)
            changed.append(f"unit {unit.id}: {old} -> {new} ({n} registry record(s))")

        if apply:
            await db.commit()

    for line in changed:
        print(line)
    print(f"\n{'Applied' if apply else 'DRY RUN'}: {len(changed)} identifier(s) affected.")
    if not apply and changed:
        print("Re-run with --apply to persist these changes.")
    return len(changed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="persist the repairs (default: dry run)")
    args = parser.parse_args()
    asyncio.run(repair(apply=args.apply))

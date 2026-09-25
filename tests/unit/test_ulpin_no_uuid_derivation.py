"""Regression guard: a displayed ULPIN must never be derived from the internal UUID.

The UI once showed ``CAND-MA-MU-B-D59E7AED`` for the building whose backend UUID is
``d59e7aed-d00e-4d64-bacb-a1793df26794`` - the trailing segment was the entity UUID.
Candidate identifiers must come from the cadastral parent chain instead:
parcel -> building (-B<n>) -> floor (-F<n>) -> unit (-U<n>).
"""
import re
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.errors import ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.services.ulpin import ULPINService

BACKEND = Path(__file__).resolve().parents[2]


class _FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    """Minimal session stub: entity lookup plus a fixed count for ordinal queries."""

    def __init__(self, entities, count=1):
        self.entities = entities
        self._count = count

    async def get(self, model, ident):
        return self.entities.get(ident)

    async def execute(self, statement, *args, **kwargs):
        return _FakeResult(scalar=self._count)


def _make_parcel(candidate_ulpin="MA-MU-AND-VIL-P-ABC12345"):
    parcel = Parcel(
        parcel_number="PARCEL-MU-00001",
        district="Mumbai",
        taluk="Andheri",
        village="Village",
        state="Maharashtra",
    )
    parcel.id = uuid4()
    parcel.candidate_ulpin = candidate_ulpin
    return parcel


@pytest.mark.asyncio
async def test_building_candidate_ulpin_comes_from_parcel_not_uuid():
    parcel = _make_parcel()
    building = Building(parcel_id=parcel.id)
    building.id = uuid4()
    svc = ULPINService(_FakeSession({parcel.id: parcel, building.id: building}, count=1))

    value = await svc._derive_candidate_ulpin("building", building.id)

    assert value == f"{parcel.candidate_ulpin}-B1"
    assert str(building.id).split("-")[0].upper() not in value


@pytest.mark.asyncio
async def test_floor_and_unit_candidate_ulpins_chain_from_parent():
    parcel = _make_parcel()
    building = Building(parcel_id=parcel.id)
    building.id = uuid4()
    building.candidate_ulpin = f"{parcel.candidate_ulpin}-B1"

    floor = Floor(building_id=building.id, floor_number=2)
    floor.id = uuid4()

    unit = Unit(floor_id=floor.id, unit_number="201")
    unit.id = uuid4()

    svc = ULPINService(
        _FakeSession({parcel.id: parcel, building.id: building, floor.id: floor, unit.id: unit})
    )

    floor_value = await svc._derive_candidate_ulpin("floor", floor.id)
    assert floor_value == f"{building.candidate_ulpin}-F2"

    floor.candidate_ulpin = floor_value
    unit_value = await svc._derive_candidate_ulpin("unit", unit.id)
    assert unit_value == f"{floor_value}-U201"

    for value, entity in ((floor_value, floor), (unit_value, unit)):
        assert str(entity.id).split("-")[0].upper() not in value


@pytest.mark.asyncio
async def test_building_without_cadastral_parent_raises_instead_of_fabricating():
    parcel = _make_parcel(candidate_ulpin=None)
    building = Building(parcel_id=parcel.id)
    building.id = uuid4()
    svc = ULPINService(_FakeSession({parcel.id: parcel, building.id: building}))

    with pytest.raises(ValidationError):
        await svc._derive_candidate_ulpin("building", building.id)


def test_no_source_line_builds_a_ulpin_from_a_uuid_prefix():
    """No backend module may slice an entity UUID into something presented as a ULPIN."""
    offenders = []
    for path in (BACKEND / "app").rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "candidate_ulpin" not in line and "CAND-" not in line:
                continue
            if re.search(r"\[:8\]", line):
                offenders.append(f"{path.relative_to(BACKEND)}:{lineno}: {line.strip()}")
    assert not offenders, "ULPIN built from a UUID prefix:\n" + "\n".join(offenders)


def test_dataset_import_derives_building_ulpin_from_the_parcel():
    source = (BACKEND / "app" / "api" / "v1" / "datasets.py").read_text(encoding="utf-8")
    if "import-buildings-geojson" not in source:
        pytest.skip("GeoJSON import endpoint is not part of this revision")
    assert "building.candidate_ulpin = f\"{parcel.candidate_ulpin}-B{buildings_in_parcel}\"" in source
    assert "str(building.id)" not in source

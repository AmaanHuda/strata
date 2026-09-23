"""
Unit tests proving:
1. Units remain associated with their correct explicit floor.
2. Multiple floors work correctly.
3. Multiple units per floor work correctly.
"""
import pytest
import uuid
from app.db.models.property import Building, Floor, Parcel, Unit, ScientificStatus
from app.integrations.ml_engine.contracts import (
    MLBuildingIngest,
    MLFloorIngest,
    MLIngestionPayload,
    MLUnitIngest,
)
from app.integrations.ml_engine.mapper import MLDataMapper
from app.services.ingestion import MLIngestionService
from app.db.models.user import User
from tests.conftest import MockAsyncSession, MockDbStore


@pytest.mark.asyncio
async def test_multi_floor_multi_unit_explicit_mapping():
    """
    Validates that in a building with 3 floors and 2 units per floor:
    - Floor 1 has Unit 101, 102
    - Floor 2 has Unit 201, 202
    - Floor 3 has Unit 301, 302
    Each unit is attached to its designated floor ID, not lumped onto Floor 1.
    """
    store = MockDbStore()
    session = MockAsyncSession(store)
    service = MLIngestionService(session)

    user = User(
        id=uuid.uuid4(),
        email="surveyor@cadastre.gov.in",
        username="surveyor1",
        role="SURVEYOR"
    )

    # 3 floors, 2 units per floor
    floors = [
        MLFloorIngest(
            floor_number=1,
            floor_label="Floor 1",
            height_above_ground_m=0.0,
            ceiling_height_m=3.0,
            units=[
                MLUnitIngest(unit_number="101", area_sqm=75.0, confidence=0.85),
                MLUnitIngest(unit_number="102", area_sqm=80.0, confidence=0.85),
            ]
        ),
        MLFloorIngest(
            floor_number=2,
            floor_label="Floor 2",
            height_above_ground_m=3.0,
            ceiling_height_m=3.0,
            units=[
                MLUnitIngest(unit_number="201", area_sqm=75.0, confidence=0.85),
                MLUnitIngest(unit_number="202", area_sqm=80.0, confidence=0.85),
            ]
        ),
        MLFloorIngest(
            floor_number=3,
            floor_label="Floor 3",
            height_above_ground_m=6.0,
            ceiling_height_m=3.0,
            units=[
                MLUnitIngest(unit_number="301", area_sqm=75.0, confidence=0.85),
                MLUnitIngest(unit_number="302", area_sqm=80.0, confidence=0.85),
            ]
        ),
    ]

    building = MLBuildingIngest(
        building_name="Tower-A",
        footprint_wkt="POLYGON((77.2000 28.6000, 77.2010 28.6000, 77.2010 28.6010, 77.2000 28.6010, 77.2000 28.6000))",
        height_m=9.0,
        floor_count=3,
        floors=floors,
    )

    payload = MLIngestionPayload(
        parcel_number="DL-ND-2026-UNIT-TEST",
        district="New Delhi",
        state="DL",
        model_name="3D-Mapping-Engine",
        model_version="v2.0",
        buildings=[building],
    )

    res = await service.ingest_ml_payload(payload, user)
    assert res["success"] is True
    assert res["floors_created"] == 3
    assert res["units_created"] == 6

    # Verify each unit is linked to its correct parent floor
    created_floors = {
        v.floor_number: v for v in store.entities.values() if isinstance(v, Floor)
    }
    assert len(created_floors) == 3

    created_units = [v for v in store.entities.values() if isinstance(v, Unit)]
    assert len(created_units) == 6

    # Floor 1 units
    flr1_units = [u for u in created_units if u.floor_id == created_floors[1].id]
    flr1_unit_nums = {u.unit_number for u in flr1_units}
    assert flr1_unit_nums == {"101", "102"}

    # Floor 2 units
    flr2_units = [u for u in created_units if u.floor_id == created_floors[2].id]
    flr2_unit_nums = {u.unit_number for u in flr2_units}
    assert flr2_unit_nums == {"201", "202"}

    # Floor 3 units
    flr3_units = [u for u in created_units if u.floor_id == created_floors[3].id]
    flr3_unit_nums = {u.unit_number for u in flr3_units}
    assert flr3_unit_nums == {"301", "302"}

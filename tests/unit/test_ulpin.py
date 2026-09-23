"""Unit tests for ULPIN generator."""
from app.services.ulpin import ULPINService


def test_parcel_ulpin_generation():
    ulpin = ULPINService.generate_parcel_ulpin(
        state="DL",
        district="01",
        taluk="002",
        village="000456",
        survey_number="101/A",
    )
    assert ulpin.startswith("DL-01-002-000456-P-")
    assert len(ulpin) > 20


def test_vertical_unit_ulpin_generation():
    parent = "DL-01-002-000456-P-123456"
    unit_ulpin = ULPINService.generate_vertical_unit_ulpin(
        parent_ulpin=parent,
        floor_number=3,
        unit_number="302",
    )
    assert unit_ulpin == f"{parent}-F3-U302"


import pytest
from tests.conftest import MockAsyncSession, MockDbStore
from app.db.models.ulpin import ULPINRecord, ULPINStatus
import uuid


@pytest.mark.asyncio
async def test_ulpin_unverified_format_is_not_official():
    """Valid 14-char format must NEVER be reported as is_official=True without government registry proof."""
    store = MockDbStore()
    session = MockAsyncSession(store)
    service = ULPINService(session)

    # 14-character valid Bhu-Aadhaar format, but unregistered
    res = await service.validate_ulpin("1234567890ABCD")
    assert res.is_valid_format is True
    assert res.ulpin_format_valid is True
    assert res.is_official is False  # CRITICAL: must NOT be official
    assert res.ulpin_officially_verified is False
    assert res.official_ulpin is None
    assert res.status == ULPINStatus.EXTERNAL_REFERENCE


@pytest.mark.asyncio
async def test_ulpin_authoritative_record_is_official():
    """Registered authoritative record correctly validates as official."""
    store = MockDbStore()
    session = MockAsyncSession(store)
    service = ULPINService(session)

    record = ULPINRecord(
        id=uuid.uuid4(),
        candidate_ulpin="CAND-DL-01-P-001",
        official_ulpin="1234567890ABCD",
        entity_type="parcel",
        status=ULPINStatus.OFFICIAL,
        is_authoritative=True,
    )
    store.save(record)

    res = await service.validate_ulpin("1234567890ABCD")
    assert res.is_valid_format is True
    assert res.is_official is True
    assert res.ulpin_officially_verified is True
    assert res.official_ulpin == "1234567890ABCD"
    assert res.status == ULPINStatus.OFFICIAL


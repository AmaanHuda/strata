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

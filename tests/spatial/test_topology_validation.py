"""Cadastral topology validation tests."""
from uuid import uuid4
from app.schemas.validation import ValidationStatus
from app.services.topology_validation import TopologyValidationService


def test_building_contained_in_parcel():
    parcel_wkt = "POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))"
    building_wkt = "POLYGON((10 10, 50 10, 50 50, 10 50, 10 10))"

    res = TopologyValidationService.validate_building_in_parcel(parcel_wkt, building_wkt)
    assert res.status == ValidationStatus.PASS
    assert "fully contained" in res.message


def test_building_outside_parcel():
    parcel_wkt = "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"
    building_wkt = "POLYGON((50 50, 60 50, 60 60, 50 60, 50 50))"

    res = TopologyValidationService.validate_building_in_parcel(parcel_wkt, building_wkt)
    assert res.status == ValidationStatus.FAIL


def test_full_topology_validation_report():
    report = TopologyValidationService.run_full_validation(
        property_id=uuid4(),
        entity_type="building",
        parcel_wkt="POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))",
        building_wkt="POLYGON((10 10, 40 10, 40 40, 10 40, 10 10))",
        floors_data=[
            {"floor_number": 0, "ceiling_height_m": 3.0},
            {"floor_number": 1, "ceiling_height_m": 3.0},
        ],
    )
    assert report.overall_status in [ValidationStatus.PASS, ValidationStatus.WARNING]
    assert report.score >= 90.0

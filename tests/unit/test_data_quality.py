"""Data quality evaluation tests."""
from app.services.data_quality import DataQualityService, QualityGrade


def test_data_quality_high():
    res = DataQualityService.evaluate(
        has_geometry=True,
        is_geometry_valid=True,
        crs="EPSG:4326",
        confidence_score=0.95,
        has_height=True,
        has_floors=True,
        source_authority="Survey of India",
    )
    assert res["grade"] == QualityGrade.HIGH
    assert res["score"] >= 85.0


def test_data_quality_insufficient():
    res = DataQualityService.evaluate(
        has_geometry=False,
        is_geometry_valid=False,
        crs="UNKNOWN",
        confidence_score=0.1,
    )
    assert res["grade"] == QualityGrade.INSUFFICIENT
    assert res["score"] < 40.0

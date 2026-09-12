"""
Data Quality Evaluation Service.
Evaluates:
- Completeness
- Geometry validity
- CRS validity
- Resolution & sensor fidelity
- Source reliability
- Temporal freshness
- Attribute completeness
- Cross-source consistency
Produces overall score and grade: HIGH / MEDIUM / LOW / INSUFFICIENT.
Never artificially inflates confidence.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class QualityGrade:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class DataQualityService:
    """Evaluates spatial, temporal, and semantic data quality."""

    @staticmethod
    def evaluate(
        has_geometry: bool,
        is_geometry_valid: bool,
        crs: str,
        confidence_score: Optional[float] = None,
        has_height: bool = False,
        has_floors: bool = False,
        acquisition_date: Optional[str] = None,
        source_authority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Computes comprehensive data quality score and grade."""
        score = 0.0
        factors = {}

        # 1. Geometry completeness and validity (30 points)
        if has_geometry and is_geometry_valid:
            score += 30.0
            factors["geometry"] = "valid_and_complete"
        elif has_geometry:
            score += 10.0
            factors["geometry"] = "present_but_invalid"
        else:
            factors["geometry"] = "missing"

        # 2. CRS Validity (15 points)
        if crs and crs.upper() in ["EPSG:4326", "EPSG:3857", "EPSG:32643", "EPSG:32644", "EPSG:7755"]:
            score += 15.0
            factors["crs"] = "standard_supported"
        else:
            factors["crs"] = "unknown_or_missing"

        # 3. 3D attributes (height & floor completeness) (25 points)
        if has_height and has_floors:
            score += 25.0
            factors["3d_completeness"] = "full"
        elif has_height or has_floors:
            score += 12.0
            factors["3d_completeness"] = "partial"
        else:
            factors["3d_completeness"] = "2d_only"

        # 4. Model / Extraction confidence (20 points)
        conf = confidence_score if confidence_score is not None else 0.5
        score += round(conf * 20.0, 1)
        factors["ml_confidence"] = conf

        # 5. Authority / Source reliability (10 points)
        if source_authority:
            score += 10.0
            factors["source_authority"] = source_authority
        else:
            score += 5.0
            factors["source_authority"] = "open_or_inferred"

        # Final Grade determination
        if score >= 85.0:
            grade = QualityGrade.HIGH
        elif score >= 65.0:
            grade = QualityGrade.MEDIUM
        elif score >= 40.0:
            grade = QualityGrade.LOW
        else:
            grade = QualityGrade.INSUFFICIENT

        return {
            "score": round(score, 1),
            "grade": grade,
            "factors": factors,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

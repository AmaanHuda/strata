"""Cadastral topology and 3D geometry validation schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus:
    PASS = "PASS"
    WARNING = "WARNING"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class ValidationCheckResult(BaseModel):
    check_name: str
    status: str = Field(..., description="PASS, WARNING, REVIEW, FAIL")
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PropertyValidationReport(BaseModel):
    property_id: UUID
    entity_type: str
    overall_status: str
    score: float
    is_authoritative_ready: bool
    checks: List[ValidationCheckResult]
    validated_at: datetime
    summary: str

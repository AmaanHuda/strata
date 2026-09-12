from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvidenceDecisionRecordCreate(BaseModel):
    property_entity_id: UUID
    property_entity_type: str
    attribute_name: str
    attribute_value: Optional[str] = None
    source: str
    evidence_state: str = "CANDIDATE"
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    validation_status: str
    model_version: Optional[str] = None
    is_authoritative: bool = False


class EvidenceDecisionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_entity_id: UUID
    property_entity_type: str
    attribute_name: str
    attribute_value: Optional[str] = None
    source: str
    evidence_state: str
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    validation_status: str
    model_version: Optional[str] = None
    is_authoritative: bool
    timestamp: datetime


class LegalValidationRecordCreate(BaseModel):
    property_entity_id: UUID
    property_entity_type: str
    jurisdiction: str
    applicable_framework: str
    rule_version: str
    validation_status: str
    evidence_source: str
    remarks: Optional[str] = None


class LegalValidationRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_entity_id: UUID
    property_entity_type: str
    jurisdiction: str
    applicable_framework: str
    rule_version: str
    validation_status: str
    evidence_source: str
    remarks: Optional[str] = None
    validation_timestamp: datetime

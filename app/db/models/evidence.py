import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.models.property import ScientificStatus


class EvidenceDecisionRecord(Base):
    __tablename__ = "evidence_decision_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    property_entity_type = Column(String(50), nullable=False)  # "PARCEL", "BUILDING", "FLOOR", "UNIT"
    attribute_name = Column(String(100), nullable=False)
    attribute_value = Column(String(255), nullable=True)
    
    source = Column(String(100), nullable=False)
    evidence_state = Column(String(50), default=ScientificStatus.CANDIDATE, nullable=False)
    confidence = Column(Float, nullable=True)
    uncertainty = Column(Float, nullable=True)
    
    validation_status = Column(String(50), nullable=False)
    model_version = Column(String(100), nullable=True)
    is_authoritative = Column(Boolean, default=False, nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class LegalValidationRecord(Base):
    __tablename__ = "legal_validation_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    property_entity_type = Column(String(50), nullable=False)
    
    jurisdiction = Column(String(100), nullable=False)
    applicable_framework = Column(String(255), nullable=False)
    rule_version = Column(String(50), nullable=False)
    
    validation_status = Column(String(50), nullable=False)
    evidence_source = Column(String(100), nullable=False)
    remarks = Column(Text, nullable=True)
    
    validation_timestamp = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

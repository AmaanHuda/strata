"""Provenance records for data lineage tracking."""
import uuid

from sqlalchemy import Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False, index=True)  # parcel, building, floor, unit, ulpin
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    data_source = Column(String(255), nullable=False)  # dataset name / ML model / survey
    derivation_method = Column(String(100), nullable=False)  # direct, inferred, ml_predicted, surveyed
    input_datasets = Column(JSONB, nullable=True)  # list of dataset IDs used
    model_version = Column(String(100), nullable=True)
    input_hash = Column(String(128), nullable=True)  # SHA-256 of input data
    confidence_label = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW, INSUFFICIENT
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

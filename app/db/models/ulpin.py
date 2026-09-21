"""
ULPIN (Unique Land Parcel Identification Number) record model.
Supports official authority ULPIN and proposed/candidate identifiers.
Official ULPIN is nullable and never fabricated.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, text, Index
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class ULPINStatus:
    PROPOSED = "PROPOSED"
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    NON_AUTHORITATIVE = "NON_AUTHORITATIVE"
    OFFICIAL = "OFFICIAL"
    AUTHORITATIVE = "AUTHORITATIVE"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"
    INVALID = "INVALID"


class ULPINRecord(Base):
    """
    ULPIN Registry for all cadastral entities.
    Distinguishes clearly between official authoritative ULPINs
    and AI/candidate proposed identifiers.
    """
    __tablename__ = "ulpin_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Candidate identifier (e.g. CAND-DL-01-002-000456-U-001)
    candidate_ulpin = Column(String(60), unique=True, nullable=False, index=True)
    
    # Official government assigned ULPIN (NULLABLE - never auto-fabricated)
    official_ulpin = Column(String(30), unique=True, nullable=True, index=True)
    
    entity_type = Column(String(20), nullable=False)  # parcel, building, floor, unit
    status = Column(String(30), default=ULPINStatus.CANDIDATE, nullable=False)

    # FK to entity (only one is set depending on entity_type)
    parcel_id = Column(UUID(as_uuid=True), ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True)
    building_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True)
    floor_id = Column(UUID(as_uuid=True), ForeignKey("floors.id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)

    # Generation metadata
    generation_method = Column(String(50), nullable=False)  # manual, ml_derived, survey
    confidence_score = Column(String(20), default="MEDIUM", nullable=True)  # HIGH, MEDIUM, LOW, INSUFFICIENT
    is_authoritative = Column(Boolean, default=False, nullable=False)

    # Legal note
    legal_disclaimer = Column(
        Text,
        default=(
            "AI-derived vertical unit assignments and candidate ULPINs are analytical/candidate "
            "outputs (NON-AUTHORITATIVE) and do not constitute legal title or authoritative "
            "cadastral records unless verified and gazetted by a competent government authority."
        ),
        nullable=False,
    )

    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    parcel = relationship("Parcel", back_populates="ulpin_records")
    building = relationship("Building", back_populates="ulpin_records")
    floor = relationship("Floor", back_populates="ulpin_records")
    unit = relationship("Unit", back_populates="ulpin_records")

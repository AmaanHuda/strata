"""ULPIN (Unique Land Parcel Identification Number) record model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey,
                         String, Text, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class ULPINRecord(Base):
    """
    A ULPIN is assigned to each addressable cadastral entity.
    Format: <STATE(2)><DISTRICT(2)><TALUK(3)><VILLAGE(6)><ENTITY_TYPE(1)><SEQ(6)><CHECK(2)>
    For vertical units: ULPIN contains floor + unit suffix.
    """
    __tablename__ = "ulpin_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ulpin = Column(String(30), unique=True, nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)  # parcel, building, floor, unit

    # FK to entity (only one will be set)
    parcel_id = Column(UUID(as_uuid=True), ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True)
    building_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True)
    floor_id = Column(UUID(as_uuid=True), ForeignKey("floors.id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)

    # Generation metadata
    generation_method = Column(String(50), nullable=False)  # manual, ml_derived, survey
    confidence_score = Column(String(10), nullable=True)    # HIGH, MEDIUM, LOW
    is_provisional = Column(Boolean, default=True, nullable=False)
    is_authoritative = Column(Boolean, default=False, nullable=False)

    # Legal note
    legal_disclaimer = Column(Text, default=(
        "AI-derived vertical unit assignments are analytical/candidate outputs "
        "and do not constitute authoritative legal cadastral records unless "
        "verified and published by a competent authority."
    ))

    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.now(timezone.utc), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    parcel = relationship("Parcel", back_populates="ulpin_records")
    floor = relationship("Floor", back_populates="ulpin_records")
    unit = relationship("Unit", back_populates="ulpin_records")

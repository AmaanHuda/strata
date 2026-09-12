"""Dataset registry â€“ metadata for all ingested spatial datasets."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class DatasetRegistry(Base):
    __tablename__ = "dataset_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    source = Column(String(500), nullable=True)
    authority = Column(String(255), nullable=True)
    license = Column(String(255), nullable=True)
    acquisition_date = Column(DateTime(timezone=True), nullable=True)
    validation_status = Column(String(50), nullable=True)
    modality = Column(String(100), nullable=True)  # satellite, lidar, survey, etc.
    crs = Column(String(50), nullable=True)
    resolution_m = Column(String(50), nullable=True)
    coverage_area = Column(Text, nullable=True)
    record_count = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)
    ingested_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

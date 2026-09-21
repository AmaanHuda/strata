"""
Async job tracking for ML inference, batch validations, and long-running tasks.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class JobStatus:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RUNNING = "RUNNING"  # Backward compatibility alias for PROCESSING
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AsyncJob(Base):
    """Tracks background ML processing and validation pipelines."""
    __tablename__ = "async_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=JobStatus.QUEUED, index=True)
    progress = Column(Float, default=0.0, nullable=False)  # 0.0 to 100.0
    progress_message = Column(Text, nullable=True)

    # Payloads and results
    payload = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Retries and Idempotency
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    idempotency_key = Column(String(255), unique=True, index=True, nullable=True)

    # Creator & Models
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(100), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # User relation
    creator = relationship("User", foreign_keys=[created_by])

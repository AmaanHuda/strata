"""Async job tracking for ML inference and long-running tasks."""
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class AsyncJob(Base):
    __tablename__ = "async_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(100), nullable=False, index=True)  # ml_inference, height_estimation, etc.
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, running, done, failed
    celery_task_id = Column(String(255), nullable=True)
    priority = Column(Integer, default=5, nullable=False)
    progress_pct = Column(Float, nullable=True)
    progress_message = Column(Text, nullable=True)
    input_payload = Column(JSONB, nullable=True)
    result_payload = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    submitted_by = Column(UUID(as_uuid=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

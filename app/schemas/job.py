"""Async job tracking schemas."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class JobSubmitRequest(BaseModel):
    job_type: str
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="input_payload")
    idempotency_key: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    priority: int = 5


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    job_type: str
    status: str
    progress: float = 0.0
    progress_message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

"""Async job schemas."""
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JobSubmitRequest(BaseModel):
    job_type: str
    input_payload: Optional[Dict[str, Any]] = None
    priority: int = 5


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_type: str
    status: str
    progress_pct: Optional[float]
    progress_message: Optional[str]
    result_payload: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

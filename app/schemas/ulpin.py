"""ULPIN generation and query schemas."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ULPINGenerateRequest(BaseModel):
    entity_type: str = Field(..., description="parcel, building, floor, or unit")
    entity_id: UUID
    district: str = Field(..., max_length=100)
    state: str = Field("DL", max_length=10)
    taluk: Optional[str] = None
    village: Optional[str] = None
    floor_number: Optional[int] = None
    unit_number: Optional[str] = None
    is_official_request: bool = False


class ULPINOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    candidate_ulpin: str
    official_ulpin: Optional[str] = None
    entity_type: str
    status: str = "CANDIDATE"
    generation_method: str = "ml_derived"
    confidence_score: Optional[str] = "MEDIUM"
    is_authoritative: bool = False
    legal_disclaimer: str
    created_at: datetime


class ULPINLookupResponse(BaseModel):
    ulpin: str
    is_official: bool
    status: str
    entity_type: str
    entity_id: Optional[UUID] = None
    entity_details: Optional[Dict[str, Any]] = None
    legal_disclaimer: str

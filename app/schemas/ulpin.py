"""ULPIN generation and lookup schemas."""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ULPINGenerateRequest(BaseModel):
    entity_type: str  # parcel | building | floor | unit
    entity_id: UUID
    generation_method: str = "ml_derived"  # manual | ml_derived | survey


class ULPINOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ulpin: str
    entity_type: str
    generation_method: str
    confidence_score: Optional[str]
    is_provisional: bool
    is_authoritative: bool
    legal_disclaimer: str
    created_at: datetime


class ULPINLookupResponse(BaseModel):
    ulpin: str
    entity_type: str
    entity_id: Optional[UUID]
    is_provisional: bool
    is_authoritative: bool
    legal_disclaimer: str

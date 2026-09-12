"""Search query and response schemas."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    entity_type: str
    entity_id: UUID
    identifier: str
    official_ulpin: Optional[str] = None
    candidate_ulpin: Optional[str] = None
    status: str
    location_summary: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]

"""Standard envelope responses and shared primitives."""
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[DataT]):
    """Standard API response envelope."""
    model_config = ConfigDict(populate_by_name=True)
    success: bool = True
    data: Optional[DataT] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[ErrorDetail] = None


class PaginatedMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[DataT]):
    items: List[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    environment: str
    components: Dict[str, str] = Field(default_factory=dict)

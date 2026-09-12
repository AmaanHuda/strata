"""Provenance Service for data lineage and audit tracking."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provenance import ProvenanceRecord
from app.db.repositories.base import BaseRepository


class ProvenanceService:
    """Records lineage, input sources, ML models, and processing CRS for all property entities."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaseRepository(ProvenanceRecord, db)

    async def record_lineage(
        self,
        entity_type: str,
        entity_id: UUID,
        data_source: str,
        derivation_method: str,
        input_datasets: Optional[List[str]] = None,
        model_version: Optional[str] = None,
        input_hash: Optional[str] = None,
        confidence_label: Optional[str] = "MEDIUM",
        notes: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> ProvenanceRecord:
        """Persists an immutable provenance lineage record."""
        return await self.repo.create({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data_source": data_source,
            "derivation_method": derivation_method,
            "input_datasets": input_datasets or [],
            "model_version": model_version,
            "input_hash": input_hash,
            "confidence_label": confidence_label,
            "notes": notes,
            "created_by": created_by,
        })

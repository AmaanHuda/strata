"""
Dataset Registry Service.
Tracks metadata for spatial datasets (GeoJSON, GeoTIFF, DEM, DSM, LiDAR, Cadastral vectors, etc.)
Backend only registers and inspects metadata; does not perform ML processing.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models.dataset import DatasetRegistry
from app.db.models.user import User
from app.db.repositories.base import BaseRepository
from app.schemas.dataset import DatasetRegisterRequest


SUPPORTED_MODALITIES = {
    "satellite", "lidar", "dem", "dsm", "drone",
    "cadastral_vector", "osm", "point_cloud", "ml_json"
}


class DatasetService:
    """Service to register and query spatial dataset metadata."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaseRepository(DatasetRegistry, db)

    async def register_dataset(self, req: DatasetRegisterRequest, user: User) -> DatasetRegistry:
        """Registers a new spatial dataset metadata manifest."""
        mod = req.modality.lower()
        if mod not in SUPPORTED_MODALITIES:
            raise ValidationError(f"Unsupported modality: {req.modality}. Supported: {list(SUPPORTED_MODALITIES)}")

        existing = await self.db.execute(
            select(DatasetRegistry).where(DatasetRegistry.name == req.name)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Dataset with name '{req.name}' is already registered")

        dataset = await self.repo.create({
            "name": req.name,
            "version": req.version,
            "source": req.source,
            "license": req.license,
            "modality": mod,
            "crs": req.crs,
            "resolution_m": req.resolution_m,
            "coverage_area": req.coverage_area,
            "record_count": req.record_count,
            "is_active": True,
            "metadata_": req.metadata_ or {},
            "created_by": user.id,
        })
        return dataset

    async def list_datasets(self, modality: Optional[str] = None) -> List[DatasetRegistry]:
        """Lists registered datasets."""
        stmt = select(DatasetRegistry).where(DatasetRegistry.is_active == True)
        if modality:
            stmt = stmt.where(DatasetRegistry.modality == modality.lower())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_dataset(self, dataset_id: UUID) -> DatasetRegistry:
        """Gets dataset by ID."""
        ds = await self.repo.get(dataset_id)
        if not ds:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        return ds

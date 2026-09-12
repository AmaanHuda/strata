"""Generic async repository providing CRUD operations."""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: UUID) -> Optional[ModelType]:
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 20, **filters) -> List[ModelType]:
        stmt = select(self.model)
        for k, v in filters.items():
            if hasattr(self.model, k) and v is not None:
                stmt = stmt.where(getattr(self.model, k) == v)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters) -> int:
        stmt = select(func.count()).select_from(self.model)
        for k, v in filters.items():
            if hasattr(self.model, k) and v is not None:
                stmt = stmt.where(getattr(self.model, k) == v)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create(self, data: Dict[str, Any]) -> ModelType:
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelType, data: Dict[str, Any]) -> ModelType:
        for k, v in data.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.db.delete(obj)
        await self.db.flush()

"""Parcel spatial queries."""
from typing import List, Optional
from uuid import UUID

from geoalchemy2.functions import ST_Contains, ST_DWithin, ST_GeomFromText, ST_Intersects
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Parcel
from app.db.repositories.base import BaseRepository


class ParcelRepository(BaseRepository[Parcel]):
    def __init__(self, db: AsyncSession):
        super().__init__(Parcel, db)

    async def get_by_parcel_number(self, number: str) -> Optional[Parcel]:
        result = await self.db.execute(select(Parcel).where(Parcel.parcel_number == number))
        return result.scalar_one_or_none()

    async def search_by_district(self, district: str, offset: int = 0, limit: int = 20) -> List[Parcel]:
        stmt = (
            select(Parcel)
            .where(Parcel.district.ilike(f"%{district}%"))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_within_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        limit: int = None,
    ) -> list:
        from app.core.config import settings
        effective_limit = min(limit or settings.MAX_PAGE_SIZE, settings.MAX_PAGE_SIZE)
        bbox_wkt = (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
            f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
        )
        stmt = (
            select(Parcel)
            .where(ST_Intersects(Parcel.geometry_2d, ST_GeomFromText(bbox_wkt, 4326)))
            .limit(effective_limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_within_radius(self, lon: float, lat: float, radius_m: float) -> List[Parcel]:
        from sqlalchemy import func
        from geoalchemy2.functions import ST_SetSRID, ST_Point
        center_geog = func.cast(ST_SetSRID(ST_Point(lon, lat), 4326), func.geography)
        parcel_geog = func.cast(Parcel.geometry_2d, func.geography)
        stmt = select(Parcel).where(
            Parcel.is_active == True,
            Parcel.geometry_2d.is_not(None),
            ST_DWithin(parcel_geog, center_geog, radius_m)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

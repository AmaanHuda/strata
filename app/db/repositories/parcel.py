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

    async def find_within_bbox(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> List[Parcel]:
        bbox_wkt = f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
        stmt = select(Parcel).where(
            ST_Intersects(Parcel.geometry_2d, ST_GeomFromText(bbox_wkt, 4326))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_within_radius(self, lon: float, lat: float, radius_m: float) -> List[Parcel]:
        point_wkt = f"POINT({lon} {lat})"
        stmt = select(Parcel).where(
            ST_DWithin(Parcel.geometry_2d, ST_GeomFromText(point_wkt, 4326), radius_m / 111320.0)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

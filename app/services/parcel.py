"""Parcel business logic."""
from geoalchemy2.elements import WKTElement
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.repositories.parcel import ParcelRepository
from app.db.models.property import Parcel
from app.schemas.property import ParcelCreate


class ParcelService:
    def __init__(self, db: AsyncSession):
        self.repo = ParcelRepository(db)

    async def create_parcel(self, data: ParcelCreate) -> Parcel:
        existing = await self.repo.get_by_parcel_number(data.parcel_number)
        if existing:
            raise ConflictError(f"Parcel {data.parcel_number} already exists")
        create_data = data.model_dump(exclude_none=True, by_alias=False)
        create_data.pop("geometry_wkt", None)  # handled separately
        # Populate the real PostGIS geometry column from the supplied WKT.
        # Without this, geometry_2d stays NULL forever and every spatial-search
        # endpoint silently returns nothing (invisible to mocked tests).
        boundary_wkt = create_data.get("boundary_wkt")
        if boundary_wkt and not create_data.get("geometry_2d"):
            create_data["geometry_2d"] = WKTElement(boundary_wkt, srid=4326)
        return await self.repo.create(create_data)

    async def get_parcel(self, parcel_id: UUID) -> Parcel:
        p = await self.repo.get(parcel_id)
        if not p:
            raise NotFoundError(f"Parcel {parcel_id} not found")
        return p

    async def list_parcels(self, district: Optional[str] = None, offset: int = 0, limit: int = 20) -> List[Parcel]:
        if district:
            return await self.repo.search_by_district(district, offset, limit)
        return await self.repo.list(offset=offset, limit=limit)

    async def spatial_search_bbox(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> List[Parcel]:
        return await self.repo.find_within_bbox(min_lon, min_lat, max_lon, max_lat)

    async def spatial_search_radius(self, lon: float, lat: float, radius_m: float) -> List[Parcel]:
        return await self.repo.find_within_radius(lon, lat, radius_m)

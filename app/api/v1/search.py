"""Search endpoint for parcels, buildings, units, and ULPINs."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.api.v1.deps import get_current_user
from app.db.models.property import Building, Parcel, Unit
from app.db.models.ulpin import ULPINRecord
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.search import SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=ApiResponse[SearchResponse])
async def search_properties(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query_term = f"%{q.strip()}%"
    results: List[SearchResultItem] = []

    # 1. Search Parcels
    p_stmt = select(Parcel).where(
        or_(
            Parcel.parcel_number.ilike(query_term),
            Parcel.district.ilike(query_term),
            Parcel.candidate_ulpin.ilike(query_term),
            Parcel.official_ulpin.ilike(query_term),
        )
    ).limit(limit)
    p_res = await db.execute(p_stmt)
    for p in p_res.scalars().all():
        results.append(
            SearchResultItem(
                entity_type="parcel",
                entity_id=p.id,
                identifier=p.parcel_number,
                official_ulpin=p.official_ulpin,
                candidate_ulpin=p.candidate_ulpin,
                status=p.status,
                location_summary=f"District: {p.district}, State: {p.state}",
                score=1.0,
            )
        )

    # 2. Search Buildings
    b_stmt = select(Building).where(
        or_(
            Building.building_name.ilike(query_term),
            Building.candidate_ulpin.ilike(query_term),
            Building.official_ulpin.ilike(query_term),
        )
    ).limit(limit)
    b_res = await db.execute(b_stmt)
    for b in b_res.scalars().all():
        results.append(
            SearchResultItem(
                entity_type="building",
                entity_id=b.id,
                identifier=b.building_name or str(b.id),
                official_ulpin=b.official_ulpin,
                candidate_ulpin=b.candidate_ulpin,
                status=b.status,
                location_summary=f"Type: {b.building_type}, Floors: {b.floor_count}",
                score=0.9,
            )
        )

    # 3. Search Units
    u_stmt = select(Unit).where(
        or_(
            Unit.unit_number.ilike(query_term),
            Unit.candidate_ulpin.ilike(query_term),
            Unit.official_ulpin.ilike(query_term),
        )
    ).limit(limit)
    u_res = await db.execute(u_stmt)
    for u in u_res.scalars().all():
        results.append(
            SearchResultItem(
                entity_type="unit",
                entity_id=u.id,
                identifier=f"Unit {u.unit_number}",
                official_ulpin=u.official_ulpin,
                candidate_ulpin=u.candidate_ulpin,
                status=u.status,
                location_summary=f"Type: {u.unit_type}, Area: {u.area_sqm} sqm",
                score=0.8,
            )
        )

    return ApiResponse(
        data=SearchResponse(
            query=q,
            total_results=len(results),
            results=results[:limit],
        )
    )

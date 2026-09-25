"""
On-demand ingestion endpoint: turn any Indian coordinate into real records.

``POST /api/v1/ingest/location`` fetches real OpenStreetMap footprints (Overpass
API), optionally runs the ML engine, and persists Parcel -> Building -> Floor
[-> Unit] rows with CANDIDATE ULPINs. No official ULPIN is ever issued here.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import MLEngineNotAvailableError, ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.integrations.osm.overpass import OverpassError
from app.schemas.common import ApiResponse
from app.schemas.ingest import IngestLocationRequest, IngestLocationResponse
from app.services.on_demand_ingest import OnDemandIngestService

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post(
    "/location",
    response_model=ApiResponse[IngestLocationResponse],
    summary="Ingest real OSM building/parcel records for a coordinate in India",
)
async def ingest_location(
    req: IngestLocationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    """
    Fetch real building footprints near ``lat``/``lon`` from OpenStreetMap and
    persist them as CANDIDATE cadastral records.

    Example — the Taj Mahal Palace Hotel, Apollo Bandar, Mumbai:
        {"lat": 18.92170, "lon": 72.83320, "radius_m": 60,
         "name_contains": "Taj Mahal Palace", "state": "Maharashtra",
         "district": "Mumbai", "max_buildings": 1}
    """
    service = OnDemandIngestService(db)
    try:
        result = await service.ingest_location(req, user)
    except OverpassError as exc:
        raise ValidationError(
            f"OpenStreetMap source data could not be retrieved: {exc}. "
            "No records were created."
        )
    except MLEngineNotAvailableError as exc:
        raise ValidationError(
            f"ML engine rejected the request: {exc}. No records were created."
        )
    return ApiResponse(
        data=result,
        meta={
            "message": "On-demand ingestion complete",
            "authoritative": False,
            "source": "OpenStreetMap (ODbL 1.0) via Overpass API",
        },
    )


@router.get(
    "/coverage",
    summary="Row counts proving what real data is currently stored",
)
async def ingestion_coverage(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Counts of the persisted hierarchy, so coverage is observable, not assumed."""
    async def _count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return int((await db.execute(stmt)).scalar() or 0)

    osm_buildings = await _count(
        Building, Building.metadata_["osm_reference"].astext.is_not(None)
    )
    return ApiResponse(
        data={
            "parcels": await _count(Parcel),
            "buildings": await _count(Building),
            "buildings_with_geometry": await _count(
                Building, Building.footprint_2d.is_not(None)
            ),
            "buildings_with_candidate_ulpin": await _count(
                Building, Building.candidate_ulpin.is_not(None)
            ),
            "buildings_from_osm_ingest": osm_buildings,
            "floors": await _count(Floor),
            "units": await _count(Unit),
        },
        meta={"note": "official_ulpin is never set by ingestion; see /ulpin endpoints."},
    )

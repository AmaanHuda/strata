"""Cadastral topology and 3D geometry validation endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.validation import PropertyValidationReport
from app.services.topology_validation import TopologyValidationService

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/{property_id}", response_model=ApiResponse[PropertyValidationReport])
async def get_validation_report(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # Determine entity type
    building = await db.get(Building, property_id)
    if building:
        parcel = await db.get(Parcel, building.parcel_id)
        floors_res = await db.execute(select(Floor).where(Floor.building_id == building.id))
        floors = floors_res.scalars().all()
        floors_data = [{"floor_number": f.floor_number, "ceiling_height_m": f.ceiling_height_m} for f in floors]
        
        report = TopologyValidationService.run_full_validation(
            property_id=property_id,
            entity_type="building",
            parcel_wkt=parcel.boundary_wkt if parcel else None,
            building_wkt=building.footprint_wkt,
            floors_data=floors_data,
        )
        return ApiResponse(data=report)

    parcel = await db.get(Parcel, property_id)
    if parcel:
        report = TopologyValidationService.run_full_validation(
            property_id=property_id,
            entity_type="parcel",
            parcel_wkt=parcel.boundary_wkt,
        )
        return ApiResponse(data=report)

    raise NotFoundError(f"Property entity {property_id} not found")


@router.post("/run/{property_id}", response_model=ApiResponse[PropertyValidationReport])
async def run_property_validation(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    return await get_validation_report(property_id=property_id, db=db, _user=user)

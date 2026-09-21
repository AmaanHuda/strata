"""
Spatial query endpoints for STRATA 3D cadastral mapping.
Supports Viewport BBox, Radius/Nearby (meters), Polygon Query, and Point Lookup.
Uses PostGIS spatial indexing (GiST) and avoids calculating metric distances in EPSG:4326 degrees.
"""
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from geoalchemy2.functions import (
    ST_AsGeoJSON,
    ST_Centroid,
    ST_Contains,
    ST_Distance,
    ST_DWithin,
    ST_GeomFromText,
    ST_Intersects,
    ST_MakeEnvelope,
    ST_Point,
    ST_SetSRID,
    ST_SimplifyPreserveTopology,
    ST_Within,
)
from shapely import wkt as shapely_wkt
from shapely.geometry import shape
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.errors import ValidationError
from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.search import (
    PointLookupResponse,
    SpatialBBoxResponse,
    SpatialEntityItem,
    SpatialNearbyResponse,
    SpatialQueryRequest,
)

router = APIRouter(prefix="/spatial", tags=["spatial"])


def _extract_centroid_coords(centroid_geojson_str: Optional[str]) -> Optional[Dict[str, float]]:
    if not centroid_geojson_str:
        return None
    try:
        data = json.loads(centroid_geojson_str)
        coords = data.get("coordinates", [])
        if len(coords) >= 2:
            return {"lon": float(coords[0]), "lat": float(coords[1])}
    except Exception:
        pass
    return None


@router.get("/bbox", response_model=ApiResponse[SpatialBBoxResponse])
async def query_bbox(
    min_lon: float = Query(..., ge=-180, le=180, description="Minimum longitude"),
    min_lat: float = Query(..., ge=-90, le=90, description="Minimum latitude"),
    max_lon: float = Query(..., ge=-180, le=180, description="Maximum longitude"),
    max_lat: float = Query(..., ge=-90, le=90, description="Maximum latitude"),
    layer: str = Query("all", description="Layer filter: 'parcel', 'building', or 'all'"),
    simplify_tolerance: Optional[float] = Query(None, ge=0.0, description="ST_Simplify tolerance in degrees"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Viewport bounding box query for map display.
    Only loads data required for current viewport using PostGIS GiST index.
    """
    if min_lon > max_lon or min_lat > max_lat:
        raise ValidationError("Invalid bounding box: min coordinates must be <= max coordinates")

    envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    results: List[SpatialEntityItem] = []

    # 1. Parcels layer
    if layer in ["parcel", "all"]:
        geom_col = (
            ST_SimplifyPreserveTopology(Parcel.geometry_2d, simplify_tolerance)
            if simplify_tolerance
            else Parcel.geometry_2d
        )
        stmt = (
            select(
                Parcel.id,
                Parcel.parcel_number,
                Parcel.official_ulpin,
                Parcel.candidate_ulpin,
                Parcel.status,
                Parcel.area_sqm,
                ST_AsGeoJSON(geom_col).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Parcel.geometry_2d)).label("centroid_geojson"),
            )
            .where(
                Parcel.is_active == True,
                Parcel.geometry_2d.is_not(None),
                ST_Intersects(Parcel.geometry_2d, envelope),
            )
            .limit(limit)
            .offset(offset)
        )
        p_res = await db.execute(stmt)
        for row in p_res.all():
            p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=p_id,
                    entity_type="parcel",
                    identifier=p_num,
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                )
            )

    # 2. Buildings layer
    if layer in ["building", "all"] and len(results) < limit:
        remaining = limit - len(results)
        geom_col = (
            ST_SimplifyPreserveTopology(Building.footprint_2d, simplify_tolerance)
            if simplify_tolerance
            else Building.footprint_2d
        )
        stmt = (
            select(
                Building.id,
                Building.building_name,
                Building.official_ulpin,
                Building.candidate_ulpin,
                Building.status,
                Building.height_m,
                Building.floor_count,
                Building.footprint_area_sqm,
                ST_AsGeoJSON(geom_col).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
            )
            .where(
                Building.is_active == True,
                Building.footprint_2d.is_not(None),
                ST_Intersects(Building.footprint_2d, envelope),
            )
            .limit(remaining)
            .offset(offset)
        )
        b_res = await db.execute(stmt)
        for row in b_res.all():
            b_id, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=b_id,
                    entity_type="building",
                    identifier=b_name or f"Building-{str(b_id)[:8]}",
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    height_m=height,
                    floor_count=floors,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                )
            )

    return ApiResponse(
        data=SpatialBBoxResponse(
            bbox=[min_lon, min_lat, max_lon, max_lat],
            layer=layer,
            crs="EPSG:4326",
            count=len(results),
            results=results,
        )
    )


@router.get("/nearby", response_model=ApiResponse[SpatialNearbyResponse])
async def query_nearby(
    lat: float = Query(..., ge=-90, le=90, description="Center latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Center longitude"),
    radius_m: float = Query(500.0, ge=1.0, le=50000.0, description="Search radius in meters"),
    layer: str = Query("all", description="Layer filter: 'parcel', 'building', or 'all'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Radius / proximity search around coordinate in METERS.
    Uses PostGIS geography type for geodesic distance calculation without flat degree distortion.
    """
    center_pt = ST_SetSRID(ST_Point(lon, lat), 4326)
    center_geog = func.cast(center_pt, func.geography)
    results: List[SpatialEntityItem] = []

    # Parcels nearby
    if layer in ["parcel", "all"]:
        parcel_geog = func.cast(Parcel.geometry_2d, func.geography)
        dist_expr = ST_Distance(parcel_geog, center_geog)
        stmt = (
            select(
                Parcel.id,
                Parcel.parcel_number,
                Parcel.official_ulpin,
                Parcel.candidate_ulpin,
                Parcel.status,
                Parcel.area_sqm,
                ST_AsGeoJSON(Parcel.geometry_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Parcel.geometry_2d)).label("centroid_geojson"),
                dist_expr.label("distance_m"),
            )
            .where(
                Parcel.is_active == True,
                Parcel.geometry_2d.is_not(None),
                ST_DWithin(parcel_geog, center_geog, radius_m),
            )
            .order_by(dist_expr)
            .limit(limit)
        )
        p_res = await db.execute(stmt)
        for row in p_res.all():
            p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str, dist = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=p_id,
                    entity_type="parcel",
                    identifier=p_num,
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                    distance_m=round(float(dist), 2) if dist is not None else None,
                )
            )

    # Buildings nearby
    if layer in ["building", "all"] and len(results) < limit:
        remaining = limit - len(results)
        bld_geog = func.cast(Building.footprint_2d, func.geography)
        dist_expr = ST_Distance(bld_geog, center_geog)
        stmt = (
            select(
                Building.id,
                Building.building_name,
                Building.official_ulpin,
                Building.candidate_ulpin,
                Building.status,
                Building.height_m,
                Building.floor_count,
                Building.footprint_area_sqm,
                ST_AsGeoJSON(Building.footprint_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
                dist_expr.label("distance_m"),
            )
            .where(
                Building.is_active == True,
                Building.footprint_2d.is_not(None),
                ST_DWithin(bld_geog, center_geog, radius_m),
            )
            .order_by(dist_expr)
            .limit(remaining)
        )
        b_res = await db.execute(stmt)
        for row in b_res.all():
            b_id, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str, dist = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=b_id,
                    entity_type="building",
                    identifier=b_name or f"Building-{str(b_id)[:8]}",
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    height_m=height,
                    floor_count=floors,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                    distance_m=round(float(dist), 2) if dist is not None else None,
                )
            )

    results.sort(key=lambda x: x.distance_m if x.distance_m is not None else float("inf"))
    return ApiResponse(
        data=SpatialNearbyResponse(
            center_lat=lat,
            center_lon=lon,
            radius_m=radius_m,
            crs="EPSG:4326",
            count=len(results),
            results=results[:limit],
        )
    )


@router.post("/query", response_model=ApiResponse[List[SpatialEntityItem]])
async def query_spatial_polygon(
    req: SpatialQueryRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Arbitrary polygon spatial query (contains, within, intersects).
    Accepts WKT or GeoJSON geometry.
    """
    poly_wkt = req.polygon_wkt
    if not poly_wkt and req.polygon_geojson:
        try:
            poly_geom = shape(req.polygon_geojson)
            poly_wkt = poly_geom.wkt
        except Exception as e:
            raise ValidationError(f"Invalid polygon GeoJSON: {str(e)}")

    if not poly_wkt:
        raise ValidationError("Either polygon_wkt or polygon_geojson must be provided")

    try:
        parsed_geom = shapely_wkt.loads(poly_wkt)
        if not parsed_geom.is_valid:
            raise ValidationError("Invalid input geometry for spatial query")
    except Exception as e:
        raise ValidationError(f"Malformed input polygon: {str(e)}")

    query_geom = ST_SetSRID(ST_GeomFromText(poly_wkt), 4326)
    results: List[SpatialEntityItem] = []

    # Choose spatial relation function
    relation_fn = ST_Intersects
    if req.relation.lower() == "contains":
        relation_fn = ST_Contains
    elif req.relation.lower() == "within":
        relation_fn = ST_Within

    if req.layer in ["parcel", "all"]:
        stmt = (
            select(
                Parcel.id,
                Parcel.parcel_number,
                Parcel.official_ulpin,
                Parcel.candidate_ulpin,
                Parcel.status,
                Parcel.area_sqm,
                ST_AsGeoJSON(Parcel.geometry_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Parcel.geometry_2d)).label("centroid_geojson"),
            )
            .where(
                Parcel.is_active == True,
                Parcel.geometry_2d.is_not(None),
                relation_fn(query_geom, Parcel.geometry_2d)
                if req.relation.lower() == "contains"
                else relation_fn(Parcel.geometry_2d, query_geom),
            )
            .limit(req.limit)
        )
        p_res = await db.execute(stmt)
        for row in p_res.all():
            p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=p_id,
                    entity_type="parcel",
                    identifier=p_num,
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                )
            )

    if req.layer in ["building", "all"] and len(results) < req.limit:
        rem = req.limit - len(results)
        stmt = (
            select(
                Building.id,
                Building.building_name,
                Building.official_ulpin,
                Building.candidate_ulpin,
                Building.status,
                Building.height_m,
                Building.floor_count,
                Building.footprint_area_sqm,
                ST_AsGeoJSON(Building.footprint_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
            )
            .where(
                Building.is_active == True,
                Building.footprint_2d.is_not(None),
                relation_fn(query_geom, Building.footprint_2d)
                if req.relation.lower() == "contains"
                else relation_fn(Building.footprint_2d, query_geom),
            )
            .limit(rem)
        )
        b_res = await db.execute(stmt)
        for row in b_res.all():
            b_id, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str = row
            geom_dict = json.loads(geo_str) if geo_str else None
            results.append(
                SpatialEntityItem(
                    id=b_id,
                    entity_type="building",
                    identifier=b_name or f"Building-{str(b_id)[:8]}",
                    official_ulpin=off_u,
                    candidate_ulpin=cand_u,
                    status=status_,
                    area_sqm=float(area) if area else None,
                    height_m=height,
                    floor_count=floors,
                    geometry_geojson=geom_dict,
                    centroid=_extract_centroid_coords(cent_str),
                )
            )

    return ApiResponse(data=results, meta={"count": len(results)})


@router.get("/search", response_model=ApiResponse[PointLookupResponse])
async def point_lookup(
    lat: float = Query(..., ge=-90, le=90, description="Latitude coordinate"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude coordinate"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Point lookup: Returns the containing land parcel, building, and vertical unit counts.
    """
    point = ST_SetSRID(ST_Point(lon, lat), 4326)

    # 1. Containing Parcel
    p_stmt = (
        select(
            Parcel.id,
            Parcel.parcel_number,
            Parcel.official_ulpin,
            Parcel.candidate_ulpin,
            Parcel.status,
            Parcel.area_sqm,
            ST_AsGeoJSON(Parcel.geometry_2d).label("geojson"),
            ST_AsGeoJSON(ST_Centroid(Parcel.geometry_2d)).label("centroid_geojson"),
        )
        .where(
            Parcel.is_active == True,
            Parcel.geometry_2d.is_not(None),
            ST_Contains(Parcel.geometry_2d, point),
        )
        .limit(1)
    )
    p_res = await db.execute(p_stmt)
    p_row = p_res.first()
    parcel_item = None
    if p_row:
        p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str = p_row
        parcel_item = SpatialEntityItem(
            id=p_id,
            entity_type="parcel",
            identifier=p_num,
            official_ulpin=off_u,
            candidate_ulpin=cand_u,
            status=status_,
            area_sqm=float(area) if area else None,
            geometry_geojson=json.loads(geo_str) if geo_str else None,
            centroid=_extract_centroid_coords(cent_str),
        )

    # 2. Containing Building
    b_stmt = (
        select(
            Building.id,
            Building.building_name,
            Building.official_ulpin,
            Building.candidate_ulpin,
            Building.status,
            Building.height_m,
            Building.floor_count,
            Building.footprint_area_sqm,
            ST_AsGeoJSON(Building.footprint_2d).label("geojson"),
            ST_AsGeoJSON(ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
        )
        .where(
            Building.is_active == True,
            Building.footprint_2d.is_not(None),
            ST_Contains(Building.footprint_2d, point),
        )
        .limit(1)
    )
    b_res = await db.execute(b_stmt)
    b_row = b_res.first()
    building_item = None
    floors_count = 0
    units_count = 0

    if b_row:
        b_id, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str = b_row
        building_item = SpatialEntityItem(
            id=b_id,
            entity_type="building",
            identifier=b_name or f"Building-{str(b_id)[:8]}",
            official_ulpin=off_u,
            candidate_ulpin=cand_u,
            status=status_,
            area_sqm=float(area) if area else None,
            height_m=height,
            floor_count=floors,
            geometry_geojson=json.loads(geo_str) if geo_str else None,
            centroid=_extract_centroid_coords(cent_str),
        )

        # Count floors and units
        fl_res = await db.execute(select(func.count(Floor.id)).where(Floor.building_id == b_id, Floor.is_active == True))
        floors_count = fl_res.scalar() or 0

        un_res = await db.execute(
            select(func.count(Unit.id))
            .join(Floor, Floor.id == Unit.floor_id)
            .where(Floor.building_id == b_id, Unit.is_active == True)
        )
        units_count = un_res.scalar() or 0

    return ApiResponse(
        data=PointLookupResponse(
            lat=lat,
            lon=lon,
            parcel=parcel_item,
            building=building_item,
            floors_count=floors_count,
            units_count=units_count,
        )
    )

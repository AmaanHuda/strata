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
    ST_XMax,
    ST_XMin,
    ST_YMax,
    ST_YMin,
)
from geoalchemy2 import Geography
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
    SpatialExtentResponse,
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


@router.get("/extent", response_model=ApiResponse[SpatialExtentResponse])
async def data_extent(
    layer: str = Query("building", description="Layer filter: 'parcel', 'building', or 'all'"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Union bounding box + counts of the geometry actually stored in PostGIS.

    Lets clients open the map on the data that really exists, instead of a
    hard-coded city centre that may be hundreds of kilometres away from it.
    """
    bbox: Optional[List[float]] = None
    building_count = 0
    parcel_count = 0

    if layer in ["building", "all"]:
        b_row = (
            await db.execute(
                select(
                    func.count(Building.id),
                    func.min(ST_XMin(Building.footprint_2d)),
                    func.min(ST_YMin(Building.footprint_2d)),
                    func.max(ST_XMax(Building.footprint_2d)),
                    func.max(ST_YMax(Building.footprint_2d)),
                ).where(
                    Building.is_active == True,
                    Building.footprint_2d.is_not(None),
                )
            )
        ).first()
        building_count = int(b_row[0] or 0) if b_row else 0
        if b_row and b_row[1] is not None:
            bbox = [float(b_row[1]), float(b_row[2]), float(b_row[3]), float(b_row[4])]

    if layer in ["parcel", "all"]:
        p_count_res = await db.execute(
            select(func.count(Parcel.id)).where(
                Parcel.is_active == True,
                Parcel.geometry_2d.is_not(None),
            )
        )
        parcel_count = int(p_count_res.scalar() or 0)

    return ApiResponse(
        data=SpatialExtentResponse(
            bbox=bbox,
            has_data=bbox is not None,
            building_count=building_count,
            parcel_count=parcel_count,
            center_lon=((bbox[0] + bbox[2]) / 2) if bbox else None,
            center_lat=((bbox[1] + bbox[3]) / 2) if bbox else None,
        )
    )


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
    center_geog = cast(center_pt, Geography)
    results: List[SpatialEntityItem] = []

    # Parcels nearby
    if layer in ["parcel", "all"]:
        parcel_geog = cast(Parcel.geometry_2d, Geography)
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
        bld_geog = cast(Building.footprint_2d, Geography)
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
    radius_m: float = Query(
        50.0,
        ge=1.0,
        le=5000.0,
        description="Proximity tolerance in meters when the click is not inside a footprint",
    ),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Point lookup: Returns the containing or nearest land parcel, building, and vertical unit counts.
    Uses PostGIS spatial index with ST_Intersects and geodesic distance tolerance to account for 3D map click projection.

    Each returned entity is annotated with match_type: "inside" when the point falls
    within the footprint, or "nearest" when it is the closest record within radius_m.
    """
    point = ST_SetSRID(ST_Point(lon, lat), 4326)
    point_geog = cast(point, Geography)

    # 1. Building Lookup (Direct intersection first, then within tolerance)
    b_stmt = (
        select(
            Building.id,
            Building.parcel_id,
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
            ST_Intersects(Building.footprint_2d, point),
        )
        .limit(1)
    )
    b_res = await db.execute(b_stmt)
    b_row = b_res.first()

    matched_parcel_id = None
    building_item = None
    floors_count = 0
    units_count = 0

    if b_row:
        b_id, b_pid, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str = b_row
        matched_parcel_id = b_pid
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
    else:
        # Check within 20m tolerance for 3D perspective / offset clicks
        bld_geog = cast(Building.footprint_2d, Geography)
        dist_expr = ST_Distance(bld_geog, point_geog)
        b_near_stmt = (
            select(
                Building.id,
                Building.parcel_id,
                Building.building_name,
                Building.official_ulpin,
                Building.candidate_ulpin,
                Building.status,
                Building.height_m,
                Building.floor_count,
                Building.footprint_area_sqm,
                ST_AsGeoJSON(Building.footprint_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Building.footprint_2d)).label("centroid_geojson"),
                dist_expr.label("dist"),
            )
            .where(
                Building.is_active == True,
                Building.footprint_2d.is_not(None),
                ST_DWithin(bld_geog, point_geog, radius_m),
            )
            .order_by(dist_expr)
            .limit(1)
        )
        b_near_res = await db.execute(b_near_stmt)
        b_near_row = b_near_res.first()
        if b_near_row:
            b_id, b_pid, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str, _ = b_near_row
            matched_parcel_id = b_pid
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

    # 2. Containing / Associated Parcel
    parcel_item = None
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
            ST_Intersects(Parcel.geometry_2d, point),
        )
        .limit(1)
    )
    p_res = await db.execute(p_stmt)
    p_row = p_res.first()

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
    elif matched_parcel_id:
        # If building was found, look up parent parcel
        p_by_id_stmt = (
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
                Parcel.id == matched_parcel_id,
                Parcel.is_active == True,
            )
            .limit(1)
        )
        p_by_id_res = await db.execute(p_by_id_stmt)
        p_by_id_row = p_by_id_res.first()
        if p_by_id_row:
            p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str = p_by_id_row
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
    else:
        # Check within 20m tolerance
        pcl_geog = cast(Parcel.geometry_2d, Geography)
        p_dist_expr = ST_Distance(pcl_geog, point_geog)
        p_near_stmt = (
            select(
                Parcel.id,
                Parcel.parcel_number,
                Parcel.official_ulpin,
                Parcel.candidate_ulpin,
                Parcel.status,
                Parcel.area_sqm,
                ST_AsGeoJSON(Parcel.geometry_2d).label("geojson"),
                ST_AsGeoJSON(ST_Centroid(Parcel.geometry_2d)).label("centroid_geojson"),
                p_dist_expr.label("dist"),
            )
            .where(
                Parcel.is_active == True,
                Parcel.geometry_2d.is_not(None),
                ST_DWithin(pcl_geog, point_geog, radius_m),
            )
            .order_by(p_dist_expr)
            .limit(1)
        )
        p_near_res = await db.execute(p_near_stmt)
        p_near_row = p_near_res.first()
        if p_near_row:
            p_id, p_num, off_u, cand_u, status_, area, geo_str, cent_str, _ = p_near_row
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

    # 3. If parcel was found but no building yet, check for buildings located on this parcel
    if parcel_item and not building_item:
        b_on_p_stmt = (
            select(
                Building.id,
                Building.parcel_id,
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
                Building.parcel_id == parcel_item.id,
                Building.is_active == True,
            )
            .limit(1)
        )
        b_on_p_res = await db.execute(b_on_p_stmt)
        b_on_p_row = b_on_p_res.first()
        if b_on_p_row:
            b_id, b_pid, b_name, off_u, cand_u, status_, height, floors, area, geo_str, cent_str = b_on_p_row
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

    # 4. Vertical Unit and Floor Counts
    if building_item:
        b_id = building_item.id
        fl_res = await db.execute(select(func.count(Floor.id)).where(Floor.building_id == b_id, Floor.is_active == True))
        fl_count = fl_res.scalar() or 0

        un_res = await db.execute(
            select(func.count(Unit.id))
            .join(Floor, Floor.id == Unit.floor_id)
            .where(Floor.building_id == b_id, Unit.is_active == True)
        )
        units_count = un_res.scalar() or 0
        floors_count = fl_count or (building_item.floor_count or 0)

    # 5. Annotate how each record was matched, so the UI never claims a pure
    #    proximity hit was a containment hit (geodesic distance, in metres).
    if building_item is not None:
        b_dist_res = await db.execute(
            select(ST_Distance(cast(Building.footprint_2d, Geography), point_geog)).where(
                Building.id == building_item.id
            )
        )
        b_dist = b_dist_res.scalar()
        if b_dist is not None:
            b_dist = float(b_dist)
            building_item.distance_m = round(b_dist, 2)
            building_item.match_type = "inside" if b_dist <= 1e-6 else "nearest"

    if parcel_item is not None:
        p_dist_res = await db.execute(
            select(ST_Distance(cast(Parcel.geometry_2d, Geography), point_geog)).where(
                Parcel.id == parcel_item.id
            )
        )
        p_dist = p_dist_res.scalar()
        if p_dist is not None:
            p_dist = float(p_dist)
            parcel_item.distance_m = round(p_dist, 2)
            parcel_item.match_type = "inside" if p_dist <= 1e-6 else "nearest"

    return ApiResponse(
        data=PointLookupResponse(
            lat=lat,
            lon=lon,
            parcel=parcel_item,
            building=building_item,
            floors_count=floors_count,
            units_count=units_count,
            search_radius_m=radius_m,
        )
    )

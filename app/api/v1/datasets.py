"""Spatial dataset registry + dataset ingestion endpoints."""
import hashlib
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import ValidationError
from app.db.models.property import Building, Parcel
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.dataset import (
    BuildingImportError,
    BuildingImportResult,
    DatasetOut,
    DatasetRegisterRequest,
    ImportStatusOut,
)
from app.services.cadastral_codes import assign_cadastral_codes
from app.services.dataset import DatasetService
from app.services.ulpin import ULPINService

router = APIRouter(prefix="/datasets", tags=["datasets"])


# Candidate ULPINs produced by ingestion are analytical outputs, never legal title.
_ULPIN_DISCLAIMER = (
    "Candidate ULPINs produced by the dataset import pipeline are NON-AUTHORITATIVE "
    "analytical identifiers. They do not constitute legal title and become cadastral "
    "records only once verified and gazetted by a competent government authority."
)


def _normalise_features(payload: Any) -> List[Dict[str, Any]]:
    """Accepts a FeatureCollection, a single Feature, a bare geometry, or a list of Features."""
    if isinstance(payload, dict):
        gtype = payload.get("type")
        if gtype == "FeatureCollection":
            features = payload.get("features") or []
            if not isinstance(features, list):
                raise ValidationError("FeatureCollection.features must be a list")
            return features
        if gtype == "Feature":
            return [payload]
        if gtype in {"Polygon", "MultiPolygon"}:
            return [{"type": "Feature", "geometry": payload, "properties": {}}]
        raise ValidationError(
            "Unsupported GeoJSON object. Expected FeatureCollection, Feature, Polygon or MultiPolygon."
        )
    if isinstance(payload, list):
        return payload
    raise ValidationError("Unsupported GeoJSON document root type.")


def _largest_polygon(geometry: Dict[str, Any]):
    """Coerce a GeoJSON geometry into one valid shapely Polygon (largest part of a MultiPolygon)."""
    from shapely.geometry import MultiPolygon, Polygon, shape as shapely_shape

    try:
        geom = shapely_shape(geometry)
    except Exception as exc:  # malformed coordinates
        raise ValueError(f"cannot parse geometry ({exc})")

    if geom.is_empty:
        raise ValueError("empty geometry")

    if not geom.is_valid:
        # buffer(0) is the standard repair for self-intersecting rings
        geom = geom.buffer(0)

    if isinstance(geom, MultiPolygon):
        if not geom.geoms:
            raise ValueError("empty multipolygon")
        geom = max(geom.geoms, key=lambda g: g.area)

    if not isinstance(geom, Polygon):
        raise ValueError(f"unsupported geometry type '{geom.geom_type}'")
    if geom.is_empty or geom.area <= 0:
        raise ValueError("degenerate polygon (zero area)")
    return geom


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


@router.post(
    "/import-buildings-geojson",
    response_model=ApiResponse[BuildingImportResult],
    status_code=status.HTTP_201_CREATED,
)
async def import_buildings_geojson(
    file: UploadFile = File(
        ...,
        description="GeoJSON of building footprints: FeatureCollection, Feature, or bare Polygon/MultiPolygon",
    ),
    district: str = Query("Mumbai", description="Cadastral district used for generated parcels"),
    state: str = Query("Maharashtra", description="State used for generated parcels and ULPINs"),
    taluk: str = Query("Andheri", description="Taluk/sub-district for generated parcels"),
    village: str = Query("Village", description="Default village name when a feature has none"),
    building_type: str = Query("residential", description="Default building type"),
    model_version: str = Query("geojson-import-v1", description="Provenance tag stored on every building"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    """
    Bulk-load building footprints from a GeoJSON file into PostGIS.

    For every valid feature this endpoint:
      * creates (or reuses) the parent Parcel,
      * creates a CANDIDATE Building with real footprint geometry,
      * computes the geodesic footprint area and confirms the geometry is tileable
        via PostGIS (ST_GeomFromText -> geometry_2d / footprint_2d),
      * generates a non-authoritative candidate ULPIN and registers it.

    Idempotent: re-uploading the same feature is skipped via a stored import hash,
    so it is safe to run repeatedly without creating duplicates.
    """
    raw = await file.read()
    if not raw:
        raise ValidationError("Uploaded file is empty")

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValidationError(f"File is not valid UTF-8 text: {exc}")
    except json.JSONDecodeError as exc:
        raise ValidationError(f"File is not valid JSON: {exc}")

    features = _normalise_features(payload)

    errors: List[BuildingImportError] = []
    imported_ids: List[UUID] = []
    parcels_created = 0
    parcels_reused = 0
    ulpins_generated = 0
    skipped = 0

    # Only used to build a human-readable default parcel number below. It is
    # NOT used for ULPIN segments any more — the natural key `PARCEL-<xx>-nnnnn`
    # must stay stable or re-importing would create duplicate parcels. ULPIN code
    # segments come from assign_cadastral_codes() instead.
    district_code = (district or "00")[:2].upper().ljust(2, "0")

    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(BuildingImportError(index=idx, reason="feature is not an object"))
            skipped += 1
            continue

        geometry = feature.get("geometry")
        props = feature.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        if not geometry:
            errors.append(BuildingImportError(index=idx, reason="feature has no geometry"))
            skipped += 1
            continue

        try:
            polygon = _largest_polygon(geometry)
        except ValueError as exc:
            errors.append(BuildingImportError(index=idx, reason=str(exc)))
            skipped += 1
            continue

        wkt = polygon.wkt
        import_hash = hashlib.sha256(f"{wkt}|{model_version}".encode()).hexdigest()[:32]

        # Idempotency: skip features already ingested by this pipeline.
        existing = await db.execute(
            select(Building.id)
            .where(Building.metadata_["import_hash"].astext == import_hash)
            .limit(1)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Honesty guard: a plain GeoJSON file is source data, not a model output.
        # Mark provenance as ML-derived only when the feature itself declares it,
        # otherwise the UI would claim a model estimated values that simply came
        # from the uploaded file's own attributes.
        declared_model = props.get("model_version") or props.get("ml_model_version")
        declared_ml = props.get("ml_derived")
        if declared_ml is None:
            is_ml_derived = bool(declared_model)
        elif isinstance(declared_ml, str):
            is_ml_derived = declared_ml.strip().lower() in {"true", "1", "yes"}
        else:
            is_ml_derived = bool(declared_ml)
        ml_model_version = str(declared_model) if (is_ml_derived and declared_model) else None

        village_name = str(props.get("village") or village)
        parcel_number = str(
            props.get("parcel_number") or f"PARCEL-{district_code}-{idx + 1:05d}"
        )

        parcel_res = await db.execute(
            select(Parcel).where(
                Parcel.parcel_number == parcel_number, Parcel.is_active == True  # noqa: E712
            )
        )
        parcel = parcel_res.scalar_one_or_none()
        if parcel:
            parcels_reused += 1
        else:
            parcel = Parcel(
                parcel_number=parcel_number,
                survey_number=props.get("survey_number"),
                district=district,
                taluk=taluk,
                village=village_name,
                state=state,
                land_use=props.get("land_use"),
                status="CANDIDATE",
                boundary_wkt=wkt,
                metadata_={"import_hash": import_hash, "source": file.filename},
            )
            db.add(parcel)
            await db.flush()
            parcels_created += 1

        building = Building(
            parcel_id=parcel.id,
            building_name=props.get("name") or props.get("building_name"),
            building_type=props.get("building_type") or building_type,
            floor_count=_as_int(props.get("floor_count", props.get("floors"))),
            height_m=_as_float(props.get("height_m", props.get("height"))),
            footprint_wkt=wkt,
            source_crs="EPSG:4326",
            processing_crs="EPSG:3857",
            status="CANDIDATE",
            ml_derived=is_ml_derived,
            ml_model_version=ml_model_version,
            ml_confidence_score=(
                _as_float(props.get("confidence"))
                if is_ml_derived
                else None
            ),
            metadata_={
                "import_hash": import_hash,
                "source": file.filename,
                "raw_properties": props,
            },
        )
        db.add(building)
        await db.flush()

        # Materialise the PostGIS geometry and the true (geodesic) area in one shot.
        await db.execute(
            text(
                "UPDATE buildings "
                "SET footprint_2d = ST_GeomFromText(:wkt, 4326), "
                "    footprint_area_sqm = ST_Area(ST_GeomFromText(:wkt, 4326)::geography) "
                "WHERE id = :bid"
            ),
            {"wkt": wkt, "bid": building.id},
        )
        await db.execute(
            text(
                "UPDATE parcels SET geometry_2d = ST_Multi(ST_GeomFromText(:wkt, 4326)) "
                "WHERE id = :pid"
            ),
            {"wkt": wkt, "pid": parcel.id},
        )

        # Candidate (NON-AUTHORITATIVE) identifiers so the sidebar has ULPINs to show.
        #
        # The code segments go through the shared assigner rather than raw string
        # slicing: slicing produced identifiers such as `MA-MU-AND-KURLA0-P-...`
        # (letters where the candidate format requires digits), which
        # /api/v1/ulpin/validate then classified as syntactically INVALID. Existing
        # rows are left untouched; this corrects every new import.
        codes = assign_cadastral_codes(
            state=state,
            district=district,
            taluk=taluk,
            village=village_name,
        )
        parcel.candidate_ulpin = ULPINService.generate_parcel_ulpin(
            state=codes.state_code,
            district=codes.district_code,
            taluk=codes.taluk_code,
            village=codes.village_code,
            survey_number=parcel_number,
        )
        if isinstance(parcel.metadata_, dict):
            parcel.metadata_ = {**parcel.metadata_, "cadastral_codes": codes.as_metadata()}
        # Derive the building identifier from its cadastral parent (the parcel's
        # candidate ULPIN), exactly like the ML ingestion pipeline. The internal
        # UUID is never embedded in a value presented as a ULPIN.
        buildings_in_parcel = (
            await db.execute(
                select(func.count())
                .select_from(Building)
                .where(Building.parcel_id == parcel.id)
            )
        ).scalar() or 0
        building.candidate_ulpin = f"{parcel.candidate_ulpin}-B{buildings_in_parcel}"

        db.add(
            ULPINRecord(
                candidate_ulpin=building.candidate_ulpin,
                official_ulpin=None,
                entity_type="building",
                status=ULPINStatus.CANDIDATE,
                building_id=building.id,
                generation_method="geojson_import",
                confidence_score="MEDIUM",
                is_authoritative=False,
                legal_disclaimer=_ULPIN_DISCLAIMER,
                created_by=user.id,
            )
        )
        ulpins_generated += 1
        imported_ids.append(building.id)

    await db.commit()

    result = BuildingImportResult(
        filename=file.filename,
        features_received=len(features),
        buildings_imported=len(imported_ids),
        buildings_skipped=skipped,
        parcels_created=parcels_created,
        parcels_reused=parcels_reused,
        ulpins_generated=ulpins_generated,
        imported_building_ids=imported_ids,
        errors=errors,
        model_version=model_version,
        district=district,
        state=state,
        authoritative=False,
    )
    return ApiResponse(
        data=result,
        meta={"message": "GeoJSON import complete", "disclaimer": _ULPIN_DISCLAIMER},
    )


# NOTE: declared before "/{dataset_id}" so the literal path is not swallowed by the UUID route.
@router.get("/import-status", response_model=ApiResponse[ImportStatusOut])
async def import_status(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Row counts proving what is actually persisted (used to confirm an import worked)."""
    total_buildings = (
        await db.execute(select(func.count()).select_from(Building))
    ).scalar() or 0
    active_buildings = (
        await db.execute(
            select(func.count()).select_from(Building).where(Building.is_active == True)  # noqa: E712
        )
    ).scalar() or 0
    total_parcels = (
        await db.execute(select(func.count()).select_from(Parcel))
    ).scalar() or 0
    with_geometry = (
        await db.execute(
            select(func.count())
            .select_from(Building)
            .where(Building.footprint_2d.isnot(None))
        )
    ).scalar() or 0
    with_ulpin = (
        await db.execute(
            select(func.count())
            .select_from(Building)
            .where(Building.candidate_ulpin.isnot(None))
        )
    ).scalar() or 0

    return ApiResponse(
        data=ImportStatusOut(
            total_buildings=total_buildings,
            active_buildings=active_buildings,
            total_parcels=total_parcels,
            buildings_with_geometry=with_geometry,
            buildings_with_candidate_ulpin=with_ulpin,
        )
    )


@router.post("/register", response_model=ApiResponse[DatasetOut], status_code=status.HTTP_201_CREATED)
async def register_dataset(
    req: DatasetRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = DatasetService(db)
    ds = await svc.register_dataset(req, user)
    return ApiResponse(data=DatasetOut.model_validate(ds), meta={"message": "Dataset registered in catalog"})


@router.get("", response_model=ApiResponse[List[DatasetOut]])
async def list_datasets(
    modality: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = DatasetService(db)
    datasets = await svc.list_datasets(modality=modality)
    return ApiResponse(data=[DatasetOut.model_validate(d) for d in datasets], meta={"count": len(datasets)})


@router.get("/{dataset_id}", response_model=ApiResponse[DatasetOut])
async def get_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    svc = DatasetService(db)
    ds = await svc.get_dataset(dataset_id)
    return ApiResponse(data=DatasetOut.model_validate(ds))

"""
On-demand ingestion of real cadastral records for ANY coordinate in India.

Pipeline
--------
1. Live Overpass/OSM fetch  -> real building footprint geometry + real tags
                               (``height``, ``building:levels``, ``name``, addr:*).
2. Cadastral context        -> parcel/building/floors/units hierarchy.
3. ML engine (optional)     -> height derivation, floor detection, vertical unit
                               delineation, confidence + evidence fusion, emitting
                               a validated MLOutputContractV1.
4. Persistence              -> PostGIS parcel/building/floor[/unit] rows, CANDIDATE
                               ULPINs derived from the cadastral parent chain,
                               provenance + audit trail.

Honesty rules enforced here (do not relax):
  * ``official_ulpin`` is NEVER set. Only a government source may set it.
  * Every candidate ULPIN is derived from the parcel's candidate identifier.
  * Height/floor counts come from real OSM tags, or from the ML engine, or are
    left NULL. Nothing is defaulted to a plausible-looking number.
  * Re-running for the same OSM object updates nothing and creates no duplicate:
    the natural key is the OSM reference (``way/28846517``).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import MLEngineNotAvailableError, ValidationError
from app.core.logging import logger
from app.db.models.dataset import DatasetRegistry
from app.db.models.property import Building, Floor, Parcel, ScientificStatus, Unit
from app.db.models.provenance import ProvenanceRecord
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.db.models.user import User
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import (
    MLOutputContractV1,
    MLProcessParcelRequest,
    VerticalUnitGenRequest,
)
from app.integrations.osm import (
    FLOOR_TO_FLOOR_M,
    OSMBuilding,
    OverpassClient,
    pick_target_buildings,
)
from app.schemas.ingest import (
    IngestedBuildingOut,
    IngestedFloorOut,
    IngestedUnitOut,
    IngestLocationRequest,
    IngestLocationResponse,
)
from app.services.cadastral_codes import assign_cadastral_codes
from app.services.ulpin import ULPINService

def osm_building_type(tags: Dict[str, str]) -> str:
    """
    Resolve a useful building type from real OSM tags.

    ``building=yes`` is a placeholder meaning "a building is here" and is not a
    type. Rather than storing the literal string "yes" (which then propagated
    into floor/unit records), fall through to the specific OSM classification
    tag when present, and only then give up with "unclassified".
    """
    raw = (tags.get("building") or "").strip().lower()
    if raw and raw not in {"yes", "true", "1", "building"}:
        return raw
    for key in ("tourism", "amenity", "office", "shop", "industrial", "man_made", "healthcare", "building:part"):
        value = (tags.get(key) or "").strip().lower()
        if value and value not in {"yes", "true", "1"}:
            return value
    return "unclassified"


OSM_DATASET_NAME = "OpenStreetMap-India-Buildings"
OSM_DATASET_SOURCE = "https://www.openstreetmap.org (Overpass API)"
OSM_AUTHORITY = "OpenStreetMap contributors"
OSM_LICENSE = "ODbL-1.0"

_ULPIN_DISCLAIMER = (
    "Candidate ULPINs produced by on-demand ingestion are NON-AUTHORITATIVE analytical "
    "identifiers derived from a real cadastral parent chain. They do not constitute "
    "legal title and become cadastral records only once verified and gazetted by a "
    "competent government authority."
)


class OnDemandIngestService:
    """Fetch real footprints for a location and persist them as candidate records."""

    def __init__(self, db: AsyncSession, overpass: Optional[OverpassClient] = None):
        self.db = db
        self.overpass = overpass or OverpassClient()

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    async def ingest_location(
        self, req: IngestLocationRequest, user: User
    ) -> IngestLocationResponse:
        disclaimers: List[str] = [_ULPIN_DISCLAIMER]
        skipped_reasons: List[str] = []

        # 0. India extent guard — refuse to hammer Overpass for out-of-scope input.
        if not (68.0 <= req.lon <= 97.5 and 6.5 <= req.lat <= 37.5):
            raise ValidationError(
                f"Coordinate {req.lat},{req.lon} is outside the India extent "
                "(lon 68.0-97.5, lat 6.5-37.5)."
            )

        # 1. Real source data
        if req.osm_id:
            target = await self.overpass.building_by_osm_id(req.osm_id)
            found: List[OSMBuilding] = [target] if target else []
        else:
            found = await self.overpass.buildings_around(
                req.lat, req.lon, req.radius_m, name_contains=req.name_contains
            )

        selected = pick_target_buildings(
            found, name_contains=req.name_contains, osm_id=req.osm_id
        )[: req.max_buildings]

        if not found:
            skipped_reasons.append(
                "No OSM building footprints were found for this query. OpenStreetMap has "
                "no mapped building here; nothing was created."
            )
        elif not selected:
            skipped_reasons.append(
                f"{len(found)} footprint(s) were found but none matched the given filters "
                f"(name_contains={req.name_contains!r}, osm_id={req.osm_id})."
            )

        ingested: List[IngestedBuildingOut] = []
        counters = {
            "parcels_created": 0,
            "parcels_reused": 0,
            "floors_created": 0,
            "units_created": 0,
        }
        ml_used_any = False
        ml_unavailable_reason: Optional[str] = None

        for osm_building in selected:
            try:
                result = await self._persist_building(
                    osm_building, req, user
                )
            except Exception as exc:  # one bad footprint must not abort the batch
                logger.warning(
                    "On-demand ingestion failed for footprint",
                    osm_reference=osm_building.osm_reference,
                    error=str(exc),
                )
                skipped_reasons.append(
                    f"{osm_building.osm_reference} could not be ingested: {exc}"
                )
                continue

            counters["parcels_created"] += result["parcels_created"]
            counters["parcels_reused"] += result["parcels_reused"]
            counters["floors_created"] += result["floors_created"]
            counters["units_created"] += result["units_created"]
            ml_used_any = ml_used_any or result["building"].ml_used
            ml_unavailable_reason = ml_unavailable_reason or result.get("ml_reason")
            ingested.append(result["building"])

        if req.run_ml and not ml_used_any and ml_unavailable_reason:
            disclaimers.append(
                "ML engine was not used for these records: "
                f"{ml_unavailable_reason} Real OSM geometry and tags were still stored."
            )
        if not ml_used_any:
            disclaimers.append(
                "No ML inference was applied. Height/floor values shown come only from "
                "real OpenStreetMap tags; fields with no source remain NULL."
            )

        if ingested:
            await self._register_osm_dataset(user, len(ingested))

        await self.db.commit()

        return IngestLocationResponse(
            query_lat=req.lat,
            query_lon=req.lon,
            radius_m=req.radius_m,
            buildings_found=len(found),
            buildings_ingested=len(ingested),
            buildings_skipped=len(selected) - len(ingested),
            parcels_created=counters["parcels_created"],
            parcels_reused=counters["parcels_reused"],
            floors_created=counters["floors_created"],
            units_created=counters["units_created"],
            candidate_ulpins=[
                b.candidate_ulpin for b in ingested if b.candidate_ulpin
            ],
            buildings=ingested,
            skipped_reasons=skipped_reasons,
            authoritative=False,
            disclaimers=disclaimers,
        )

    # ------------------------------------------------------------------ #
    # Per-building persistence
    # ------------------------------------------------------------------ #

    async def _persist_building(
        self, osm: OSMBuilding, req: IngestLocationRequest, user: User
    ) -> Dict[str, Any]:
        parcel_number = f"OSM-{osm.osm_type[0].upper()}{osm.osm_id}"
        geometry_wkt = osm.to_wkt()
        import_hash = hashlib.sha256(
            f"{osm.osm_reference}|{geometry_wkt}".encode("utf-8")
        ).hexdigest()

        # 1. Cadastral context — caller-supplied, else the real OSM addr:* tags.
        admin = self._resolve_admin_context(osm, req)
        codes = assign_cadastral_codes(
            state=admin["state"],
            district=admin["district"],
            taluk=admin["taluk"],
            village=admin["village"],
        )
        parcel_ulpin = ULPINService.generate_parcel_ulpin(
            state=codes.state_code,
            district=codes.district_code,
            taluk=codes.taluk_code,
            village=codes.village_code,
            survey_number=parcel_number,
        )

        # 2. Idempotency: same OSM object already ingested?
        existing_building = (
            await self.db.execute(
                select(Building)
                .where(
                    Building.metadata_["osm_reference"].astext == osm.osm_reference,
                    Building.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
        ).scalars().first()
        if existing_building:
            logger.info(
                "OSM footprint already ingested; not duplicating it",
                osm_reference=osm.osm_reference,
            )
            # Re-running is safe and useful: if the hierarchy is still missing its
            # candidate vertical units (e.g. the ML service was down when the
            # footprint was first ingested) this completes it in place, without
            # creating a second building or a second set of floors.
            units_added = 0
            if req.run_ml and ml_client.enabled:
                units_added = await self._backfill_units(existing_building, osm, user)
            return {
                "building": await self._summarise(
                    existing_building, osm, already_existed=True
                ),
                "parcels_created": 0,
                "parcels_reused": 1,
                "floors_created": 0,
                "units_created": units_added,
                "ml_reason": None,
            }

        # 3. ML engine (optional, never fabricated)
        ml_output: Optional[MLOutputContractV1] = None
        ml_reason: Optional[str] = None
        if req.run_ml:
            if not ml_client.enabled:
                ml_reason = "ML_ENGINE_ENABLED is false."
            else:
                ml_output, ml_reason = await self._run_ml(osm, parcel_ulpin)

        # 4. Resolve height / floors from REAL signals, in priority order:
        #    measured OSM height tag > OSM building:levels > ML-derived > NULL.
        height_m = osm.height_m
        height_source = osm.height_source if osm.height_m is not None else None
        floor_count = osm.floor_count
        floor_source = osm.floor_source if osm.floor_count is not None else None

        if floor_count is None and ml_output and ml_output.floor_count:
            floor_count = int(ml_output.floor_count)
            floor_source = "ml_derived"
        if height_m is None and ml_output and ml_output.height:
            height_m = float(ml_output.height)
            height_source = "ml_derived"

        # 5. Parcel (create or reuse)
        parcel = (
            await self.db.execute(
                select(Parcel).where(Parcel.parcel_number == parcel_number)
            )
        ).scalars().first()
        parcels_created = 0
        parcels_reused = 0
        if parcel:
            parcels_reused = 1
        else:
            parcel = Parcel(
                parcel_number=parcel_number,
                survey_number=str(osm.osm_id),
                district=codes.district_name,
                taluk=codes.taluk_name,
                village=codes.village_name,
                state=codes.state_name,
                land_use=osm.tags.get("landuse"),
                official_ulpin=None,  # never fabricated
                candidate_ulpin=parcel_ulpin,
                status=ScientificStatus.CANDIDATE,
                boundary_wkt=geometry_wkt,
                source_crs="EPSG:4326",
                processing_crs="EPSG:3857",
                is_verified=False,
                metadata_={
                    "import_hash": import_hash,
                    "osm_reference": osm.osm_reference,
                    "source_url": osm.source_url,
                    "parcel_boundary_basis": "DERIVED_FROM_OSM_BUILDING_FOOTPRINT",
                    "cadastral_codes": codes.as_metadata(),
                },
            )
            self.db.add(parcel)
            await self.db.flush()
            parcels_created = 1

        # 6. Building
        building = Building(
            parcel_id=parcel.id,
            building_name=osm.name or osm.tags.get("official_name"),
            building_type=osm_building_type(osm.tags),
            floor_count=floor_count,
            height_m=height_m,
            height_confidence=(ml_output.confidence if (ml_output and height_source == "ml_derived") else None),
            uncertainty_range_m=(ml_output.uncertainty if (ml_output and height_source == "ml_derived") else None),
            footprint_wkt=geometry_wkt,
            source_crs="EPSG:4326",
            processing_crs="EPSG:3857",
            official_ulpin=None,  # never fabricated
            candidate_ulpin=None,  # set below from the cadastral parent chain
            status=ScientificStatus.CANDIDATE,
            ml_derived=bool(ml_output and (height_source == "ml_derived" or floor_source == "ml_derived")),
            ml_model_version=(ml_output.model_version if ml_output else None),
            ml_confidence_score=(ml_output.confidence if ml_output else None),
            is_verified=False,
            metadata_={
                "import_hash": import_hash,
                "osm_reference": osm.osm_reference,
                "osm_type": osm.osm_type,
                "osm_id": osm.osm_id,
                "source_url": osm.source_url,
                "source_license": OSM_LICENSE,
                "osm_tags": osm.tags,
                "height_source": height_source or "unavailable",
                "floor_source": floor_source or "unavailable",
                "cadastral_codes": codes.as_metadata(),
                "ml": (
                    {
                        "provenance_id": ml_output.provenance_id,
                        "data_status": ml_output.data_status,
                        "review_status": ml_output.review_status,
                        "volume_id": ml_output.volume_id,
                        "validation": ml_output.validation,
                        "evidence": ml_output.evidence,
                        "generated_at": ml_output.generated_at,
                    }
                    if ml_output
                    else None
                ),
            },
        )
        self.db.add(building)
        await self.db.flush()

        # 7. Materialise PostGIS geometry + geodesic area in one shot.
        await self.db.execute(
            text(
                "UPDATE buildings SET footprint_2d = ST_GeomFromText(:wkt, 4326), "
                "footprint_area_sqm = ST_Area(ST_GeomFromText(:wkt, 4326)::geography) "
                "WHERE id = :bid"
            ),
            {"wkt": geometry_wkt, "bid": building.id},
        )
        # The parcel needs its geodesic area too. Previously only the building got
        # one, so /spatial/search returned a parcel with area_sqm = null even when
        # its geometry was present and the building on it had a real area.
        await self.db.execute(
            text(
                "UPDATE parcels SET geometry_2d = ST_Multi(ST_GeomFromText(:wkt, 4326)), "
                "area_sqm = ST_Area(ST_GeomFromText(:wkt, 4326)::geography) "
                "WHERE id = :pid"
            ),
            {"wkt": geometry_wkt, "pid": parcel.id},
        )

        area_sqm = (
            await self.db.execute(
                text("SELECT footprint_area_sqm FROM buildings WHERE id = :bid"),
                {"bid": building.id},
            )
        ).scalar()

        # 8. Candidate ULPIN from the cadastral parent chain (never the raw UUID)
        buildings_in_parcel = (
            await self.db.execute(
                select(func.count())
                .select_from(Building)
                .where(Building.parcel_id == parcel.id)
            )
        ).scalar() or 0
        building.candidate_ulpin = f"{parcel.candidate_ulpin}-B{buildings_in_parcel}"

        self.db.add(
            ULPINRecord(
                candidate_ulpin=building.candidate_ulpin,
                official_ulpin=None,
                entity_type="building",
                status=ULPINStatus.CANDIDATE,
                building_id=building.id,
                parcel_id=parcel.id,
                generation_method="osm_ingest",
                confidence_score="MEDIUM" if ml_output else "LOW",
                is_authoritative=False,
                legal_disclaimer=_ULPIN_DISCLAIMER,
                created_by=user.id,
            )
        )

        # 9. Floors (only when a real or ML-derived floor count exists)
        floors_created = 0
        floors: List[Floor] = []
        if floor_count and floor_count > 0:
            per_floor_height = (
                round(float(height_m) / floor_count, 3)
                if height_m
                else FLOOR_TO_FLOOR_M
            )
            for index in range(int(floor_count)):
                floor = Floor(
                    building_id=building.id,
                    floor_number=index,
                    floor_label="G" if index == 0 else f"F{index}",
                    floor_use=osm_building_type(osm.tags),
                    height_above_ground_m=round(index * per_floor_height, 3),
                    ceiling_height_m=per_floor_height,
                    floor_area_sqm=area_sqm,
                    official_ulpin=None,
                    candidate_ulpin=f"{building.candidate_ulpin}-F{index}",
                    status=ScientificStatus.CANDIDATE,
                    ml_derived=False,
                    ml_confidence_score=(ml_output.confidence if ml_output else None),
                    is_verified=False,
                    metadata_={
                        "floor_source": floor_source or "unavailable",
                        "height_basis": (
                            f"{height_source} / {floor_count} levels"
                            if height_m
                            else f"documented {FLOOR_TO_FLOOR_M} m storey constant"
                        ),
                    },
                )
                self.db.add(floor)
                floors.append(floor)
            await self.db.flush()
            floors_created = len(floors)
            for floor in floors:
                self.db.add(
                    ULPINRecord(
                        candidate_ulpin=floor.candidate_ulpin,
                        official_ulpin=None,
                        entity_type="floor",
                        status=ULPINStatus.CANDIDATE,
                        floor_id=floor.id,
                        building_id=building.id,
                        parcel_id=parcel.id,
                        generation_method="osm_ingest",
                        confidence_score="MEDIUM" if ml_output else "LOW",
                        is_authoritative=False,
                        legal_disclaimer=_ULPIN_DISCLAIMER,
                        created_by=user.id,
                    )
                )

        # 10. Units — only from the ML engine's documented candidate delineation.
        units_created = 0
        if floors and ml_client.enabled and req.run_ml and area_sqm:
            units_created = await self._generate_units(
                floors, building, osm, float(area_sqm), user
            )

        # 11. Provenance
        self.db.add(
            ProvenanceRecord(
                entity_type="parcel",
                entity_id=parcel.id,
                data_source=f"{OSM_AUTHORITY} / OpenStreetMap {osm.osm_reference}",
                derivation_method=(
                    "osm_fetch+ml_inference" if ml_output else "osm_fetch"
                ),
                input_datasets=[OSM_DATASET_NAME],
                model_version=(ml_output.model_version if ml_output else None),
                input_hash=import_hash,
                confidence_label=("MEDIUM" if ml_output else "LOW"),
                notes=(
                    f"Real OSM footprint {osm.source_url} ({OSM_LICENSE}). "
                    f"Parcel boundary derived from the building footprint. "
                    f"Height source: {height_source or 'unavailable'}; "
                    f"floor source: {floor_source or 'unavailable'}. "
                    + (
                        f"ML provenance_id={ml_output.provenance_id}."
                        if ml_output
                        else "No ML inference applied."
                    )
                ),
                created_by=user.id,
            )
        )

        await self.db.commit()
        await self.db.refresh(building)

        summary = await self._summarise(
            building,
            osm,
            already_existed=False,
            floors=floors,
            parcel_number=parcel_number,
        )
        return {
            "building": summary,
            "parcels_created": parcels_created,
            "parcels_reused": parcels_reused,
            "floors_created": floors_created,
            "units_created": units_created,
            "ml_reason": ml_reason,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _run_ml(
        self, osm: OSMBuilding, parcel_reference: str
    ) -> Tuple[Optional[MLOutputContractV1], Optional[str]]:
        """Invoke the ML engine with real inputs only. Failures are non-fatal."""
        # A measured `height` tag is passed through as the height signal; otherwise
        # the real `building:levels` tag lets the engine derive one.
        supplied_height = osm.height_m if osm.height_source == "osm_height_tag" else None
        supplied_levels = osm.floor_count if osm.height_source != "osm_height_tag" else None
        try:
            output = await ml_client.process_parcel(
                MLProcessParcelRequest(
                    official_ulpin=parcel_reference,
                    parcel_polygon=list(osm.outer_ring),
                    building_footprint=list(osm.outer_ring),
                    height_m=supplied_height,
                    floor_count=supplied_levels,
                    height_source=osm.height_source,
                    evidence=[osm.evidence_item()],
                    crs="EPSG:4326",
                )
            )
            return output, None
        except MLEngineNotAvailableError as exc:
            logger.warning("ML engine unavailable during ingest", error=str(exc))
            return None, str(exc)
        except Exception as exc:  # schema/validation/transport
            logger.warning("ML engine call failed during ingest", error=str(exc))
            return None, str(exc)

    async def _backfill_units(
        self, building: Building, osm: OSMBuilding, user: User
    ) -> int:
        """Complete a previously ingested building's candidate unit hierarchy."""
        if building.footprint_area_sqm is None:
            return 0
        floors = (
            await self.db.execute(
                select(Floor)
                .where(Floor.building_id == building.id, Floor.is_active == True)  # noqa: E712
                .order_by(Floor.floor_number)
            )
        ).scalars().all()
        if not floors:
            return 0
        return await self._generate_units(
            floors, building, osm, float(building.footprint_area_sqm), user
        )

    async def _generate_units(
        self,
        floors: Sequence[Floor],
        building: Building,
        osm: OSMBuilding,
        floor_area_sqm: float,
        user: User,
    ) -> int:
        """Candidate vertical units via the ML engine's documented delineation."""
        created = 0
        for floor in floors:
            # Never duplicate: (floor_id, unit_number) is a unique index and a
            # floor that already has candidate units is left untouched.
            existing_units = (
                await self.db.execute(
                    select(func.count()).select_from(Unit).where(Unit.floor_id == floor.id)
                )
            ).scalar() or 0
            if existing_units:
                continue
            try:
                response = await ml_client.generate_vertical_units(
                    VerticalUnitGenRequest(
                        floor_id=str(floor.id),
                        building_id=str(building.id),
                        floor_number=floor.floor_number,
                        floor_area_sqm=floor_area_sqm,
                        building_type=building.building_type or "residential",
                    )
                )
            except Exception as exc:
                logger.info(
                    "Vertical unit generation skipped for floor",
                    floor=str(floor.id),
                    error=str(exc),
                )
                continue
            for unit in response.units:
                candidate = f"{floor.candidate_ulpin}-U{unit.unit_number.replace('U-', '')}"
                record = Unit(
                    floor_id=floor.id,
                    unit_number=unit.unit_number,
                    unit_type=unit.unit_type,
                    area_sqm=unit.area_sqm,
                    volume_cum=unit.volume_cum,
                    official_ulpin=None,
                    candidate_ulpin=candidate,
                    status=ScientificStatus.CANDIDATE,
                    ml_derived=True,
                    ml_confidence_score=unit.confidence,
                    is_verified=False,
                    metadata_={
                        "unit_delineation": "ML_ENGINE_VERTICAL_UNIT_GENERATION",
                        "osm_reference": osm.osm_reference,
                        "source_status": "CANDIDATE_VERTICAL_UNIT_GENERATION",
                        "basis": (
                            "ML engine candidate delineation. The engine partitions the "
                            "floor by area (documented heuristic: one candidate unit per "
                            "~100 m2), so this is an analytical subdivision, NOT a count "
                            "of real rooms/dwellings."
                        ),
                        "is_authoritative": False,
                    },
                )
                self.db.add(record)
                await self.db.flush()
                self.db.add(
                    ULPINRecord(
                        candidate_ulpin=candidate,
                        official_ulpin=None,
                        entity_type="unit",
                        status=ULPINStatus.CANDIDATE,
                        unit_id=record.id,
                        floor_id=floor.id,
                        building_id=building.id,
                        parcel_id=building.parcel_id,
                        generation_method="ml_derived",
                        confidence_score="MEDIUM",
                        is_authoritative=False,
                        legal_disclaimer=_ULPIN_DISCLAIMER,
                        created_by=user.id,
                    )
                )
                created += 1
        if created:
            await self.db.commit()
            await self.db.refresh(building)
        return created

    def _resolve_admin_context(
        self, osm: OSMBuilding, req: IngestLocationRequest
    ) -> Dict[str, Optional[str]]:
        tags = osm.tags
        return {
            "state": req.state or tags.get("addr:state"),
            "district": req.district or tags.get("addr:district") or tags.get("addr:city"),
            "taluk": req.taluk or tags.get("addr:subdistrict") or tags.get("addr:city"),
            "village": (
                req.village
                or tags.get("addr:suburb")
                or tags.get("addr:postcode")
                or osm.name
            ),
        }

    async def _summarise(
        self,
        building: Building,
        osm: OSMBuilding,
        *,
        already_existed: bool,
        floors: Optional[Sequence[Floor]] = None,
        parcel_number: Optional[str] = None,
    ) -> IngestedBuildingOut:
        parcel = await self.db.get(Parcel, building.parcel_id)
        area = None
        if building.footprint_area_sqm is not None:
            area = float(building.footprint_area_sqm)

        floor_rows = floors
        if floor_rows is None:
            floor_rows = (
                await self.db.execute(
                    select(Floor)
                    .where(Floor.building_id == building.id, Floor.is_active == True)  # noqa: E712
                    .order_by(Floor.floor_number)
                )
            ).scalars().all()

        floor_out: List[IngestedFloorOut] = []
        for floor in floor_rows:
            units = (
                await self.db.execute(
                    select(Unit)
                    .where(Unit.floor_id == floor.id, Unit.is_active == True)  # noqa: E712
                    .order_by(Unit.unit_number)
                )
            ).scalars().all()
            floor_out.append(
                IngestedFloorOut(
                    id=floor.id,
                    floor_number=floor.floor_number,
                    floor_label=floor.floor_label,
                    floor_use=floor.floor_use,
                    height_above_ground_m=floor.height_above_ground_m,
                    ceiling_height_m=floor.ceiling_height_m,
                    floor_area_sqm=(
                        float(floor.floor_area_sqm)
                        if floor.floor_area_sqm is not None
                        else None
                    ),
                    candidate_ulpin=floor.candidate_ulpin,
                    status=floor.status,
                    floor_source=(floor.metadata_ or {}).get("floor_source"),
                    units=[
                        IngestedUnitOut(
                            id=u.id,
                            unit_number=u.unit_number,
                            unit_type=u.unit_type,
                            area_sqm=(float(u.area_sqm) if u.area_sqm is not None else None),
                            candidate_ulpin=u.candidate_ulpin,
                            status=u.status,
                            ml_derived=u.ml_derived,
                        )
                        for u in units
                    ],
                )
            )

        meta = building.metadata_ or {}
        ml_block = meta.get("ml") or {}
        centroid_lon, centroid_lat = osm.centroid()

        return IngestedBuildingOut(
            building_id=building.id,
            parcel_id=building.parcel_id,
            parcel_number=parcel.parcel_number if parcel else (parcel_number or ""),
            building_name=building.building_name,
            building_type=building.building_type,
            osm_type=osm.osm_type,
            osm_id=osm.osm_id,
            source_url=osm.source_url,
            osm_tags=osm.tags,
            height_m=building.height_m,
            height_source=meta.get("height_source"),
            floor_count=building.floor_count,
            floor_source=meta.get("floor_source"),
            footprint_area_sqm=area,
            footprint_geojson=osm.to_geojson_polygon(),
            centroid={"lon": centroid_lon, "lat": centroid_lat},
            official_ulpin=building.official_ulpin,
            candidate_ulpin=building.candidate_ulpin,
            status=building.status,
            ml_used=bool(ml_block),
            ml_model_version=building.ml_model_version,
            ml_confidence=building.ml_confidence_score,
            ml_data_status=ml_block.get("data_status"),
            ml_review_status=ml_block.get("review_status"),
            ml_validation=ml_block.get("validation"),
            floors=floor_out,
            units_created=sum(len(f.units) for f in floor_out),
            already_existed=already_existed,
        )

    async def _register_osm_dataset(self, user: User, ingested_now: int) -> None:
        """Register/refresh the OSM dataset catalogue entry (real source metadata)."""
        dataset = (
            await self.db.execute(
                select(DatasetRegistry).where(DatasetRegistry.name == OSM_DATASET_NAME)
            )
        ).scalars().first()
        total_buildings = (
            await self.db.execute(
                select(func.count())
                .select_from(Building)
                .where(Building.metadata_["osm_reference"].astext.is_not(None))
            )
        ).scalar() or 0
        if dataset:
            dataset.record_count = str(total_buildings)
            dataset.coverage_area = "India (on-demand per coordinate)"
            return
        self.db.add(
            DatasetRegistry(
                name=OSM_DATASET_NAME,
                version="live",
                source=OSM_DATASET_SOURCE,
                authority=OSM_AUTHORITY,
                license=OSM_LICENSE,
                modality="osm",
                crs="EPSG:4326",
                resolution_m="vector (footprint)",
                coverage_area="India (on-demand per coordinate)",
                record_count=str(total_buildings),
                is_active=True,
                validation_status="CANDIDATE",
                metadata_={
                    "is_authoritative": False,
                    "note": (
                        "Crowd-sourced OSM footprints used as candidate source geometry. "
                        "Not a cadastral record of title."
                    ),
                    "last_ingest_batch": ingested_now,
                },
                created_by=user.id,
            )
        )

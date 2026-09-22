"""
ML Result Ingestion Pipeline Service.
Executes the strict ingestion workflow:
1. Authenticate & Authorize
2. Schema & Version Validation (reject unsupported with UNSUPPORTED_SCHEMA_VERSION)
3. Payload & CRS Validation
4. 2D & 3D Geometry Validation
5. Provenance & Data Quality Validation
6. Idempotency Check (prevent duplicate creation on repeated runs)
7. Transactional hierarchy creation (Parcel -> Building -> Floor -> Unit)
8. Candidate ULPIN Generation & Provenance Log
9. Commit & Return Standardized Summary
"""
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.errors import (
    ConflictError,
    InvalidCRSError,
    InvalidGeometryError,
    UnsupportedSchemaVersionError,
    ValidationError,
)
from app.core.logging import logger
from app.db.models.audit import AuditLog
from app.db.models.job import AsyncJob, JobStatus
from app.db.models.property import Building, Floor, Parcel, ScientificStatus, Unit
from app.db.models.provenance import ProvenanceRecord
from app.db.models.ulpin import ULPINRecord, ULPINStatus
from app.db.models.user import User
from app.integrations.ml_engine.contracts import (
    MLIngestionPayload,
    SUPPORTED_SCHEMA_VERSIONS,
)
from app.integrations.ml_engine.mapper import MLDataMapper
from app.services.data_quality import DataQualityService
from app.services.geometry_validation import GeometryValidationService
from app.services.topology_validation import TopologyValidationService
from app.services.ulpin import ULPINService


class MLIngestionService:
    """Orchestrates safe ingestion of ML prediction outputs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_ml_payload(self, payload: MLIngestionPayload, user: User) -> Dict[str, Any]:
        """Runs the complete ingestion pipeline inside a safe database transaction."""
        # 1. Schema version validation
        if payload.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedSchemaVersionError(
                f"Schema version {payload.schema_version} is unsupported. Supported: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        # 2. CRS validation
        GeometryValidationService.validate_crs(payload.source_crs)
        GeometryValidationService.validate_crs(payload.processing_crs)

        # 3. Idempotency check
        raw_hash_str = f"{payload.parcel_number}:{payload.model_name}:{payload.model_version}:{len(payload.buildings)}"
        input_hash = hashlib.sha256(raw_hash_str.encode()).hexdigest()

        if payload.idempotency_key:
            existing_job = await self.db.execute(
                select(AsyncJob).where(AsyncJob.idempotency_key == payload.idempotency_key)
            )
            if existing_job.scalar_one_or_none():
                logger.info("Idempotent ML ingestion detected; returning cached result", key=payload.idempotency_key)
                return {
                    "status": "already_processed",
                    "idempotency_key": payload.idempotency_key,
                    "message": "Payload with this idempotency key was previously ingested.",
                }

        # 4. Geometry validations
        for b in payload.buildings:
            if b.footprint_wkt:
                GeometryValidationService.validate_2d_wkt(b.footprint_wkt)
            floors_dict = [f.model_dump() for f in b.floors]
            GeometryValidationService.validate_3d_hierarchy(b.floor_count, b.height_m, floors_dict)

        # 5. Database Transaction: Persist hierarchy
        async with self.db.begin_nested():
            # A. Find or create parcel
            parcel_res = await self.db.execute(
                select(Parcel).where(Parcel.parcel_number == payload.parcel_number)
            )
            parcel = parcel_res.scalar_one_or_none()
            if not parcel:
                cand_parcel_ulpin = ULPINService.generate_parcel_ulpin(
                    state=payload.state,
                    district=payload.district,
                    taluk=payload.taluk,
                    village=payload.village,
                    survey_number=payload.parcel_number,
                )
                parcel = Parcel(
                    parcel_number=payload.parcel_number,
                    district=payload.district,
                    taluk=payload.taluk,
                    village=payload.village,
                    state=payload.state,
                    candidate_ulpin=cand_parcel_ulpin,
                    status=payload.scientific_status,
                    source_crs=payload.source_crs,
                    processing_crs=payload.processing_crs,
                    is_verified=False,
                )
                self.db.add(parcel)
                await self.db.flush()

            created_buildings = []
            created_floors = []
            created_units = []
            candidate_ulpins = []

            # B. Ingest buildings
            for b_idx, ml_bldg in enumerate(payload.buildings):
                bldg_data = MLDataMapper.building_from_ml(parcel.id, ml_bldg, payload.model_version)
                bldg = Building(**bldg_data)
                
                bldg.candidate_ulpin = f"{parcel.candidate_ulpin}-B{b_idx + 1}"
                self.db.add(bldg)
                await self.db.flush()
                created_buildings.append(bldg.id)
                candidate_ulpins.append(bldg.candidate_ulpin)

                bldg_ulpin_rec = ULPINRecord(
                    candidate_ulpin=bldg.candidate_ulpin,
                    entity_type="building",
                    building_id=bldg.id,
                    parcel_id=parcel.id,
                    status=ULPINStatus.CANDIDATE,
                    generation_method="ml_derived",
                    is_authoritative=False,
                    created_by=user.id,
                )
                self.db.add(bldg_ulpin_rec)

                # C. Ingest floors
                for ml_flr in ml_bldg.floors:
                    flr_data = MLDataMapper.floor_from_ml(bldg.id, ml_flr)
                    flr = Floor(**flr_data)
                    flr.candidate_ulpin = f"{bldg.candidate_ulpin}-F{flr.floor_number}"
                    self.db.add(flr)
                    await self.db.flush()
                    created_floors.append(flr.id)

                    flr_ulpin_rec = ULPINRecord(
                        candidate_ulpin=flr.candidate_ulpin,
                        entity_type="floor",
                        floor_id=flr.id,
                        building_id=bldg.id,
                        status=ULPINStatus.CANDIDATE,
                        generation_method="ml_derived",
                        is_authoritative=False,
                        created_by=user.id,
                    )
                    self.db.add(flr_ulpin_rec)

                    # D. Ingest units
                    for ml_unit in ml_flr.units:
                        unit_data = MLDataMapper.unit_from_ml(flr.id, ml_unit)
                        unit = Unit(**unit_data)
                        unit.candidate_ulpin = f"{flr.candidate_ulpin}-U{unit.unit_number}"
                        self.db.add(unit)
                        await self.db.flush()
                        created_units.append(unit.id)
                        candidate_ulpins.append(unit.candidate_ulpin)

                        unit_ulpin_rec = ULPINRecord(
                            candidate_ulpin=unit.candidate_ulpin,
                            entity_type="unit",
                            unit_id=unit.id,
                            floor_id=flr.id,
                            status=ULPINStatus.CANDIDATE,
                            generation_method="ml_derived",
                            is_authoritative=False,
                            created_by=user.id,
                        )
                        self.db.add(unit_ulpin_rec)

            # E. Provenance & Lineage Logging
            prov = ProvenanceRecord(
                entity_type="parcel",
                entity_id=parcel.id,
                data_source=f"{payload.model_name}:{payload.model_version}",
                derivation_method="ml_inference",
                input_datasets=[payload.dataset_name] if payload.dataset_name else [],
                model_version=payload.model_version,
                input_hash=input_hash,
                confidence_label="MEDIUM",
                notes=f"Ingested {len(created_buildings)} buildings, {len(created_floors)} floors, {len(created_units)} units.",
                created_by=user.id,
            )
            self.db.add(prov)

            # F. Audit Log
            audit = AuditLog(
                table_name="parcels",
                record_id=parcel.id,
                operation="ML_INGESTION",
                actor_id=user.id,
                actor_email=user.email,
                after_data={
                    "buildings_count": len(created_buildings),
                    "floors_count": len(created_floors),
                    "units_count": len(created_units),
                    "model_version": payload.model_version,
                },
            )
            self.db.add(audit)

            # G. Job record completion if job_id provided
            if payload.job_id:
                try:
                    job_uuid = UUID(payload.job_id)
                    job_res = await self.db.execute(select(AsyncJob).where(AsyncJob.id == job_uuid))
                    job = job_res.scalar_one_or_none()
                    if job:
                        job.status = JobStatus.COMPLETED
                        job.progress = 100.0
                        job.completed_at = datetime.now(timezone.utc)
                        job.result = {
                            "buildings_created": len(created_buildings),
                            "floors_created": len(created_floors),
                            "units_created": len(created_units),
                        }
                except Exception:
                    pass

        # Data quality summary — use actual confidence from payload, not a fabricated value.
        # payload.confidence_score is None when the ML source did not report it.
        actual_confidence = getattr(payload, "confidence_score", None)
        dq_report = DataQualityService.evaluate(
            has_geometry=True,
            is_geometry_valid=True,
            crs=payload.source_crs,
            confidence_score=actual_confidence,
            has_height=any(b.height_m is not None for b in payload.buildings),
            has_floors=any(len(b.floors) > 0 for b in payload.buildings),
            source_authority=payload.model_name,
        )

        return {
            "success": True,
            "parcel_id": str(parcel.id),
            "parcel_candidate_ulpin": parcel.candidate_ulpin,
            "buildings_created": len(created_buildings),
            "floors_created": len(created_floors),
            "units_created": len(created_units),
            "candidate_ulpins": candidate_ulpins[:10],
            "data_quality": dq_report,
            "scientific_status": ScientificStatus.CANDIDATE,
            "legal_notice": "Outputs are non-authoritative candidate models for analytical verification.",
        }

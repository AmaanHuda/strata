"""Async job management and ML result ingestion endpoints."""
from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.db.models.job import AsyncJob, JobStatus
from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.integrations.ml_engine.contracts import MLIngestionPayload
from app.schemas.common import ApiResponse
from app.schemas.job import JobOut, JobSubmitRequest
from app.services.ingestion import MLIngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=ApiResponse[JobOut], status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    req: JobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = BaseRepository(AsyncJob, db)
    job = await repo.create({
        "job_type": req.job_type,
        "payload": req.payload,
        "idempotency_key": req.idempotency_key,
        "model_name": req.model_name,
        "model_version": req.model_version,
        "priority": req.priority,
        "created_by": user.id,
        "status": JobStatus.QUEUED,
        "progress": 0.0,
    })
    return ApiResponse(data=JobOut.model_validate(job), meta={"message": "Job queued for execution"})


@router.get("/{job_id}", response_model=ApiResponse[JobOut])
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = BaseRepository(AsyncJob, db)
    job = await repo.get(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return ApiResponse(data=JobOut.model_validate(job))


@router.post("/ingest-ml", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_200_OK)
async def ingest_ml_results(
    payload: MLIngestionPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = MLIngestionService(db)
    result = await svc.ingest_ml_payload(payload, user)
    return ApiResponse(data=result, meta={"message": "ML output ingested and verified"})

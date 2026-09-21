"""Async job management and execution endpoints."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.models.job import AsyncJob, JobStatus
from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.integrations.ml_engine.contracts import MLIngestionPayload
from app.schemas.common import ApiResponse
from app.schemas.job import JobOut, JobSubmitRequest
from app.services.ingestion import MLIngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


VALID_JOB_TYPES = {
    "batch_validation",
    "ulpin_batch",
    "cadastral_audit",
    "height_estimation",
    "floor_segmentation",
    "3d_reconstruction",
}


@router.post("", response_model=ApiResponse[JobOut], status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    req: JobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Submits an async job (batch validation, cadastral audit, ulpin generation).
    Supports idempotency via idempotency_key.
    Enqueues job to Redis task queue for worker execution.
    """
    if req.job_type not in VALID_JOB_TYPES:
        from app.core.errors import ValidationError
        raise ValidationError(f"Invalid job_type: '{req.job_type}'. Must be one of {sorted(VALID_JOB_TYPES)}")

    repo = BaseRepository(AsyncJob, db)

    # 1. Check idempotency
    if req.idempotency_key:
        stmt = select(AsyncJob).where(AsyncJob.idempotency_key == req.idempotency_key)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return ApiResponse(
                data=JobOut.model_validate(existing),
                meta={"message": "Existing job returned via idempotency key"},
            )

    # 2. Create job in database
    job = await repo.create({
        "job_type": req.job_type,
        "payload": req.payload,
        "idempotency_key": req.idempotency_key,
        "model_name": req.model_name,
        "model_version": req.model_version,
        "created_by": user.id,
        "status": JobStatus.QUEUED,
        "progress": 0.0,
        "retry_count": 0,
        "max_retries": 3,
    })

    # 3. Enqueue to Redis queue for background workers
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        await r.rpush("strata:jobs:queue", str(job.id))
        await r.aclose()
    except Exception:
        # Fallback: Job remains in QUEUED status in DB and worker DB polling catches it
        pass

    return ApiResponse(
        data=JobOut.model_validate(job),
        meta={"message": "Job queued for background execution"},
    )


@router.get("", response_model=ApiResponse[List[JobOut]])
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    job_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lists jobs. Non-admin/surveyor users only see jobs they submitted.
    """
    stmt = select(AsyncJob).order_by(AsyncJob.created_at.desc()).limit(limit).offset(offset)

    # Role-based object-level authorization
    if user.role not in [UserRole.ADMIN, UserRole.SURVEYOR]:
        stmt = stmt.where(AsyncJob.created_by == user.id)

    if status_filter:
        stmt = stmt.where(AsyncJob.status == status_filter.upper())
    if job_type:
        stmt = stmt.where(AsyncJob.job_type == job_type)

    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return ApiResponse(
        data=[JobOut.model_validate(j) for j in jobs],
        meta={"count": len(jobs), "limit": limit, "offset": offset},
    )


@router.get("/{job_id}", response_model=ApiResponse[JobOut])
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Gets details and status of an async job.
    Enforces object-level ownership check.
    """
    repo = BaseRepository(AsyncJob, db)
    job = await repo.get(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")

    # Authorization
    if user.role not in [UserRole.ADMIN, UserRole.SURVEYOR]:
        if job.created_by and job.created_by != user.id:
            raise ForbiddenError("You do not have access to view this job")

    return ApiResponse(data=JobOut.model_validate(job))


@router.post("/{job_id}/cancel", response_model=ApiResponse[JobOut])
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cancels an in-progress or queued job.
    Cannot cancel already completed or failed jobs.
    """
    repo = BaseRepository(AsyncJob, db)
    job = await repo.get(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")

    # Authorization check
    if user.role not in [UserRole.ADMIN, UserRole.SURVEYOR]:
        if job.created_by and job.created_by != user.id:
            raise ForbiddenError("You do not have permission to cancel this job")

    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise ConflictError(f"Cannot cancel job in terminal state: {job.status}")

    if job.status == JobStatus.CANCELLED:
        return ApiResponse(data=JobOut.model_validate(job), meta={"message": "Job already cancelled"})

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    job.progress_message = "Job cancelled by user request"
    await db.commit()
    await db.refresh(job)

    return ApiResponse(
        data=JobOut.model_validate(job),
        meta={"message": f"Job {job_id} successfully cancelled"},
    )


@router.post("/ingest-ml", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_200_OK)
async def ingest_ml_results(
    payload: MLIngestionPayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SURVEYOR, UserRole.ANALYST)),
):
    svc = MLIngestionService(db)
    result = await svc.ingest_ml_payload(payload, user)
    return ApiResponse(data=result, meta={"message": "ML output ingested and verified"})

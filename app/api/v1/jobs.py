"""Async job management endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.models.job import AsyncJob
from app.db.repositories.base import BaseRepository
from app.db.session import get_db
from app.schemas.job import JobOut, JobSubmitRequest

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=202)
async def submit_job(
    req: JobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = BaseRepository(AsyncJob, db)
    job = await repo.create({
        "job_type": req.job_type,
        "input_payload": req.input_payload,
        "priority": req.priority,
        "submitted_by": user.id,
        "status": "pending",
    })
    # TODO: enqueue to Celery worker
    return job


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    repo = BaseRepository(AsyncJob, db)
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

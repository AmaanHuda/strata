"""Health check endpoints (Liveness, Readiness, Detailed)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from app.core.config import settings
from app.db.session import get_db
from app.integrations.ml_engine.client import ml_client
from app.schemas.common import ApiResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthResponse])
@router.get("/api/v1/health", response_model=ApiResponse[HealthResponse])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive readiness and component status."""
    components = {}
    
    # 1. Database check
    try:
        await db.execute(text("SELECT 1;"))
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)}"

    # 2. PostGIS check
    try:
        res = await db.execute(text("SELECT PostGIS_Version();"))
        ver = res.scalar()
        components["postgis"] = f"available: {ver}"
    except Exception as e:
        components["postgis"] = "unavailable (standard postgres fallback)"

    # 3. Redis check
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        components["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)}"

    # 4. ML Engine client
    try:
        ml_res = await ml_client.health_check()
        components["ml_engine"] = ml_res.status
    except Exception as e:
        components["ml_engine"] = "unavailable"

    overall = "healthy" if components.get("database") == "healthy" else "degraded"

    return ApiResponse(
        data=HealthResponse(
            status=overall,
            version="2.0.0",
            database="PostgreSQL + PostGIS",
            environment=settings.ENVIRONMENT,
            components=components,
        )
    )


@router.get("/health/live")
async def liveness_probe():
    """Kubernetes / Docker Liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Kubernetes / Docker Readiness probe."""
    try:
        await db.execute(text("SELECT 1;"))
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}

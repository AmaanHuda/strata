"""Health and readiness probe endpoints."""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db
from app.schemas.common import ApiResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthResponse])
@router.get("/api/v1/health", response_model=ApiResponse[HealthResponse])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive readiness and component status."""
    components = {}

    # 1. Database check — log internal error, never expose it to clients
    try:
        await db.execute(text("SELECT 1;"))
        components["database"] = "healthy"
    except Exception as e:
        logger.error("Health check: database connectivity failed", error=str(e))
        components["database"] = "unhealthy"

    # 2. PostGIS check
    try:
        res = await db.execute(text("SELECT PostGIS_Version();"))
        ver = res.scalar()
        components["postgis"] = f"available: {ver}"
    except Exception as e:
        logger.warning("Health check: PostGIS unavailable", error=str(e))
        components["postgis"] = "unavailable"

    # 3. Redis check (short timeout to prevent stalling)
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        await r.ping()
        components["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        logger.warning("Health check: Redis unavailable", error=str(e))
        components["redis"] = "unhealthy"

    # 4. ML Engine status (decoupled boundary — check only if explicitly enabled)
    if settings.ML_ENGINE_ENABLED:
        try:
            from app.integrations.ml_engine.client import ml_client
            ml_res = await ml_client.health_check()
            components["ml_engine"] = ml_res.status
        except Exception as e:
            logger.warning("Health check: ML Engine unreachable", error=str(e))
            components["ml_engine"] = "unavailable"
    else:
        components["ml_engine"] = "decoupled"

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
@router.get("/live")
async def liveness_probe():
    """Liveness probe: returns 200 when the process is alive."""
    return {"status": "alive"}


@router.get("/health/ready")
@router.get("/ready")
@router.get("/api/v1/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe: returns 200 when database connectivity is verified,
    503 Service Unavailable when the database is not reachable so that
    load balancers and Kubernetes correctly stop routing traffic.
    """
    try:
        await db.execute(text("SELECT 1;"))
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness probe: database not reachable", error=str(e))
        # Return 503 — do NOT expose internal error string to callers
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready"},
        )

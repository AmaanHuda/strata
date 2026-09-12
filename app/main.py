"""
FastAPI application entrypoint for SIH 2026 PS26011.
3D ULPIN Generation & Vertical Property Mapping System Backend.
"""
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    auth,
    buildings,
    datasets,
    floors,
    health,
    jobs,
    parcels,
    search,
    ulpin,
    units,
    validation,
)
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import logger
from app.schemas.common import ApiResponse, ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "3D-Mapping Backend starting up",
        environment=settings.ENVIRONMENT,
        ml_engine_url=settings.ML_ENGINE_URL,
    )
    yield
    logger.info("3D-Mapping Backend shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    description=(
        "SIH 2026 PS26011 Backend: 3D Cadastral Mapping, ULPIN Generation, "
        "and Vertical Property Management. Privacy-preserving architecture with PostGIS spatial integration."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS Middleware
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID & Timing Middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()
    
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = f"{duration_ms}ms"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# Exception Handlers (Standardized Error Response Envelope)
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        ).model_dump(by_alias=True),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ApiResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message="Request validation error",
                details={"errors": errors},
            ),
        ).model_dump(by_alias=True),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        401: ErrorCode.AUTHENTICATION_ERROR,
        403: ErrorCode.AUTHORIZATION_ERROR,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
    }
    err_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code=err_code,
                message=str(exc.detail),
            ),
        ).model_dump(by_alias=True),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ApiResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code=ErrorCode.INTERNAL_ERROR,
                message="An unexpected server error occurred. Check system logs.",
            ),
        ).model_dump(by_alias=True),
    )


# API Routers
api_v1 = "/api/v1"
app.include_router(health.router)
app.include_router(auth.router, prefix=api_v1)
app.include_router(parcels.router, prefix=api_v1)
app.include_router(buildings.router, prefix=api_v1)
app.include_router(floors.router, prefix=api_v1)
app.include_router(units.router, prefix=api_v1)
app.include_router(ulpin.router, prefix=api_v1)
app.include_router(search.router, prefix=api_v1)
app.include_router(validation.router, prefix=api_v1)
app.include_router(datasets.router, prefix=api_v1)
app.include_router(jobs.router, prefix=api_v1)

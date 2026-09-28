"""
Central settings for SIH 2026 PS26011 Backend.
Loaded from environment variables and .env file.

Canonical variable names (one name per setting):
- SECRET_KEY          → JWT signing secret
- ML_ENGINE_URL       → ML Engine base URL
- ML_ENGINE_TIMEOUT   → ML Engine HTTP timeout (seconds)
- ENVIRONMENT         → Runtime environment (development/production)
- CORS_ORIGINS        → Comma-separated allowed CORS origins
"""
from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application
    PROJECT_NAME: str = "3D-Mapping-Backend"
    APP_NAME: str = "3D-Mapping-Backend"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ulpin_db"
    SYNC_DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/ulpin_db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("SYNC_DATABASE_URL", mode="before")
    @classmethod
    def assemble_sync_db_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            elif v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql+asyncpg://", "postgresql://", 1)
        return v

    # JWT & Security
    # Canonical JWT secret. MUST be overridden via SECRET_KEY env var in production.
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARS"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # CORS — canonical: CORS_ORIGINS
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,https://strataaa.netlify.app"
    )

    # External ML Engine Contract — canonical: ML_ENGINE_URL, ML_ENGINE_TIMEOUT
    ML_ENGINE_URL: str = "http://localhost:8001"
    ML_ENGINE_API_KEY: str = ""
    ML_ENGINE_TIMEOUT: int = 120
    ML_ENGINE_VERSION: str = "v2.0"
    ML_ENGINE_ENABLED: bool = False

    # Storage & Uploads
    STORAGE_PATH: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104857600  # 100 MB

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Spatial References
    DEFAULT_CRS: str = "EPSG:4326"
    # EPSG:7755 = GCS India 2014 — used for metric area/distance calculations
    INDIA_CRS: str = "EPSG:7755"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 200

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

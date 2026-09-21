# STRATA 3D-Mapping Backend

**SIH 2026 PS26011 — 3D ULPIN Generation & Vertical Property Mapping System**

Production-ready FastAPI backend for managing 3D cadastral data, ULPIN generation, spatial queries, and async batch processing.

> See [`BACKEND_INTEGRATION_GUIDE.md`](./BACKEND_INTEGRATION_GUIDE.md) for the full API reference for frontend and ML Engine teams.

---

## Architecture

```
Frontend (React/Cesium/Three.js)
    │
    ▼ REST API
FastAPI Backend  ← This Repository
    │
    ├── PostgreSQL 16 + PostGIS 3.4   (spatial data + GiST indexes)
    ├── Redis                          (async task queue: strata:jobs:queue)
    ├── Background Worker             (async event loop, no Celery)
    └── ML Engine (decoupled)  ──────→ 3D-Mapping-ml-engine (future integration)
```

**Layer Pattern:** `Routes → Schemas → Services → Repositories → DB`

**Property Hierarchy:**
```
Parcel (land plot)
  └── Building
        └── Floor
              └── Unit (apartment / shop / office)
```

Each entity can receive a **ULPIN** (Unique Land Parcel Identification Number).

> ⚠️ **Candidate ULPINs** are AI/computational outputs only. They do NOT constitute
> authoritative legal cadastral records until verified by a competent authority.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI 0.115+ (async) |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| ORM | SQLAlchemy 2.0 (async) + GeoAlchemy2 |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Task Queue | Redis (async `blpop` consumer, no Celery) |
| Geometry | Shapely + GeoAlchemy2 + PostGIS |
| ML Integration | HTTPX async client (decoupled, future phase) |
| Testing | pytest-asyncio + HTTPX AsyncClient |
| Containerization | Docker + Docker Compose |

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
git clone https://github.com/Rehan-roid/3D-Mapping-Backend.git
cd 3D-Mapping-Backend
cp .env.example .env
# Edit .env: set SECRET_KEY, DATABASE_URL

# 2. Start all services (PostgreSQL/PostGIS, Redis, Backend, Worker)
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. API is live at http://localhost:8000
#    Swagger UI:  http://localhost:8000/docs
#    OpenAPI JSON: http://localhost:8000/api/v1/openapi.json
```

---

## Quick Start (Local Dev)

```bash
# Prerequisites: Python 3.12+, PostgreSQL + PostGIS, Redis

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt

cp .env.example .env
# Fill in DATABASE_URL, REDIS_URL, SECRET_KEY

alembic upgrade head
uvicorn app.main:app --reload --port 8000

# In another terminal - start background worker:
python -m app.workers.worker
```

---

## API Endpoints (v2.0.0)

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login → JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user profile |

### Spatial Queries
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/spatial/bbox` | Viewport bounding box search |
| GET | `/api/v1/spatial/nearby` | Radius search (metric, PostGIS geography) |
| POST | `/api/v1/spatial/query` | Polygon intersection/contains/within query |
| GET | `/api/v1/spatial/search` | Point-in-polygon lookup |

### Parcels
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/parcels/` | List parcels (paginated) |
| POST | `/api/v1/parcels/` | Create parcel |
| GET | `/api/v1/parcels/{id}` | Get parcel |
| PUT | `/api/v1/parcels/{id}` | Update parcel |
| DELETE | `/api/v1/parcels/{id}` | Delete parcel |

### Buildings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/buildings/` | List buildings |
| POST | `/api/v1/buildings/` | Create building |
| GET | `/api/v1/buildings/{id}` | Get building |
| GET | `/api/v1/buildings/{id}/structure` | Full hierarchy (building→floors→units) |
| GET | `/api/v1/buildings/{id}/geometry` | 2D/3D geometry + centroid |
| GET | `/api/v1/buildings/{id}/geojson` | GeoJSON footprint |
| POST | `/api/v1/buildings/{id}/estimate-height` | Trigger ML height estimation |

### Floors & Units
| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/floors/` | List/Create floors |
| GET/PUT | `/api/v1/floors/{id}` | Get/Update floor |
| GET/POST | `/api/v1/units/` | List/Create units |
| GET/PUT | `/api/v1/units/{id}` | Get/Update unit |

### ULPIN
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ulpin/generate` | Generate candidate ULPIN |
| POST | `/api/v1/ulpin/validate` | Validate ULPIN format + status |
| GET | `/api/v1/ulpin/{ulpin}` | Lookup ULPIN by string |

### Validation Services
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/validation/geometry` | 2D/3D geometry validation |
| POST | `/api/v1/validation/topology` | Topological relationship validation |
| POST | `/api/v1/validation/cadastral` | Full cadastral entity integrity check |

### Async Jobs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/jobs` | Submit async job |
| GET | `/api/v1/jobs` | List jobs (filtered) |
| GET | `/api/v1/jobs/{id}` | Get job status + result |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel queued/processing job |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |
| GET | `/api/v1/health` | Full system health |

Full interactive docs at: **`http://localhost:8000/docs`**

---

## RBAC Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access + user management |
| `surveyor` | Create/edit parcels, buildings, floors, units; generate ULPIN; submit jobs |
| `analyst` | Read all; validate; generate ULPIN; submit jobs |
| `viewer` | Read-only |

---

## Database Tables

| Table | Description |
|-------|-------------|
| `users` | Auth + RBAC |
| `parcels` | Land parcels with 2D boundary geometry (PostGIS) |
| `buildings` | Buildings on parcels with footprint + height |
| `floors` | Floors within buildings (elevation, area) |
| `units` | Units within floors (type, occupancy) |
| `ulpin_records` | ULPIN assignments + status lifecycle |
| `async_jobs` | Job queue tracking + results |
| `dataset_registry` | Ingested dataset metadata |
| `provenance_records` | Data lineage |
| `audit_logs` | Immutable change log |

PostGIS GiST spatial indexes are created on `parcels.boundary` and `buildings.footprint_2d`.

---

## Background Worker

The worker is a standalone async event loop process (no Celery dependency):

```bash
python -m app.workers.worker
```

**Execution flow:**
1. Listens on Redis list `strata:jobs:queue` via `blpop` (3s timeout)
2. Falls back to DB polling for QUEUED jobs if Redis is unavailable
3. Executes real job types: `batch_validation`, `cadastral_audit`, `ulpin_batch`
4. Retries up to `max_retries` on failure; marks `FAILED` after exhaustion

---

## Running Tests

```bash
# All tests (25 unit + spatial + contract + integration)
python -m pytest tests/ -v

# By category
python -m pytest tests/unit/           # Unit tests (no DB)
python -m pytest tests/spatial/        # Geometry + topology service tests
python -m pytest tests/contract/       # ML/ingestion contract validation
python -m pytest tests/integration/    # API endpoint integration tests

# With coverage
python -m pytest --cov=app --cov-report=html
```

---

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async URL | required |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (≥32 chars) | required |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `ML_ENGINE_ENABLED` | Enable ML Engine integration | `false` |
| `ML_ENGINE_URL` | ML Engine base URL | `http://ml-engine:8001` |
| `ENVIRONMENT` | `development` / `production` | `development` |

---

## PostGIS Requirements

- PostgreSQL 16+ with PostGIS 3.4+ extension
- Enable extension: `CREATE EXTENSION IF NOT EXISTS postgis;`
- Docker image used: `postgis/postgis:16-3.4`

---

## ML Engine Integration (Future Phase)

The ML Engine is fully decoupled. Set `ML_ENGINE_ENABLED=true` and configure `ML_ENGINE_URL` to enable:
- Height estimation: `POST /api/v1/buildings/{id}/estimate-height`
- Floor count estimation (job type `height_estimation`)

Contracts are defined in `app/integrations/ml_engine/contracts.py`.

---

## Limitations & Disclaimers

1. **Candidate ULPINs** are computational outputs — not official government ULPINs.
2. Official ULPIN assignment requires external authority validation (out of backend scope).
3. Spatial area calculations in EPSG:4326 use degree-based approximations in Shapely. PostGIS geography functions are used for metric distance queries.
4. Production deployments should configure proper SSL, WAF, and rate limiting.

---

*STRATA Backend v2.0.0 — SIH 2026 PS26011*


---

## Architecture

```
Frontend (React/Cesium)
    │
    ▼
FastAPI Backend  ← This Repository
    │
    ├── PostgreSQL + PostGIS  (spatial data)
    ├── Redis + Celery        (async jobs)
    └── ML Engine Adapter ──→ 3D-Mapping-ml-engine (separate repo)
```

**Pattern**: Routes → Schemas → Services → Repositories → DB  
with Services → ML Adapter for external ML calls.

---

## Property Hierarchy

```
Parcel (land plot)
  └── Building
        └── Floor
              └── Unit (apartment/shop/office)
```

Each entity can receive a **ULPIN** (Unique Land Parcel Identification Number).

> ⚠️ AI-derived vertical unit ULPINs are analytical/candidate outputs only.
> They do NOT constitute authoritative legal cadastral records until verified
> by a competent authority.

---

## Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI 0.115 |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| ORM | SQLAlchemy 2.0 (async) + GeoAlchemy2 |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Task Queue | Celery + Redis |
| ML Integration | HTTPX async client with retry |
| Testing | pytest-asyncio + HTTPX |
| Containerization | Docker + Docker Compose |

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
git clone <your-repo-url> 3D-Mapping-backend
cd 3D-Mapping-backend
cp .env.example .env
# Edit .env: set SECRET_KEY, DATABASE_URL

# 2. Start all services
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Create superadmin
docker compose exec backend python scripts/create_superadmin.py

# 5. API is live at http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

---

## Quick Start (Local Dev)

```bash
# Prerequisites: Python 3.12+, PostgreSQL + PostGIS, Redis

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Fill in DATABASE_URL, SECRET_KEY

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /api/v1/auth/register | Register user |
| POST | /api/v1/auth/login | Login → JWT tokens |
| POST | /api/v1/parcels | Create parcel |
| GET | /api/v1/parcels | List parcels |
| GET | /api/v1/parcels/{id} | Get parcel |
| GET | /api/v1/parcels/spatial/bbox | Spatial bbox search |
| GET | /api/v1/parcels/spatial/radius | Spatial radius search |
| POST | /api/v1/buildings | Create building |
| GET | /api/v1/buildings/{id} | Get building |
| POST | /api/v1/buildings/{id}/ml/height | Trigger ML height estimation |
| POST | /api/v1/buildings/{id}/ml/floors | Trigger ML floor count |
| POST | /api/v1/floors | Create floor |
| GET | /api/v1/floors/{id} | Get floor |
| POST | /api/v1/units | Create unit |
| GET | /api/v1/units/{id} | Get unit |
| POST | /api/v1/ulpin/generate | Generate ULPIN |
| GET | /api/v1/ulpin/lookup/{ulpin} | Lookup ULPIN |
| POST | /api/v1/jobs | Submit async job |
| GET | /api/v1/jobs/{id} | Get job status |

Full interactive docs at `/docs`.

---

## RBAC Roles

| Role | Permissions |
|------|-------------|
| admin | Full access |
| surveyor | Create/edit parcels, buildings, floors, units; generate ULPIN |
| analyst | Read all data; trigger ML jobs |
| viewer | Read-only |

---

## Database Tables

| Table | Description |
|-------|-------------|
| users | Auth + RBAC |
| parcels | Land parcels with 2D/3D geometry |
| buildings | Buildings on parcels |
| floors | Floors within buildings |
| units | Units within floors |
| ulpin_records | ULPIN assignments |
| async_jobs | Job queue tracking |
| dataset_registry | Dataset metadata |
| provenance_records | Data lineage |
| audit_logs | Immutable change log |

---

## ML Integration

The backend connects to the **3D-Mapping-ml-engine** via HTTP adapter:

```
Backend ML Adapter → POST /v1/height/estimate
                   → POST /v1/buildings/extract
                   → POST /v1/floors/count
```

Configure `ML_ENGINE_BASE_URL` in `.env`.
The contracts are defined in `app/integrations/ml_engine/contracts.py`.

---

## Running Tests

```bash
pytest tests/unit/           # Unit tests (no DB needed)
pytest tests/contract/       # Contract/schema tests
pytest tests/integration/    # Integration tests (needs running app)
pytest --cov=app             # Full coverage
```

---

## Environment Variables

See `.env.example` for all variables. Critical ones:

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing key (min 32 chars, random)
- `ML_ENGINE_BASE_URL` — URL of the ML engine service

---

## Limitations & Disclaimers

1. AI/ML-derived height, floor count, and unit segmentation are **analytical estimates** only.
2. ULPIN generation uses a deterministic hash — **not the official government ULPIN format**.
3. Authoritative cadastral records require official survey and legal publication.
4. PostGIS spatial indexes must be created via Alembic migration for production performance.

---

## Connecting to Frontend & ML Engine

```
3D-Mapping-ml-engine  ←─ HTTP ─→  3D-Mapping-backend  ←─ REST API ─→  Frontend
```

- ML Engine: set `ML_ENGINE_BASE_URL` to the running ml-engine address
- Frontend: point all API calls to `http://<backend-host>:8000/api/v1/`
- CORS: add frontend origin to `ALLOWED_ORIGINS` in `.env`

---

## Backup & Recovery

```bash
# Backup
pg_dump -U postgres ulpin_db > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres ulpin_db < backup_YYYYMMDD.sql
```

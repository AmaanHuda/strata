> **ARCHIVED — superseded by the top-level [`README.md`](../README.md).**
>
> This file is kept only so no reference material is lost. It is two earlier
> README drafts concatenated, so several sections appear twice and some numbers
> are stale (e.g. "86 backend tests" — the suite is now 212). Do not use it as
> the source of truth; see `README.md` and [`ARCHITECTURE.md`](./ARCHITECTURE.md).

# STRATA 3D-Mapping — Monorepo (legacy README)

**SIH 2026 PS26011 — 3D ULPIN Generation & Vertical Property Mapping System**

This repository contains the **Frontend** (React + Mapbox GL JS / Three.js), the **Backend** (FastAPI), and the **ML Engine** (FastAPI) as unified modules in a clean fullstack monorepo.

> See [`BACKEND_INTEGRATION_GUIDE.md`](./BACKEND_INTEGRATION_GUIDE.md) for the full API reference.

---

## Repository Structure

```
3D-MAPPING/
├── frontend/               ← Frontend (React 19 + TypeScript + Mapbox GL JS + Three.js)
│   ├── src/                  Application source
│   │   ├── api/                Backend REST client (Axios, JWT auth)
│   │   ├── components/         UI, Map, Panels, 3D Scenes
│   │   ├── state/              Zustand store (real backend entity state)
│   │   ├── three/              Mapbox 3D terrain space & feature parsing
│   │   └── ui/                 Main view & modal workflows
│   ├── Dockerfile            Multi-stage production build (Nginx)
│   ├── package.json
│   └── vite.config.ts
├── app/                    ← Backend (FastAPI + SQLAlchemy + PostGIS)
│   ├── api/                  API routes
│   ├── core/                 Config, auth, errors, logging
│   ├── db/                   ORM models, repositories, migrations
│   ├── integrations/
│   │   └── ml_engine/        Backend ↔ ML Engine boundary
│   │       ├── client.py       Async HTTP client (HTTPX)
│   │       ├── contracts.py    Pydantic request/response schemas
│   │       ├── adapter.py      Orchestrates ML call + DB persist
│   │       └── mapper.py       Maps ML output → ORM entities
│   ├── services/
│   ├── schemas/
│   └── workers/
├── ml-engine/              ← ML Engine (FastAPI, separate service)
│   ├── src/                  ML source modules
│   │   ├── server.py           FastAPI app (port 8001)
│   │   ├── inference/          MLEnginePipeline orchestrator
│   │   ├── building_extraction/
│   │   ├── height/
│   │   ├── floors/
│   │   ├── units/
│   │   ├── reconstruction/
│   │   ├── fusion/
│   │   ├── confidence/
│   │   ├── geospatial/
│   │   ├── change_detection/
│   │   ├── validation/
│   │   └── preprocessing/
│   ├── models/checkpoints/   building_extraction_unet — real trained checkpoint (KAGGLE_BENCHMARK provenance)
│   ├── schemas/              ml_output_contract.json (v1.0.0)
│   ├── scripts/              Training + benchmark + validation utilities
│   │   └── train_building_extraction.py   Reproducible U-Net training harness
│   ├── tests/                100 unit tests (torch env) / 99 (torch-free)
│   ├── docs/                 ML specification & audit documents
│   ├── pyproject.toml
│   └── Dockerfile
├── alembic/                ← DB migrations (backend)
├── tests/                  ← Backend tests (86 passing)
├── docker-compose.yml      ← Fullstack compose (db, redis, backend, worker, ml-engine, frontend)
├── .env.example            ← Backend environment template
├── .env                    ← Backend active environment
└── README.md
```

> **Note on naming:** The backend application module is `app/` (not `backend/`).
> Renaming it would break all Python imports, Alembic config, and Docker paths.
> The README refers to it as "Backend" conceptually.

---

## Service Boundary

```
Frontend (React / Cesium / Three.js)
    │
    ▼  REST API (port 8000)
Backend / FastAPI  ──────────────────────────────── app/
    │  app/integrations/ml_engine/client.py
    │  ML_ENGINE_URL=http://ml-engine:8001
    ▼  HTTP POST /process/parcel
ML Engine / FastAPI  ────────────────────────────── ml-engine/src/server.py
    │
    ▼  MLEnginePipeline.process_parcel()
ML Output Contract v1.0.0  ──────────────────────── ml-engine/schemas/ml_output_contract.json
    │
    ▼  MLDataMapper.contract_v1_to_entities()
Backend validation + PostGIS persistence
```

**Key rule:** `ML_ENGINE_ENABLED=false` by default.
The backend raises `MLEngineNotAvailableError` — it never returns fabricated predictions.
Set `ML_ENGINE_ENABLED=true` and start the ml-engine service to activate real inference.

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
| ML Integration | HTTPX async client (decoupled, activate via env) |
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

## ML Engine Integration

The ML Engine is integrated as `ml-engine/` in this monorepo and runs as a separate FastAPI service.

**ML Engine API (port 8001):**
- `GET  /health` — liveness probe
- `POST /process/parcel` — end-to-end ML inference (`MLEnginePipeline.process_parcel`)
- `POST /predict/height` — height estimation
- `POST /predict/floors` — floor count estimation
- `POST /generate/vertical-units` — vertical unit segmentation

**Activating the ML Engine:**
```bash
# In .env:
ML_ENGINE_ENABLED=true
ML_ENGINE_URL=http://ml-engine:8001   # Docker Compose internal name

# Start all services including ml-engine:
docker compose up -d

# Or run ML Engine standalone (local dev):
cd ml-engine
uvicorn src.server:app --host 0.0.0.0 --port 8001 --reload
```

**ML Engine tests (no DB needed):**
```bash
cd ml-engine
pytest tests/unit/ -v
```

**When `ML_ENGINE_ENABLED=false` (default):** the backend raises `MLEngineNotAvailableError` — 
it never fabricates synthetic predictions.

Contracts: `app/integrations/ml_engine/contracts.py`
ML Output Schema: `ml-engine/schemas/ml_output_contract.json`

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

### Trained model status (2026-09-24)

- **Building-footprint extraction**: a real torch U-Net (1.09M params) has been
  trained from scratch on SVAMITVA drone tiles (Kaggle community mirror —
  `KAGGLE_BENCHMARK` provenance; government-**origin** imagery, community
  annotations, **not** Survey of India ground truth). Honest held-out metrics:
  **IoU 0.241 / Dice 0.322** on a leakage-resistant spatial split.
  Full audit: [`ml-engine/MODEL_STATUS.md`](./ml-engine/MODEL_STATUS.md),
  [`ml-engine/DATASET_STATUS.md`](./ml-engine/DATASET_STATUS.md), and the
  per-dataset usage map [`ml-engine/datasets/DATASET_CATALOG.md`](./ml-engine/datasets/DATASET_CATALOG.md).
- **Height / floors / units / cadastral**: no open government-labelled data exists —
  these remain **DATA_BLOCKED** and are served by the algorithmic baselines only.
- No ML endpoint fabricates values when a model or engine is unavailable; failures
  surface as errors, and every checkpoint must carry provenance metadata to load.
- Persistence is verified against real **PostgreSQL 16.4 + PostGIS 3.6.2**
  end-to-end (parcel → building → floor → geometry), not just mocked tests.

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

1. Building-footprint extraction uses a **trained U-Net with KAGGLE_BENCHMARK
   provenance** (community-annotated SVAMITVA mirror) — it is a benchmark
   demonstration, not government-compliant ground truth.
2. AI/ML-derived height, floor count, and unit segmentation are **analytical estimates**
   only (no open labelled data exists to train them; see ml-engine/DATASET_STATUS.md).
3. ULPIN generation uses a deterministic hash — **not the official government ULPIN format**.
4. Authoritative cadastral records require official survey and legal publication.
5. PostGIS spatial indexes must be created via Alembic migration for production performance.

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

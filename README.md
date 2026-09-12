# 3D-Mapping-backend

**SIH 2026 PS26011 — 3D ULPIN Generation & Vertical Property Mapping**

Backend API server for managing 3D cadastral data, ULPIN generation, and integration with the ML engine.

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

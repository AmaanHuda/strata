# STRATA Backend Integration Guide
## SIH 2026 PS26011 — 3D ULPIN Generation & Vertical Property Mapping System

> **Version:** 2.0.0 | **Base URL:** `http://localhost:8000`

This guide is the authoritative reference for frontend developers and future ML Engine integration. It documents every API contract, authentication flow, spatial query payload, building hierarchy response, ULPIN lifecycle, validation services, and async job flow.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Authentication](#2-authentication)
3. [Spatial Query APIs](#3-spatial-query-apis)
4. [Parcel APIs](#4-parcel-apis)
5. [Building Hierarchy APIs](#5-building-hierarchy-apis)
6. [ULPIN Lifecycle APIs](#6-ulpin-lifecycle-apis)
7. [Validation Service APIs](#7-validation-service-apis)
8. [Async Job System](#8-async-job-system)
9. [Health & Readiness Probes](#9-health--readiness-probes)
10. [Error Response Envelope](#10-error-response-envelope)
11. [ML Engine Integration (Decoupled)](#11-ml-engine-integration-decoupled)
12. [Environment Configuration](#12-environment-configuration)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      STRATA 3D-Mapping Backend                       │
│                                                                      │
│  FastAPI (async) ─── SQLAlchemy 2.0 (async) ─── PostgreSQL/PostGIS  │
│                │                                                      │
│                ├── Redis (async task queue: strata:jobs:queue)       │
│                ├── Background Worker (worker.py async event loop)    │
│                └── ML Engine (decoupled, future integration)         │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Boundaries:**
- **Frontend** consumes REST API — no direct DB access.
- **ML Engine** is fully decoupled — integration enabled via `ML_ENGINE_ENABLED=true` env.
- **All spatial distances** are calculated using PostGIS geography (meters), not EPSG:4326 degrees.
- **Candidate ULPINs** are never promoted to government-official status by this backend.

---

## 2. Authentication

All endpoints except `/health`, `/ready`, and `/docs` require a Bearer JWT token.

### Register
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe",
  "role": "viewer"   // viewer | analyst | surveyor | admin
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "role": "viewer",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Using the Token
```http
Authorization: Bearer <access_token>
```

### Role Hierarchy
| Role       | Permissions                                               |
|------------|-----------------------------------------------------------|
| `viewer`   | Read-only: parcels, buildings, floors, units, ULPIN lookup |
| `analyst`  | viewer + validate, generate ULPINs, submit jobs           |
| `surveyor` | analyst + create/update parcels, buildings, floors, units |
| `admin`    | All permissions + user management, delete operations      |

---

## 3. Spatial Query APIs

Base: `/api/v1/spatial/`

### 3.1 Viewport Bounding Box Search
```http
GET /api/v1/spatial/bbox?min_lon=77.0&min_lat=28.0&max_lon=77.5&max_lat=28.5&layer=all&limit=100
Authorization: Bearer <token>
```

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `min_lon` | float | ✅ | West boundary longitude |
| `min_lat` | float | ✅ | South boundary latitude |
| `max_lon` | float | ✅ | East boundary longitude |
| `max_lat` | float | ✅ | North boundary latitude |
| `layer` | string | ❌ | `parcel`, `building`, or `all` (default: `all`) |
| `simplify_tolerance` | float | ❌ | WGS84 degree tolerance for geometry simplification |
| `limit` | int | ❌ | Max results (default: 200, max: 1000) |

**Response:**
```json
{
  "success": true,
  "data": {
    "parcels": [
      {
        "id": "uuid",
        "survey_number": "DL-2024-001",
        "geometry": { "type": "Polygon", "coordinates": [...] },
        "centroid": { "lat": 28.25, "lon": 77.25 },
        "area_sqm": 5000.0,
        "candidate_ulpin": "IND-DL-2024-001-0000",
        "validation_status": "VALIDATED"
      }
    ],
    "buildings": [
      {
        "id": "uuid",
        "parcel_id": "uuid",
        "address": "123 Main St",
        "height_m": 45.0,
        "floor_count": 12,
        "centroid": { "lat": 28.25, "lon": 77.25 },
        "footprint_geojson": { "type": "Polygon", "coordinates": [...] }
      }
    ],
    "bbox": [77.0, 28.0, 77.5, 28.5],
    "total_count": 42
  }
}
```

### 3.2 Nearby Search (Metric Radius)
```http
GET /api/v1/spatial/nearby?lat=28.6139&lon=77.2090&radius_m=500&limit=20
Authorization: Bearer <token>
```

> ⚠️ **Note:** Distance is calculated using PostGIS `ST_DWithin` on geography (spheroid), giving true metric distances, **not** Euclidean degree-based approximations.

**Response:**
```json
{
  "success": true,
  "data": {
    "center": { "lat": 28.6139, "lon": 77.2090 },
    "radius_m": 500,
    "results": [
      {
        "entity_type": "building",
        "id": "uuid",
        "distance_m": 123.45,
        "centroid": { "lat": 28.614, "lon": 77.210 },
        "address": "456 Near Street"
      }
    ],
    "count": 5
  }
}
```

### 3.3 Polygon Intersection Query
```http
POST /api/v1/spatial/query
Authorization: Bearer <token>
Content-Type: application/json

{
  "geometry_wkt": "POLYGON((77.0 28.0, 78.0 28.0, 78.0 29.0, 77.0 29.0, 77.0 28.0))",
  "relationship": "intersects",
  "layer": "parcel",
  "limit": 50
}
```

**Supported `relationship` values:** `intersects`, `contains`, `within`

### 3.4 Point-in-Polygon Lookup
```http
GET /api/v1/spatial/search?lat=28.6139&lon=77.2090
Authorization: Bearer <token>
```

**Response:** `200 OK` (or `404` if no parcel at coordinates)
```json
{
  "success": true,
  "data": {
    "lat": 28.6139,
    "lon": 77.2090,
    "parcel": {
      "id": "uuid",
      "survey_number": "DL-2024-001",
      "area_sqm": 5000.0,
      "candidate_ulpin": "IND-DL-2024-001-0000",
      "official_ulpin": null
    },
    "buildings": [
      {
        "id": "uuid",
        "floor_count": 12,
        "height_m": 45.0,
        "candidate_ulpin": "IND-DL-2024-001-B01-0000"
      }
    ]
  }
}
```

---

## 4. Parcel APIs

Base: `/api/v1/parcels/`

### List Parcels
```http
GET /api/v1/parcels/?page=1&page_size=20&district=Delhi
Authorization: Bearer <token>
```

### Get Parcel
```http
GET /api/v1/parcels/{parcel_id}
Authorization: Bearer <token>
```

### Create Parcel (surveyor/admin)
```http
POST /api/v1/parcels/
Authorization: Bearer <token>
Content-Type: application/json

{
  "survey_number": "DL-2024-001",
  "district": "New Delhi",
  "state_code": "DL",
  "boundary_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
  "area_sqm": 5000.0,
  "land_use": "residential",
  "source_crs": "EPSG:4326"
}
```

---

## 5. Building Hierarchy APIs

Base: `/api/v1/buildings/`

### 5.1 Building Complete Structure
Returns the entire building hierarchy in a single optimized query.

```http
GET /api/v1/buildings/{building_id}/structure
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "building_id": "uuid",
    "parcel_id": "uuid",
    "address": "Tower A, Connaught Place",
    "height_m": 45.0,
    "floor_count": 12,
    "centroid": { "lat": 28.6139, "lon": 77.2090 },
    "candidate_ulpin": "IND-DL-0-0-B01-0000",
    "official_ulpin": null,
    "validation_status": "VALIDATED",
    "floors": [
      {
        "floor_id": "uuid",
        "floor_number": 1,
        "label": "Ground Floor",
        "height_above_ground_m": 0.0,
        "ceiling_height_m": 3.5,
        "floor_area_sqm": 450.0,
        "candidate_ulpin": "IND-DL-0-0-B01-F01-0000",
        "status": "VALIDATED",
        "units": [
          {
            "unit_id": "uuid",
            "unit_number": "101",
            "unit_type": "office",
            "area_sqm": 75.0,
            "is_occupied": true,
            "candidate_ulpin": "IND-DL-0-0-B01-F01-U01-0000",
            "status": "CANDIDATE"
          }
        ]
      }
    ]
  }
}
```

### 5.2 Building Geometry
```http
GET /api/v1/buildings/{building_id}/geometry
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "building_id": "uuid",
    "parcel_id": "uuid",
    "centroid": { "lat": 28.6139, "lon": 77.2090 },
    "height_m": 45.0,
    "elevation_m": null,
    "footprint_wkt": "POLYGON((...))",
    "footprint_geojson": { "type": "Polygon", "coordinates": [...] },
    "bounds": [77.20, 28.61, 77.21, 28.62],
    "geometry_3d_lod2": null,
    "source_crs": "EPSG:4326",
    "processing_crs": "EPSG:4326"
  }
}
```

### 5.3 Building GeoJSON
```http
GET /api/v1/buildings/{building_id}/geojson
Authorization: Bearer <token>
```

---

## 6. ULPIN Lifecycle APIs

Base: `/api/v1/ulpin/`

### ULPIN Status States
```
CANDIDATE → VALIDATED → OFFICIAL
```
> ⚠️ **OFFICIAL** status can only be assigned by an external government authority. This backend never auto-promotes ULPINs to OFFICIAL status.

### 6.1 Generate Candidate ULPIN (analyst/surveyor/admin)
```http
POST /api/v1/ulpin/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "entity_type": "parcel",      // parcel | building | floor | unit
  "parcel_id": "uuid",
  "state_code": "DL",
  "district_code": "001",
  "survey_number": "SV-2024-001",
  "generation_method": "survey"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "candidate_ulpin": "IND-DL-001-SV2024001-0000",
    "official_ulpin": null,
    "status": "CANDIDATE",
    "entity_type": "parcel",
    "is_authoritative": false,
    "legal_disclaimer": "This is a CANDIDATE ULPIN generated computationally...",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "meta": { "message": "Candidate ULPIN generated" }
}
```

### 6.2 Validate ULPIN
```http
POST /api/v1/ulpin/validate
Authorization: Bearer <token>
Content-Type: application/json

{
  "ulpin": "IND-DL-001-SV2024001-0000",
  "entity_id": "uuid",         // optional: check entity linkage
  "entity_type": "parcel"      // optional
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "ulpin": "IND-DL-001-SV2024001-0000",
    "is_valid": true,
    "status": "CANDIDATE",
    "format_valid": true,
    "registry_found": true,
    "entity_linked": true,
    "is_official": false,
    "errors": [],
    "warnings": ["ULPIN is CANDIDATE status; not yet government-validated"],
    "legal_disclaimer": "Official ULPIN assignment requires government authority verification."
  }
}
```

### 6.3 Lookup ULPIN
```http
GET /api/v1/ulpin/{ulpin_string}
Authorization: Bearer <token>
```

---

## 7. Validation Service APIs

Base: `/api/v1/validation/`

### 7.1 Geometry Validation
```http
POST /api/v1/validation/geometry
Authorization: Bearer <token>
Content-Type: application/json

{
  "geometry_wkt": "POLYGON((77.2 28.6, 77.3 28.6, 77.3 28.7, 77.2 28.7, 77.2 28.6))",
  "geometry_geojson": null,
  "crs": "EPSG:4326",
  "elevation_min_m": 0.0,
  "elevation_max_m": 45.0,
  "floor_number": null,
  "height_above_ground_m": null,
  "ceiling_height_m": null
}
```

**Validation Checks:**
- CRS validity (EPSG:4326, EPSG:32643, EPSG:32644 supported)
- WKT/GeoJSON syntax parsing
- Ring closure (linear ring must close)
- Self-intersection detection (Shapely validity)
- Empty geometry detection
- Polygon/MultiPolygon geometry type enforcement
- Non-zero metric area (using Shapely area heuristic)
- Vertex count warning (>500 vertices)
- 3D: min elevation ≤ max elevation
- 3D: non-negative heights
- 3D: floor_number vs height_above_ground consistency

**Response:**
```json
{
  "success": true,
  "data": {
    "is_valid": true,
    "status": "VALID",
    "error_count": 0,
    "warning_count": 0,
    "checks": [
      { "check_name": "crs_check", "passed": true, "message": "CRS valid" },
      { "check_name": "ring_closure", "passed": true, "message": "Ring is closed" },
      { "check_name": "self_intersection", "passed": true, "message": "No self-intersections" }
    ],
    "errors": [],
    "warnings": [],
    "details": {
      "geometry_type": "Polygon",
      "vertex_count": 5,
      "area_degrees_sq": 0.01,
      "bounds": [77.2, 28.6, 77.3, 28.7]
    }
  }
}
```

### 7.2 Topology Validation
```http
POST /api/v1/validation/topology
Authorization: Bearer <token>
Content-Type: application/json

{
  "parcel_wkt": "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))",
  "building_wkt": "POLYGON((2 2, 8 2, 8 8, 2 8, 2 2))",
  "adjacent_building_wkts": [],
  "floor_wkts": []
}
```

**Topology Checks:**
- `building_within_parcel`: Building footprint must be within or touching parcel boundary
- `building_no_overlap`: Adjacent buildings must not overlap
- `floor_continuity`: Floor footprints must align vertically

**Response:**
```json
{
  "success": true,
  "data": {
    "is_valid": true,
    "status": "VALID",
    "checks": [
      {
        "check_name": "building_within_parcel",
        "passed": true,
        "message": "Building is within parcel boundary"
      }
    ],
    "errors": [],
    "warnings": []
  }
}
```

### 7.3 Cadastral Validation (Entity Integrity Check)
```http
POST /api/v1/validation/cadastral
Authorization: Bearer <token>
Content-Type: application/json

{
  "parcel_id": "uuid",
  "building_id": null,
  "scope": "full"
}
```

---

## 8. Async Job System

Base: `/api/v1/jobs/`

### Supported Job Types

| `job_type` | Description | Roles |
|------------|-------------|-------|
| `batch_validation` | Real geometry+topology validation on DB records | analyst, surveyor, admin |
| `cadastral_audit` | Scans for orphaned entities, missing geometries | analyst, surveyor, admin |
| `ulpin_batch` | Generates candidate ULPINs for unassigned parcels | surveyor, admin |
| `height_estimation` | ML height estimation (requires ML_ENGINE_ENABLED=true) | admin |

### 8.1 Submit Job
```http
POST /api/v1/jobs
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_type": "batch_validation",
  "payload": { "scope": "parcels" },
  "idempotency_key": "unique-client-key-001"
}
```

**Response:** `202 Accepted`
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "job_type": "batch_validation",
    "status": "QUEUED",
    "progress": 0.0,
    "created_at": "2024-01-01T00:00:00Z",
    "started_at": null,
    "completed_at": null,
    "result": null,
    "error_message": null
  },
  "meta": { "message": "Job queued for background execution" }
}
```

**Idempotency:** If `idempotency_key` is provided and a job with the same key exists, the existing job is returned (no duplicate creation).

### 8.2 List Jobs
```http
GET /api/v1/jobs?status=QUEUED&job_type=batch_validation&page=1&page_size=20
Authorization: Bearer <token>
```

### 8.3 Get Job Status
```http
GET /api/v1/jobs/{job_id}
Authorization: Bearer <token>
```

**Job Status Flow:**
```
QUEUED → PROCESSING → VALIDATING → COMPLETED
                   ↘             ↘ FAILED
                    CANCELLED (via /cancel)
```

### 8.4 Cancel Job
```http
POST /api/v1/jobs/{job_id}/cancel
Authorization: Bearer <token>
```
- Only `QUEUED` and `PROCESSING` jobs can be cancelled.
- Users can only cancel their own jobs (admins can cancel any).

---

## 9. Health & Readiness Probes

```http
GET /health          # Liveness probe
GET /ready           # Readiness probe (checks DB + Redis)
GET /api/v1/health   # Full system health
GET /api/v1/ready    # Full readiness (alias)
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "environment": "production",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "ml_engine": "disabled"
  }
}
```

---

## 10. Error Response Envelope

All API responses follow a consistent envelope:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "meta": { "message": "...", "pagination": { ... } },
  "error": null
}
```

**Error:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": {}
  }
}
```

**Error Codes:**

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `AUTHENTICATION_ERROR` | 401 | Invalid or missing token |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource does not exist |
| `CONFLICT` | 409 | Resource state conflict |
| `INVALID_GEOMETRY` | 422 | Geometry parsing or validity error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

**Security Headers** (included in all responses):
```
X-Request-ID: <uuid>
X-Process-Time: <ms>
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## 11. ML Engine Integration (Decoupled)

The ML Engine is intentionally decoupled and will be integrated in a future phase.

**Current behavior:**
- `ML_ENGINE_ENABLED=false` (default): Height estimation jobs return `{ "status": "decoupled" }`.
- `ML_ENGINE_ENABLED=true`: The backend will forward requests to `ML_ENGINE_URL`.

**ML Engine contract interface** (`app/integrations/ml_engine/contracts.py`):
```python
class HeightEstimationRequest:
    parcel_id: str
    building_id: str
    lat: float
    lon: float
    footprint_wkt: Optional[str]

class HeightEstimationResponse:
    building_id: str
    estimated_height_m: float
    confidence_score: float
    model_version: str
```

**Endpoint for future ML trigger:**
```http
POST /api/v1/buildings/{building_id}/estimate-height?lat=28.6139&lon=77.2090
Authorization: Bearer <admin_token>
```

---

## 12. Environment Configuration

Copy `.env.example` to `.env` and configure:

```env
# Database (required)
DATABASE_URL=postgresql+asyncpg://strata:strata@localhost:5432/strata_db
POSTGRES_USER=strata
POSTGRES_PASSWORD=strata
POSTGRES_DB=strata_db

# Redis (required for worker queue)
REDIS_URL=redis://localhost:6379/0

# JWT Security (change in production!)
SECRET_KEY=change-me-in-production-use-32-chars-minimum
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS (set to your frontend origin in production)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# ML Engine (disabled by default — integrate later)
ML_ENGINE_ENABLED=false
ML_ENGINE_URL=http://ml-engine:8001

# Application
ENVIRONMENT=development
PROJECT_NAME=STRATA 3D-Mapping Backend
LOG_LEVEL=INFO
```

### Docker Compose Quick Start
```bash
docker compose up -d
# Runs: PostgreSQL/PostGIS, Redis, Backend API, Background Worker
# API available at: http://localhost:8000
# Swagger UI: http://localhost:8000/docs
# OpenAPI JSON: http://localhost:8000/api/v1/openapi.json
```

### Database Migrations
```bash
alembic upgrade head
```

### Running Background Worker
```bash
python -m app.workers.worker
```
The worker polls Redis (`strata:jobs:queue`) with DB fallback polling every 0.5s.

---

*Last updated: SIH 2026 PS26011 Backend v2.0.0*

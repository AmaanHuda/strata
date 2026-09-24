# Dataset Status & Provenance Audit (SIH 2026 PS 26011)

> **Usage map / per-dataset verification table:** see [`datasets/DATASET_CATALOG.md`](./datasets/DATASET_CATALOG.md) — the authoritative record of which manifests are actively used, metadata-only, or blocked, with verified source URLs and IDs.

## Policy & Requirement
Authoritative dataset requirement for SIH 2026 PS 26011:
**DATASETS MUST COME FROM data.gov.in OR ITS OFFICIAL STATE/UT data.gov.in PORTALS ONLY.**

Datasets from Kaggle, SpaceNet, INRIA, NASA, OpenStreetMap, Wuhan University, synthetic datasets, or scraped unofficial sources are **NOT ALLOWED** for training, validation, or production inference, and exist solely as historical metadata references where noted.

---

## Dataset Audit Matrix

| Dataset | data.gov.in source | Verified | Local data | Intended use | Classification & Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DILRMP Cadastral Progress / Statistics** | `https://data.gov.in/` (Department of Land Resources) | **YES (Portal Verified)** | No (Metadata only) | Reference progress tracking & coverage verification; NOT for 2D/3D geometry. | **DATA_GOV_IN_CANDIDATE_REQUIRES_VERIFICATION** / **METADATA_ONLY** |
| **DILRMP State GIS Cadastral Shapefiles** | State Land Record Portals (`*.data.gov.in` / Bhulekh / Dharani) | **NO (Requires state clearance)** | No (Not present locally) | Ground anchor for 2D parcel boundary alignment. | **DATA_SOURCE_UNAVAILABLE** |
| **Bhuvan Cartosat-3 Ortho Imagery** | `https://bhuvan.nrsc.gov.in/` (ISRO / NRSC) | **NO (Non-data.gov.in portal)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **CartoDEM v3 R1** | `https://bhuvan.nrsc.gov.in/` (ISRO / NRSC) | **NO (Non-data.gov.in portal)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **Copernicus DEM GLO-30** | `https://registry.opendata.aws/copernicus-dem/` (ESA) | **NO (International source)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **NASA SRTM 30m** | `https://earthexplorer.usgs.gov/` (NASA / USGS) | **NO (International source)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **SpaceNet 7 Multi-Temporal** | `https://spacenet.ai/` (SpaceNet LLC / AWS) | **NO (International source)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **INRIA Aerial Image Labeling** | `https://project.inria.fr/aerialimagelabeling/` (INRIA) | **NO (International source)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **WHU Building Dataset** | `http://gpcv.whu.edu.cn/` (Wuhan University) | **NO (International source)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |
| **OpenStreetMap India Buildings** | `https://download.geofabrik.de/asia/india.html` (OSM) | **NO (Crowd-sourced non-gov)** | No (Not present locally) | Historical metadata only; NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE. | **NON_DATA_GOV_SOURCE_NOT_ALLOWED** / **METADATA_ONLY** |

---

## Detailed Dataset Classification

### Classification Categories:
- **A. VERIFIED_DATA_GOV_IN**: Verified catalog/resource published on `data.gov.in` with open download or API access for cadastral/geospatial datasets.
- **B. DATA_GOV_IN_CANDIDATE_REQUIRES_VERIFICATION**: Available on Open Government Data (OGD) platform or state portals; requires authentication or formal state data-sharing clearance.
- **C. NON_DATA_GOV_SOURCE_NOT_ALLOWED**: Global, commercial, crowd-sourced, or foreign academic datasets prohibited from active training or inference.
- **D. METADATA_ONLY**: Retained as architectural schema reference without downloading raw weights/bytes into version control.
- **E. UNAVAILABLE**: Missing dataset needed for full end-to-end trained model inference.

### Missing Data & Pipeline Readiness:
1. **Building Footprints**: No public pan-India building footprint vector geometry exists openly on `data.gov.in`. Pipeline uses input cadastral vector boundaries and algorithmic baseline geometric processing.
2. **LiDAR / High-Resolution Elevation (DSM/DTM)**: Sub-metre DSM/DTM is restricted. Pipeline provides nDSM percentile baseline logic ready for point cloud / raster ingestion.
3. **Internal Floor Plans**: Architectural drawings / floor layouts are unavailable openly. Vertical unit partitioner operates via mathematical floor area division and volumetric unit reconstruction rules.

---

## 2026-09-24 Amendment — Last-Resort Training Source Used (KAGGLE_BENCHMARK)

Per the dated amendment in `AGENTS.md` §3, the Kaggle last-resort path was invoked on
2026-09-23 (user-approved) after Phase 1 established that NO Indian government source
pairs imagery with building mask labels:

| Target | Government-data verdict (Phase 1 evidence table) |
| :--- | :--- |
| Building extraction (imagery → masks) | **DATA_BLOCKED** — no gov source publishes imagery + masks together |
| Building height | **DATA_BLOCKED** — no building-level height ground truth anywhere open |
| Floor counts | **DATA_BLOCKED** — SVAMITVA treats floors as derivable, not published labels |
| Units / floor plans | **DATA_BLOCKED** — state portals are viewing-only |
| Cadastral geometry | **DATA_BLOCKED** for training (Bhu-Naksha is per-state, viewing/export-limited, metadata-only in audit) |

### Source actually used for the single trained checkpoint
- **Dataset**: `utkarshsaxenadn/svamitva-drone-aerial-images` (Kaggle; SVAMITVA
  government-origin drone imagery from Smart India Hackathon 2024/25; CC0 license)
- **Provenance label**: `KAGGLE_BENCHMARK` — community-annotated masks, NOT Survey of
  India ground truth; never presented as data.gov.in-compliant
- **Local audit (verified, not assumed)**: 1,322 image/mask pairs; Building =
  exact colour (0,110,255) per the uploader's own `poly2mask.py`; `FilteredData`
  (690) is a byte-identical subset of `Full Data` (1,322) — only `Full Data` used;
  `BinaryMasks` folder is viridis-colormapped and would poison labels — NOT used;
  61 nodata-blank tiles found (58 excluded, 6 of them building-positive — reported);
  tiles are spatially adjacent (lag-1 seam diff 31.5 vs 51.0 baseline) → contiguous
  split mandatory, random-tile split would leak.
- **Third-party pretrained models bundled in the Kaggle dataset were NOT used.**
  The checkpoint was trained from scratch on this machine.
- Full audit embedded in `models/checkpoints/building_extraction_unet/metadata.json`
  and `datasets/manifests/svamitva_drone_kaggle.json`.

### PostGIS persistence verification (2026-09-24)
Verified against a REAL PostgreSQL 16.4 + PostGIS 3.6.2 instance (portable local
install, port 55432) — NOT inferred from the mocked test suite. Proven end-to-end
over HTTP: register → login → `POST /parcels` → `POST /buildings` → `POST /floors`
→ `GET /buildings/{id}/floors` → `GET /buildings/{id}/geojson`, with rows confirmed
by direct SQL (`ST_GeometryType = ST_Polygon`, `ST_Area > 0`, floor FK intact).
This verification exposed and fixed four real defects that mocked tests could never
catch: (1) `alembic.ini` / `alembic/env.py` UTF-8 BOM prevented migrations from
running at all; (2) migration created `users.role` as VARCHAR while the ORM uses a
PG ENUM — every INSERT failed on real Postgres; (3) SQLAlchemy bound enum member
NAMES (`'ADMIN'`) instead of values (`'admin'`) — real inserts rejected;
(4) nothing ever populated `parcels.geometry_2d` / `buildings.footprint_2d`, so all
PostGIS geometry columns stayed NULL forever and every spatial endpoint silently
returned nothing. All four are fixed and the mocked suites still pass (90 backend +
100 ml-engine).

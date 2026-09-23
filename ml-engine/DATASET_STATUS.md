# Dataset Status & Provenance Audit (SIH 2026 PS 26011)

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

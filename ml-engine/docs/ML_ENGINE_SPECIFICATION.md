# ML Engine Specification
# SIH 2026 — PS 26011: 3D Cadastral Mapping and ULPIN / 3D Property Identity
# Last updated: 2026-09-12

---

## 1. Project Overview

**Problem Statement:** PS 26011 — 3D Cadastral Mapping and ULPIN / 3D Property Identity

India's land record system currently operates primarily in 2D.
Modern urban environments contain multi-storey buildings where
multiple property units exist on the same 2D parcel footprint.
The Unique Land Parcel Identification Number (ULPIN) system
provides unique parcel IDs but does not yet address vertical
(3D) property identity.

**Objective:** Build an ML + AI engine that:
1. Extracts and validates building footprints from 2D cadastral parcels
2. Estimates height, floor count, and unit delineation from available evidence
3. Reconstructs candidate 3D property volumes
4. Fuses multi-source evidence (satellite, LiDAR, drone, BIM, etc.)
5. Validates spatial and topological consistency
6. Computes calibrated confidence and uncertainty
7. Produces a structured, backend-ready ML output contract

The engine produces CANDIDATE geometry with evidence and confidence.
It does NOT make legal, ownership, or registration decisions.

---

## 2. Repository Structure

```
ml-engine/
├── datasets/
│   ├── raw/                  # Original, unmodified source data
│   ├── processed/            # Cleaned, transformed, tiled data
│   ├── manifests/            # Dataset manifests (JSON)
│   └── quality_reports/      # Automated quality reports
├── src/
│   ├── ingestion/            # Data ingestion, format conversion
│   ├── preprocessing/        # Cleaning, normalization, augmentation
│   ├── geospatial/           # CRS, spatial ops, GeoJSON utilities
│   ├── pointcloud/           # LAS/LAZ/DSM/DEM/DTM processing
│   ├── building_extraction/  # Footprint segmentation (Task 1)
│   ├── height/               # Height/elevation estimation (Task 3)
│   ├── floors/               # Floor count detection (Task 4)
│   ├── units/                # Unit/vertical segmentation (Task 5)
│   ├── reconstruction/       # 3D geometry reconstruction (Task 6)
│   ├── fusion/               # Evidence fusion (Task 7)
│   ├── validation/           # Spatial/topological validation (Task 9)
│   ├── confidence/           # Confidence + uncertainty (Tasks 7-8)
│   ├── inference/            # Inference pipeline, output schema
│   └── orchestration/        # Pipeline orchestration (optional LangGraph)
├── models/
│   ├── checkpoints/          # Saved model weights
│   └── registry/             # Model registry metadata (JSON)
├── schemas/                  # JSON / GeoJSON schemas, output contracts
├── configs/                  # Training / inference configs (YAML)
├── tests/
│   ├── unit/                 # Unit tests per module
│   ├── integration/          # Cross-module integration tests
│   └── fixtures/             # Test data, sample inputs/outputs
├── scripts/                  # Utility scripts (batch processing, eval)
├── notebooks/                # Exploratory analysis, prototyping
├── reports/                  # Evaluation and quality reports
├── docs/                     # Documentation (this file, integration guide)
├── experiments/              # Experiment tracking configs and results
├── AGENTS.md                 # Concise permanent operating rules
└── pyproject.toml            # Project dependencies
```

---

## 3. Core Pipeline

```
[Input]
  2D Parcel (ULPIN + boundary polygon)

  [Stage 1] Building Extraction
    Input:  2D parcel boundary + satellite/aerial imagery
    Output: building footprint polygon(s) + confidence

  [Stage 2] Height / Elevation Estimation
    Input:  building footprint + LiDAR/DSM/DEM/drone
    Output: building height (m) + floor height assumption + confidence

  [Stage 3] Floor Detection
    Input:  height estimate + facade imagery + floor plans (if available)
    Output: floor_count + floor_height array + confidence

  [Stage 4] Unit Delineation
    Input:  floor layout + approved plans / BIM / IFC (if available)
    Output: unit polygons per floor + confidence

  [Stage 5] 3D Reconstruction
    Input:  footprint + height + floors + units
    Output: candidate 3D geometry (PolygonZ / MultiPolygonZ / mesh)

  [Stage 6] Evidence Fusion
    Input:  outputs from stages 1-5 + all available evidence sources
    Output: fused property volume + evidence record + conflict flags

  [Stage 7] Spatial Validation
    Input:  fused 3D geometry
    Output: validation report + issue list + VALID/INVALID/REVIEW_REQUIRED

  [Stage 8] Confidence + Uncertainty
    Input:  all stage outputs + evidence quality
    Output: confidence [0,1] + uncertainty [0,1] + review_status

[Output]
  Backend-ready ML Output Contract (see Section 8)
```

---

## 4. Dataset Policy

### 4.1 Priority
1. Official Indian / government sources
2. Reputable research / benchmark datasets
3. Kaggle only when original source, provenance, and license are verified

### 4.2 Legitimate Sources
| Category | Sources |
|---|---|
| Land records | DILRMP, ULPIN official, state land record portals |
| Topographic | Survey of India (SOI) |
| Satellite / Remote sensing | ISRO, NRSC, Bhuvan, Cartosat-2/3 |
| Open government data | data.gov.in, state GIS portals |
| Building / urban | Municipal GIS, smart city data |
| Benchmark | SpaceNet, INRIA Aerial, WHU Building, OpenAerialMap |

### 4.3 Dataset Manifest Schema
Every dataset file must have a corresponding manifest in `datasets/manifests/`:

```json
{
  "name": "Dataset display name",
  "source": "Organization / portal name",
  "url": "Direct URL or portal URL",
  "geography": "State, district, or region (India)",
  "date": "YYYY-MM or YYYY",
  "resolution": "e.g. 0.5m GSD, 1m DEM, N/A for vector",
  "crs": "EPSG:XXXX",
  "labels": "Description of available labels",
  "license": "License identifier or description",
  "provenance": "How was this obtained",
  "status": "REAL|DERIVED|SYNTHETIC|INFERRED|MIXED",
  "limitations": "Known limitations affecting use",
  "intended_use": "Which ML task(s) this dataset supports"
}
```

### 4.4 Prohibitions
- NEVER fabricate datasets, labels, metrics, government data, or legal requirements
- NEVER claim synthetic data is real cadastral truth
- NEVER claim benchmark data is authoritative for Indian land records

---

## 5. Ground Truth Strategy

| Task | Ground Truth Source | Fallback Label |
|---|---|---|
| Building extraction | Municipal GIS footprints, DILRMP vector | benchmark / inferred |
| Height estimation | LiDAR nDSM, UAV photogrammetry | inferred |
| Floor detection | Approved building plans, field survey | weakly_supervised |
| Unit segmentation | BIM/IFC, registered flat plans | unavailable |
| 3D reconstruction | Reference 3D survey geometry | unavailable |
| Change detection | Temporal imagery pairs + reference | inferred |

When ground truth is unavailable: label explicitly. Do NOT invent values.

---

## 6. ML Tasks — Technical Detail

### Task 1: Building Extraction
- **Input:** Aerial/satellite image (RGB or multispectral) + 2D parcel boundary
- **Models:** U-Net baseline → DeepLabv3+ / SegFormer final
- **Metrics:** IoU, Dice, Precision, Recall, F1
- **Post-processing:** Polygon simplification, convexity check, area filter
- **Failure modes:** Shadows, dense urban, attached buildings, trees

### Task 2: Point Cloud Processing
- **Formats:** LAS, LAZ, DSM, DEM, DTM
- **Steps:** Noise removal, ground classification, nDSM generation, void fill
- **Failure modes:** Sparse coverage, vegetation interference, missing Z
- **Library:** PDAL + Open3D

### Task 3: Height Estimation
- **Input:** Building footprint + LiDAR nDSM / photogrammetric DSM
- **Primary:** nDSM statistics (median, 90th percentile) within footprint
- **Fallback:** Facade imagery regression (MAE, RMSE, R²)
- **Output:** height_m + height_method + confidence + uncertainty
- **Hard rule:** If no reliable elevation evidence → return INFERRED + low confidence

### Task 4: Floor Detection
- **Input:** building height + floor-height assumption + facade imagery + plans
- **Methods:** height-division baseline → CNN facade classification (if imagery available)
- **Metrics:** MAE on floor count, accuracy at floor level
- **Failure modes:** Mezzanines, basements, atypical floor heights

### Task 5: Unit / Vertical Segmentation
- **Input:** Floor layout + plans/BIM (if available)
- **Methods:** Plan-based delineation → graph-based unit inference
- **Output:** Unit polygons per floor + confidence
- **Fallback:** If plans unavailable → status=INFERRED, confidence=LOW

### Task 6: 3D Reconstruction
- **Input:** Footprint + height + floor count + unit polygons
- **Output:** PolygonZ / MultiPolygonZ per floor+unit, candidate mesh (trimesh)
- **Metrics:** Volume error, boundary error vs reference (where available)
- **CRS:** Always output in projected CRS + record transformation

### Task 7: Evidence Fusion
- **Sources:** satellite, drone, LiDAR, DEM/DSM, cadastral GIS, floor plans, BIM/IFC, GNSS, temporal imagery, utility data
- **Algorithm:** Weighted evidence aggregation with source reliability scores
- **Conflict handling:** Flag SOURCE_CONFLICT when sources disagree beyond threshold
- **Output:** fused_prediction + evidence_record + conflict_flags

### Task 8: Change Detection
- **Input:** Temporal imagery pairs (t1, t2) or temporal LiDAR
- **Models:** Change vector analysis baseline → Siamese CNN / transformer final
- **Metrics:** Precision, Recall, F1, IoU on changed/unchanged classes
- **Note:** Requires multi-temporal data; clearly document availability status

### Task 9: Spatial / Topological Validation
- **Checks:** Invalid polygons, self-intersections, overlaps between units, gaps, duplicate geometry, invalid Z coordinates, wrong units, floor conflicts, unit conflicts, parcel-building mismatch
- **Library:** Shapely + GeoPandas
- **Output:** validation_status + issue_list + severity

---

## 7. Confidence + Uncertainty Framework

### 7.1 Confidence Factors
Confidence is computed from (not arbitrary):
- Model prediction score (calibrated softmax / entropy)
- Data quality score (resolution, coverage, age)
- Source reliability (government > research > inferred)
- Cross-source agreement ratio
- Geometry validity score
- Freshness (data recency)

### 7.2 Uncertainty Estimation
- Segmentation: MC-Dropout or ensemble variance
- Regression: Quantile regression or Gaussian output head
- Report: uncertainty_stddev or uncertainty_interval

### 7.3 Review Flags
| Condition | Flag |
|---|---|
| confidence < threshold | REVIEW_REQUIRED |
| SOURCE_CONFLICT present | REVIEW_REQUIRED |
| Validation issues found | REVIEW_REQUIRED |
| Ground truth unavailable | REVIEW_REQUIRED |
| Insufficient evidence | INSUFFICIENT_EVIDENCE |

---

## 8. ML Output Contract

### 8.1 Schema
File: `schemas/ml_output_contract.json`

```json
{
  "schema_version": "1.0.0",
  "official_ulpin":   "string (official ULPIN, must not be replaced)",
  "building_id":      "string (internal pipeline ID)",
  "floor_id":         "string",
  "unit_id":          "string",
  "volume_id":        "string (proposed 3D identity, illustrative)",
  "geometry":         "GeoJSON geometry object (PolygonZ or MultiPolygonZ)",
  "geometry_crs":     "string (EPSG code)",
  "height":           "number (metres above ground, float)",
  "floor_count":      "integer",
  "confidence":       "number [0.0, 1.0]",
  "uncertainty":      "number [0.0, 1.0]",
  "evidence": [
    {
      "source": "string",
      "type":   "satellite|lidar|drone|plan|bim|gnss|cadastral|dem|other",
      "reliability": "number [0.0, 1.0]",
      "date":   "string (ISO date or null)"
    }
  ],
  "validation": {
    "status": "VALID|INVALID|REVIEW_REQUIRED",
    "issues": ["array of issue descriptions"]
  },
  "review_status":    "APPROVED|REVIEW_REQUIRED|INSUFFICIENT_EVIDENCE|LOW_CONFIDENCE",
  "data_status":      "REAL|DERIVED|SYNTHETIC|INFERRED|MIXED",
  "model_version":    "string (semver)",
  "dataset_version":  "string",
  "provenance_id":    "string (UUID or hash)",
  "generated_at":     "string (ISO 8601 UTC timestamp)"
}
```

### 8.2 Proposed 3D Property ID Format
Format: `IND-{STATE}-{DISTRICT}-{PARCEL}-FL-{NN}-UNIT-{NNN}-VOL-{NNN}`
Example: `IND-MH-MUM-000123-FL-02-UNIT-005-VOL-001`
**This is illustrative only. It is NOT an official government ULPIN format.**

---

## 9. 3D Property Hierarchy

```
ULPIN (official 2D parcel identity)
  └── Building (extracted footprint + height + metadata)
        └── Floor (floor_id, floor_number, height_above_ground)
              └── Unit (unit_id, boundary polygon, area)
                    └── Volume (3D candidate geometry, CRS, height, confidence)
```

The official ULPIN is the immutable anchor. All 3D identifiers are
application-level extensions and must be clearly distinguished from
official government identifiers.

---

## 10. CRS Policy

| Context | CRS Requirement |
|---|---|
| Storage / interchange | WGS84 geographic (EPSG:4326) acceptable for GeoJSON |
| Processing (distance/area/volume) | Projected CRS required (e.g., EPSG:32643 UTM 43N for relevant zones) |
| Output geometry | Record both original CRS and processing CRS |
| LiDAR data | Preserve native CRS; document and transform explicitly |

Never compute area or distance in degrees.
Document every CRS transformation in provenance.

---

## 11. Point Cloud Processing

### Supported Input Formats
- LAS 1.2, 1.3, 1.4
- LAZ (compressed LAS)
- GeoTIFF DSM (Digital Surface Model)
- GeoTIFF DEM (Digital Elevation Model)
- GeoTIFF DTM (Digital Terrain Model)

### Processing Steps
1. Validate point cloud extent, CRS, and density
2. Ground classification (PDAL's SMRF or PMF filter)
3. Vegetation removal (height above ground threshold)
4. nDSM generation (DSM - DTM)
5. Void filling (IDW or kriging for small gaps)
6. Outlier removal (statistical + radius filtering)
7. Tile generation for large datasets

### Failure Handling
| Issue | Response |
|---|---|
| Missing Z | status=INFERRED, confidence=LOW |
| Sparse coverage | Document in manifest, flag in output |
| Vegetation interference | Apply ground filter; note residual uncertainty |
| Empty region | DATA_UNAVAILABLE |

---

## 12. Indoor / Underground / Airspace

| Domain | Evidence Required | Fallback |
|---|---|---|
| Indoor | BIM/IFC, approved plans, indoor LiDAR | INFERRED geometry only |
| Underground | GPR, utility survey | DATA_UNAVAILABLE |
| Airspace | FSI/FAR regulations + height | Candidate volume only |

AI must NOT determine legal rights in any domain.

---

## 13. Spatial Validation Checks

| Check | Severity |
|---|---|
| Invalid polygon (self-intersection) | HIGH |
| Overlapping units on same floor | HIGH |
| Unit outside building footprint | HIGH |
| Invalid Z coordinate | HIGH |
| Floor gaps (missing floor numbers) | MEDIUM |
| Parcel-building boundary mismatch | MEDIUM |
| Duplicate geometry | MEDIUM |
| Wrong area units | MEDIUM |
| Utility line conflicts | LOW |

---

## 14. Provenance Tracking

Every output record must include:
- `provenance_id`: UUID linking to a provenance log entry
- `dataset_version`: version/hash of the input dataset
- `model_version`: semver of the model used
- `code_version`: git commit hash or release tag
- `generated_at`: ISO 8601 UTC timestamp

Provenance log format: `reports/provenance/{provenance_id}.json`

---

## 15. Testing Requirements

### Test Coverage Per Module
| Module | Required Tests |
|---|---|
| geospatial | CRS transform, area calculation, coordinate range |
| building_extraction | IoU calculation, polygon validity, class balance |
| height | MAE metric, INFERRED fallback, unit conversion |
| floors | floor count accuracy, mezzanine handling |
| reconstruction | volume error, PolygonZ validity, CRS preservation |
| fusion | conflict detection, SOURCE_CONFLICT flag, evidence weighting |
| validation | all spatial checks, edge cases |
| confidence | calibration check, REVIEW_REQUIRED trigger |
| inference | output schema validation (jsonschema), provenance completeness |

### Split Strategy
- Spatial split preferred (geographic holdout by district/grid)
- Never split by random sample alone for geospatial data
- Document split strategy in dataset manifest

---

## 16. Dependency Management

```toml
# pyproject.toml (key dependencies)
[tool.poetry.dependencies]
python = ">=3.10"
torch = "^2.0"
numpy = "^1.24"
pandas = "^2.0"
geopandas = "^0.14"
shapely = "^2.0"
rasterio = "^1.3"
GDAL = "^3.6"
pdal = "^3.0"
open3d = "^0.18"
opencv-python = "^4.8"
scikit-learn = "^1.3"
trimesh = "^4.0"
pytest = "^7.0"
jsonschema = "^4.0"
```

Install new packages only after checking all existing deps first.

---

## 17. Phase Implementation Plan

| Phase | Name | Key Deliverables |
|---|---|---|
| 0 | Repository Audit | Gap analysis, scaffold, AGENTS.md, this spec |
| 1 | Dataset Foundation | Manifests, quality reports, split strategy |
| 2 | Preprocessing + Geospatial | CRS utils, point cloud pipeline, validators |
| 3 | ML Baselines | Baseline segmentation, height regression, floor count |
| 4 | Building/Height/Floor Models | Final models, evaluation reports |
| 5 | 3D Reconstruction | 3D geometry pipeline, CRS output |
| 6 | Evidence Fusion + Validation | Fusion engine, spatial validator |
| 7 | Confidence + Change Detection | Calibrated confidence, change detector |
| 8 | Inference + Output Contracts | Inference pipeline, schema validation, integration docs |
| 9 | Final QA | Full test suite, reproducibility, backend integration guide |

---

## 18. Evaluation Standards

No phase is "complete" until evaluation metrics are measured.
Do not claim improvement without measurement.

Evaluation artifacts:
- `reports/{phase}_{task}_evaluation.json`
- `reports/{phase}_{task}_confusion_matrix.png` (where applicable)
- `reports/{phase}_{task}_calibration.png` (confidence calibration)

---

## 19. Legal Disclaimer (Embedded in All Outputs)

> "This output is a CANDIDATE property volume produced by an ML system.
> It is NOT a legal determination of ownership, boundaries, or property rights.
> All cadastral decisions must be made by competent government authorities
> in accordance with applicable law."

---

## 20. Relationship to AGENTS.md

AGENTS.md = concise permanent operating rules for AI agents
This file = detailed human-readable specification

Do NOT duplicate specification content into AGENTS.md beyond summaries.
Do NOT put this full specification into chat context unnecessarily.

---
End of ML_ENGINE_SPECIFICATION.md
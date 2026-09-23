# AGENTS.md — SIH 2026 | PS 26011 | ML + Dataset + AI Engine
# Persistent operating rules. Future tasks MUST follow this file.
# Last updated: 2026-09-12

---

## 1. MODULE BOUNDARY

### THIS REPOSITORY IS ONLY FOR
- Dataset engineering & geospatial data processing
- Computer vision & machine learning
- AI inference & 3D reconstruction
- Evidence fusion & spatial/topological validation
- Confidence, uncertainty, change detection
- Provenance & ML output contracts
- JSON / GeoJSON schemas, sample payloads, integration documentation

### DO NOT BUILD OR MODIFY
React · Next.js · CesiumJS · Tailwind · Dashboards · FastAPI ·
Express · API Gateway · Authentication · RBAC · PostgreSQL ·
PostGIS · Redis · Cloud deployment · Production infrastructure

Backend and frontend are other teams' responsibility.

---

## 2. CORE PIPELINE

```
2D Parcel
  -> Building Extraction
  -> Height / Elevation
  -> Floor Detection
  -> Unit Delineation
  -> 3D Reconstruction
  -> Evidence Fusion
  -> Spatial Validation
  -> Confidence / Uncertainty
  -> Candidate 3D Property Volume
  -> Backend-ready ML Output
```

---

## 3. DATASET POLICY

AUTHORITATIVE REQUIREMENT:
Datasets must originate exclusively from data.gov.in or official state/UT *.data.gov.in portals.
Third-party portals (Kaggle, SpaceNet, INRIA, NASA, OSM, synthetic/scraped sources) are PROHIBITED from active training, validation, or production inference, and remain purely historical metadata references where recorded.

Legitimate Authoritative Sources:
- data.gov.in (Open Government Data Platform India)
- Official State/UT data.gov.in Subdomains (*.data.gov.in)
- Department of Land Resources (DoLR) / DILRMP / ULPIN-related official portals
- Survey of India / Official State GIS Land Record portals


NEVER:
- Fabricate datasets, labels, metrics, government data, or legal requirements
- Claim synthetic data is real
- Claim benchmark data is authoritative cadastral truth

Every dataset requires a manifest:
  name, source, URL, geography, date, resolution, CRS,
  labels, license, provenance, status, limitations, intended_use

Allowed status values: REAL | DERIVED | SYNTHETIC | INFERRED | MIXED

---

## 4. GROUND TRUTH RULES

| ML Task              | Ground Truth                    |
|----------------------|---------------------------------|
| Building extraction  | footprint / mask                |
| Height               | LiDAR / reference elevation     |
| Floor detection      | verified floor count / plans    |
| Unit segmentation    | verified plans / BIM            |
| 3D reconstruction    | reference geometry              |
| Change detection     | temporal reference labels       |

If ground truth is unavailable: DO NOT INVENT IT.
Label as: benchmark | weakly_supervised | synthetic | inferred | unavailable

---

## 5. DATA QUALITY

Before training validate:
- File integrity, missing data, duplicates
- CRS, geometry validity, coordinate ranges, resolution
- Labels, class balance, temporal consistency, point-cloud quality

Prevent data leakage.
Prefer: spatial split / temporal split / geographic holdout / building-parcel-level split

---

## 6. CRS RULES

- Always preserve: source CRS -> processing CRS -> output CRS
- Use projected CRS for distance / area / volume / geometry calculations
- NEVER calculate area/distance in lat/lon degrees
- UTM Zone 43N (EPSG:32643) where geographically appropriate only
- Transform CRS explicitly and record the transformation

---

## 7. POINT CLOUD / ELEVATION

Supported formats: LAS, LAZ, DSM, DEM, DTM
Handle: noise, vegetation, sparse points, missing Z, empty regions, outliers
If reliable elevation unavailable -> return: status=INFERRED + low confidence + uncertainty + reason
DO NOT fabricate height.

---

## 8. ML TASKS

1. Building extraction
2. Point-cloud processing
3. Height estimation
4. Floor detection
5. Unit / vertical segmentation
6. 3D reconstruction
7. Evidence fusion
8. Change detection
9. Spatial / topological validation

Use the simplest model that satisfies the task.
Do not add LLMs merely for appearance.

---

## 9. BASELINE + FINAL MODEL STANDARD

For every major ML task: BASELINE -> FINAL MODEL -> EVALUATION
Do not claim improvement without measured results.

Metrics:
  Segmentation:      IoU, Dice, Precision, Recall, F1
  Regression:        MAE, RMSE, R2
  Detection:         mAP, Precision, Recall
  Geometry:          boundary error, geometric error, volume error
  Change detection:  Precision, Recall, F1, IoU

---

## 10. 3D PROPERTY HIERARCHY

ULPIN -> Parcel -> Building -> Floor -> Unit -> Volume

- Official ULPIN must NOT be replaced
- Create only a proposed/application-level 3D identity
- Example: IND-MH-BLD-003-FL-02-UNIT-002-VOL-001 (ILLUSTRATIVE ONLY)
- Never claim this is an official government ULPIN format

---

## 11. 3D GEOMETRY

Support: PolygonZ, MultiPolygonZ, 3D mesh representations
Document GeoJSON interoperability limitations (GeoJSON insufficient for full 3D mesh)
Store: geometry, CRS, height, volume, geometry_quality, confidence, provenance

---

## 12. EVIDENCE FUSION

Sources: satellite, drone, LiDAR, DEM/DSM, cadastral GIS,
         floor plans, BIM/IFC, GNSS, temporal imagery, utility data

For every prediction record: prediction, evidence, source_reliability,
agreement/conflict, confidence, uncertainty

If sources disagree -> flag SOURCE_CONFLICT. Do not silently choose one.

---

## 13. CONFIDENCE + UNCERTAINTY

- Do NOT generate arbitrary confidence values
- Base on: model prediction, data quality, source reliability,
  cross-source agreement, geometry validity, uncertainty, freshness
- Keep confidence and uncertainty SEPARATE
- Where practical, evaluate calibration
- Low-confidence cases -> flag REVIEW_REQUIRED

---

## 14. FAILURE POLICY

Test: shadows, vegetation, dense urban, irregular/attached buildings,
poor imagery, missing LiDAR, incomplete plans, conflicting sources,
unusual roofs, basements, mezzanines, changed buildings,
missing metadata, incorrect CRS

If evidence insufficient -> DO NOT HALLUCINATE.
Return: INSUFFICIENT_EVIDENCE or LOW_CONFIDENCE

---

## 15. INDOOR / UNDERGROUND / AIRSPACE

Indoor:      Prefer BIM, approved plans, indoor LiDAR. If unavailable -> candidate/inferred only
Underground: Use GPR, utility, or survey evidence. If unavailable -> DATA_UNAVAILABLE
Airspace:    Candidate spatial volumes only
AI must NOT determine legal ownership or rights.

---

## 16. SPATIAL VALIDATION

Validate: invalid polygons, self-intersections, overlaps, gaps,
duplicate geometry, invalid Z, wrong units, floor/unit conflicts,
parcel-building mismatch, utility conflicts

ML accuracy alone is NOT sufficient.

---

## 17. PROVENANCE

Every important output traceable to: dataset, source, input, processing, model, date, version
Track: dataset_version, model_version, code_version, provenance_id

---

## 18. DATA STATUS

Maintain explicit status: REAL | DERIVED | SYNTHETIC | INFERRED | MIXED
Never hide this distinction.

---

## 19. SYNTHETIC DATA

Use only when necessary.
Record: generation method, parameters, random seed, assumptions, limitations.
Prefer real-world validation.

---

## 20. LANGGRAPH (OPTIONAL)

Use only if it provides genuine orchestration value.
Workflow: Validation -> Preprocessing -> ML -> Reconstruction -> Fusion -> Validation -> Confidence -> Output
DO NOT use an LLM for: coordinate/geometry calc, area, distance, volume, topology.
LangGraph is NOT the backend.

---

## 21. LEGAL BOUNDARY

ML engine provides: candidate geometry + evidence + confidence + validation
ML engine does NOT decide: ownership, legal validity, registration approval, property rights
Never fabricate legal rules.
Final decisions remain with competent authorities.

---

## 22. OUTPUT CONTRACT

Stable ML output schema (where applicable):
{
  "official_ulpin":   "string",
  "building_id":      "string",
  "floor_id":         "string",
  "unit_id":          "string",
  "volume_id":        "string",
  "geometry":         "GeoJSON geometry object",
  "geometry_crs":     "EPSG:XXXX",
  "height":           "float (metres)",
  "floor_count":      "integer",
  "confidence":       "float [0,1]",
  "uncertainty":      "float [0,1]",
  "evidence":         ["list of evidence sources"],
  "validation":       {"status": "VALID|INVALID|REVIEW_REQUIRED", "issues": []},
  "review_status":    "APPROVED|REVIEW_REQUIRED|INSUFFICIENT_EVIDENCE|LOW_CONFIDENCE",
  "model_version":    "string",
  "dataset_version":  "string",
  "provenance_id":    "string"
}
This is a CONTRACT only. Do NOT implement the backend.

---

## 23. TESTING RULES

Every core module requires tests covering:
- Dataset validation, CRS transformation, geometry validity
- Duplicate IDs, overlap detection, missing data
- Low confidence, source conflicts, output schema, inference

Do not proceed to the next phase if current-phase tests fail,
unless explicitly documented as a non-blocking limitation.

---

## 24. DEPENDENCY POLICY

Keep dependencies minimal. Prefer existing dependencies.

Approved: PyTorch, NumPy, Pandas, GeoPandas, Shapely, Rasterio,
          GDAL, PDAL, Open3D, OpenCV, scikit-learn, trimesh, pytest, jsonschema

Before installing: (1) check if it exists, (2) check if an existing dep solves it,
                   (3) install only if necessary.

---

## 25. TOKEN-EFFICIENCY RULES

INSPECT -> PLAN -> MINIMAL CHANGE -> TEST -> REPORT

1.  Inspect before editing
2.  Read only relevant files
3.  Never dump huge files into context
4.  Never load raw LAS/TIF/large GeoJSON unnecessarily
5.  Inspect metadata, schema, bounds, samples instead
6.  Use scripts for large datasets
7.  Modify only necessary files
8.  Reuse correct existing code
9.  Do not rewrite working modules
10. Do not duplicate implementations
11. Keep responses concise
12. Run targeted tests
13. Report only important results
14. Do not install unnecessary dependencies
15. Do not regenerate unchanged files

---

## 26. PHASE GATES

Phase 0: Repository / Data Audit
Phase 1: Dataset Foundation
Phase 2: Preprocessing + Geospatial Foundation
Phase 3: ML Baselines
Phase 4: Building / Height / Floor Models
Phase 5: 3D Reconstruction
Phase 6: Evidence Fusion + Validation
Phase 7: Confidence / Uncertainty + Change Detection
Phase 8: Inference + Output Contracts
Phase 9: Final QA

Each phase: implementation -> targeted tests -> validation -> short report

---

## 27. DEFINITION OF DONE

[ ] Datasets verified & provenance documented
[ ] Ground truth defined
[ ] Preprocessing reproducible, CRS validated, leakage controlled
[ ] Baselines + final models evaluated
[ ] Building extraction, height estimation, floor detection complete
[ ] 3D reconstruction & evidence fusion complete
[ ] Topology validation complete
[ ] Confidence + uncertainty implemented
[ ] Failure handling implemented
[ ] Change detection implemented (where data permits)
[ ] Model versioning & reproducibility documented
[ ] HITL flags implemented
[ ] Explainability / evidence trace implemented
[ ] Output schemas finalized
[ ] All tests passing
[ ] Backend integration guide complete

---
End of AGENTS.md — do not duplicate this content into other files.
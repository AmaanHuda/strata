# SIH 2026 PS 26011 — Ground-Truth & Dataset Matrix
**Sub-Theme:** 3D Cadastral Mapping & 3D Property Identity (ULPIN)  
**Author:** ML + Dataset + AI Engineering Lead  
**Last Updated:** 2026-09-12  

---

> [!IMPORTANT]
> **AUTHORITATIVE DATASET REQUIREMENT (SIH 2026 PS 26011):**
> Active datasets must originate exclusively from `data.gov.in` or official state/UT `*.data.gov.in` portals. All external benchmark datasets mentioned below are historical research references and are **NOT USED FOR TRAINING/VALIDATION/PRODUCTION INFERENCE**.

## 1. Executive Summary & Policy

In accordance with SIH 2026 data integrity rules:
1. **Never fabricate ground truth:** Global benchmark datasets (SpaceNet, INRIA, WHU) are NOT used for training or production inference.
2. **Authoritative Indian Cadastral Data:** Publicly available Indian satellite imagery (Bhuvan Cartosat-3) and coarse elevation (CartoDEM v3, Copernicus GLO-30) do not come with building-level polygon annotations, building-scale LiDAR point clouds, or internal strata floor plans.
3. **Transparent Classification:** Every ML task is classified into: `REAL_DATA`, `DERIVED`, `SYNTHETIC`, `INFERRED`, or `DATA_LIMITED`.


---

## 2. Comprehensive Ground-Truth Matrix

| ML Task | Input Modality | Ground Truth | Source / Provenance | Real / Synthetic Status | Train / Val / Test Split Strategy | Primary Metric(s) | Current Engineering Status | Documented Real-World Limitations |
|---|---|---|---|---|---|---|---|---|
| **1. Building Footprint Extraction** | High-res Optical Imagery (Bhuvan Cartosat-3, 0.25m–1m GSD; SpaceNet 7 / INRIA / WHU) | 2D Building Footprint Mask / Polygon | SpaceNet 7 (Global AOIs), INRIA Aerial, WHU Building; OSM India Buildings (weak) | **MIXED** (Global benchmark = REAL; Indian pilot = WEAK / INFERRED from OSM) | Geographic holdout: Train on global benchmark AOIs, validate on held-out sub-regions, test on manual Indian pilot samples | IoU, Dice Coefficient, Precision, Recall, F1-Score | **COMPLETE (Engineering) / DATA-LIMITED (Pan-India)** | Official cadastral building footprint annotations are absent from public geoportals. Pre-trained on open research benchmarks with transfer learning heuristics. |
| **2. Building Height Estimation** | DSM, DTM, nDSM rasters; High-resolution point clouds; Optical shadow cues | Rooftop Height above ground ($Z_{\text{top}} - Z_{\text{base}}$) in metres | CartoDEM v3 (30m), Copernicus GLO-30 (30m), NASA SRTM (30m); Simulated high-res nDSM | **DATA_LIMITED** (Indian public domain lacks sub-metre LiDAR) | Spatial split across distinct municipal district tiles | MAE, RMSE, Median Absolute Error (MedAE), p90 Absolute Error, Relative Error (MAPE %) | **COMPLETE (Engineering) / DATA-LIMITED (Real LiDAR)** | Indian national geoportals currently provide 30m grid DEMs; building-scale LiDAR is restricted. System computes 90th-percentile nDSM rooftops when available, falling back to facade/storey heuristics tagged `INFERRED_HEIGHT`. |
| **3. Storey & Floor Detection** | Building height ($H_m$), monocular imagery, OSM `building:levels` | Labelled floor count per structure (integer $\ge 1$) | OSM tags (`building:levels`), Municipal property tax records (pilot site) | **WEAKLY_SUPERVISED / INFERRED** | Municipal Ward / Geographic holdout | Accuracy, Multi-class F1, Floor Count MAE | **COMPLETE (Rule-Based & Metadata Heuristic)** | Supervised training data with verified architectural floor levels is not openly published in India. The engine implements a deterministic rule-based height division ($\approx 3.0\text{m/floor}$) and metadata ingestion, tagging outputs `DERIVED` or `INFERRED`. |
| **4. Unit / Vertical Strata Parcelization** | 2D building footprint, floor level, total floor count, base elevation | Architectural floor plans, BIM/IFC models, approved subdivision deeds | Synthetic subdivision based on major-axis bounding decomposition; Pilot site CAD drawings | **CANDIDATE_VERTICAL_UNIT_GENERATION (Ground Truth UNAVAILABLE)** | N/A (Algorithmic geometric partitioning) | Geometric validity, Non-overlapping topology, Area conservation | **COMPLETE (Geometric Engine) / UNIT_GROUND_TRUTH = UNAVAILABLE** | Authoritative 3D indoor property boundary deeds and BIM records are private/restricted. The engine outputs candidate strata volumes with explicit `source_status = CANDIDATE_VERTICAL_UNIT_GENERATION` and `unit_ground_truth_status = UNAVAILABLE`. |
| **5. 3D Volume Reconstruction & Mesh Export** | 2D Footprints, rooftop height, base elevation, local projected CRS | 3D LoD1/LoD2 CAD meshes, CityJSON reference models | Derived from Tasks 1–4; Synthetic 3D Solid geometries | **DERIVED / GEOMETRIC_VALIDATION** | Topological validation test suite across diverse polygonal topologies | Vertex/face consistency, 2-manifold closed solid checks, CityJSON v1.1 schema validation | **COMPLETE (Engineers LoD1.2 Solid CityJSON, Wavefront OBJ, 3D GeoJSON)** | No open national 3D cadastral mesh registry exists in India. Models are reconstructed using rigorous extrusion and projected CRS transformations (EPSG:4326 $\rightarrow$ Indian UTM Zones 42N–47N). |
| **6. Multi-Temporal Change Detection** | Bi-temporal image chips ($T_1, T_2$), bi-temporal DSMs ($H_{t1}, H_{t2}$) | Change masks & categorical change labels (NEW, DEMOLISHED, VERTICAL_EXTENSION, HORIZONTAL_EXTENSION, UNCHANGED) | SpaceNet 7 Multi-Temporal dataset (benchmark); ISRO Bhuvan multi-season imagery (requires clearance) | **MIXED** (SpaceNet 7 = REAL Benchmark; Test suite = SYNTHETIC_TEMPORAL_TEST) | Temporal split ($T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$) | Precision, Recall, F1-Score, Height Delta Accuracy ($\Delta H$) | **COMPLETE (Algorithmic & Rule Classifier)** | Multi-temporal sub-metre imagery with registered elevation changes across Indian cities is restricted. SpaceNet 7 serves as benchmark; unit tests simulate vertical and horizontal building additions. |

---

## 3. Data Leakage & Spatial Integrity Controls

To maintain scientific validity:
1. **No Random Pixel/Tile Splits:** All spatial datasets must be split along geographic administrative boundaries (districts, talukas, or non-overlapping bounding boxes) to prevent spatial autocorrelation leakage.
2. **Temporal Integrity:** For change detection, earlier chronological observation pairs are assigned strictly to training and later timestamps to evaluation.
3. **CRS Separation:** Lat/Lon degrees are never used for metric distances, areas, or volume calculations; dynamic UTM zone projection is enforced for all geometric operations.

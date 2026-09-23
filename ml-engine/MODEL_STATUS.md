# Model & Algorithmic Component Status (SIH 2026 PS 26011)

## Status Overview
- **Trained Model Weights in Repository**: **NONE (0 checkpoints)**
- **Algorithmic Baselines & Rules**: **COMPLETE & OPERATIONAL**
- **Inference Mode**: `baseline_only` (Algorithmic / Analytical / Geometric / Rule-Based)
- **Government Compliance**: Fully decoupled from unverified external weights.

---

## Component & Model Status Matrix

| Model / Component | Implementation Location | Trained Weights Present? | Training Dataset | Inference Available? | Type | Status & Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Footprint Segmenter** | `src/building_extraction/model.py` | **No** (0 MB) | N/A (Algorithmic baseline) | **Yes** (Algorithmic) | **BASELINE / RULE-BASED** | `BaselineFootprintSegmenter` extracts convex hulls / bounding polygons from input raster/vector masks. Deep learning U-Net architecture is implemented in code but marked unweighted. |
| **Height Estimator** | `src/height/estimator.py` | **No** (0 MB) | N/A (Analytical nDSM) | **Yes** (Analytical) | **BASELINE / ANALYTICAL** | `BuildingHeightEstimator` computes 90th-percentile height from nDSM raster patches or calculates analytical height from floor count heuristic. No deep regression weights loaded. |
| **Floor Count Detector** | `src/floors/detector.py` | **No** (0 MB) | N/A (Height division) | **Yes** (Rule-Based) | **BASELINE / RULE-BASED** | `FloorCountDetector` derives storey count from height division ($H / 3.0\text{m}$) or parses municipal metadata levels. |
| **Vertical Unit Segmenter** | `src/units/segmenter.py` | **No** (0 MB) | N/A (Geometric division) | **Yes** (Rule-Based) | **BASELINE / GEOMETRIC** | Generates candidate 3D property volumes and floor-associated unit boundaries based on area partitioning. |
| **3D Volume Reconstruction** | `src/reconstruction/builder.py` | **No** (0 MB) | N/A (Extrusion math) | **Yes** (Algorithmic) | **BASELINE / GEOMETRIC** | Extrudes 2D polygon footprint to LoD1/LoD2 3D solid geometries (PolygonZ / PolyhedralSurface). |
| **Evidence Fusion Engine** | `src/fusion/engine.py` | **No** (0 MB) | N/A (Bayesian / Dempster-Shafer) | **Yes** (Statistical) | **BASELINE / STATISTICAL** | Merges multi-source evidence scores (satellite, elevation, cadastral) into unified confidence and detects conflict. |
| **Cadastral Rule Engine** | `src/validation/cadastral_rules.py` | **No** (0 MB) | N/A (Spatial topology) | **Yes** (Topological) | **BASELINE / TOPOLOGICAL** | Enforces cadastral topological constraints (containment within parcel, intersection, setback). |
| **Confidence Calibrator** | `src/confidence/calibrator.py` | **No** (0 MB) | N/A (Mahalanobis / Calibration) | **Yes** (Statistical) | **BASELINE / STATISTICAL** | Generates calibrated confidence intervals and review status classifications. |

---

## Health Endpoint Status Contract
When querying `GET /health` on the ML Engine service:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "device": "cpu",
  "components_available": [
    "footprint_segmenter",
    "height_estimator",
    "floor_detector",
    "volume_reconstruction",
    "evidence_fusion",
    "cadastral_validator",
    "confidence_calibrator"
  ],
  "trained_models_loaded": false,
  "models_loaded": [],
  "datasets_available": false,
  "inference_ready": "baseline_only"
}
```
This honestly reflects that algorithmic baseline engines are active, while zero unverified deep learning model weights or unauthorized datasets are loaded.

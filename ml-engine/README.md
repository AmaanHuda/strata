# SIH 2026 — PS 26011: 3D Cadastral Mapping & ULPIN ML Engine

**Problem Statement:** PS 26011 — 3D Cadastral Mapping and ULPIN / 3D Property Identity  
**Repository:** ML + Dataset + AI Engineering Core  
**Status:** **ML Engineering Pipeline Complete; Real-World Validation is Dataset-Dependent**  
**Automated Tests:** **53/53 Passed (100% Algorithmic Test Suite)**  
**Documentation:** [docs/FINAL_ML_AUDIT.md](file:///docs/FINAL_ML_AUDIT.md) | [docs/GROUND_TRUTH_MATRIX.md](file:///docs/GROUND_TRUTH_MATRIX.md) | [docs/DATASET_STRATEGY.md](file:///docs/DATASET_STRATEGY.md)

---

## 🚀 Engineering Capabilities & Status

| Capability | Module Path | Engineering Status | Data / Scientific Validation Tier |
|---|---|---|---|
| **Dataset Foundation** | `datasets/manifests/` | ✅ **Complete** | **DATA-LIMITED** (9 standard manifests for Indian & benchmark data) |
| **Preprocessing + Geospatial** | `src/geospatial/`, `src/preprocessing/` | ✅ **Complete** | **COMPLETE** (Indian UTM Zones 42N–47N, metric geometry) |
| **Footprint Extraction** | `src/building_extraction/` | ✅ **Complete** | **BENCHMARK VALIDATED** (U-Net & baseline segmentation) |
| **Height Estimation** | `src/height/`, `src/pointcloud/` | ✅ **Complete** | **DATA-LIMITED** (nDSM $p90$ extraction + facade heuristics) |
| **Floor Detection** | `src/floors/` | ✅ **Complete** | **RULE-BASED / INFERRED** (Deterministic height division) |
| **3D Strata Unit Partitioner** | `src/units/` | ✅ **Complete** | **CANDIDATE GENERATION** (`UNIT_GROUND_TRUTH = UNAVAILABLE`) |
| **3D Reconstruction & Mesh** | `src/reconstruction/` | ✅ **Complete** | **GEOMETRIC VALIDATION** (CityJSON 1.1, OBJ, 3D GeoJSON) |
| **Evidence Fusion & Conflict** | `src/fusion/` | ✅ **Complete** | **COMPLETE** (Reliability weighting & conflict flagging) |
| **Change Detection** | `src/change_detection/` | ✅ **Complete** | **BENCHMARK VALIDATED** (Vertical/horizontal extension rules) |
| **Confidence & Uncertainty** | `src/confidence/` | ✅ **Complete** | **STATISTICAL CALIBRATION** (Brier Score, ECE, Prediction Intervals) |
| **Inference Pipeline & Output**| `src/inference/` | ✅ **Complete** | **COMPLETE** (Validated against `schemas/ml_output_contract.json`) |

---

## 🛠️ Verification & Benchmark Commands

```bash
# 1. Run all unit and integration tests
pytest

# 2. Run the scientific ML benchmark suite
python scripts/run_benchmarks.py

# 3. Validate all dataset manifests
python scripts/validate_manifest.py

# 4. Check dataset quality reports
python scripts/dataset_quality_check.py
```

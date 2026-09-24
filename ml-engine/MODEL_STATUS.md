# Model & Algorithmic Component Status (SIH 2026 PS 26011)

> **Last updated: 2026-09-24** — reflects the first genuinely trained model in this
> repository. All earlier claims in this file that "no checkpoints exist" applied to
> the state before 2026-09-24 and are superseded by the entry below.

## Status Overview
- **Trained Model Weights in Repository**: **1 checkpoint**
  (`models/checkpoints/building_extraction_unet/` — `model.pt`, 4.4 MB,
  1,093,381 trainable parameters, PyTorch 2.14.0+cpu)
- **Dataset provenance of that checkpoint**: **KAGGLE_BENCHMARK** (SVAMITVA drone
  imagery, government-**origin**; masks are **community annotations**, NOT Survey of
  India ground truth). See `DATASET_STATUS.md` and the checkpoint's `metadata.json`
  for the full honest audit.
- **Algorithmic Baselines & Rules**: **COMPLETE & OPERATIONAL** (unchanged)
- **Inference Mode**: `trained_models_available` for building-footprint extraction;
  `baseline_only` for every other target (height, floors, units, cadastral)
- **Government Compliance**: The trained checkpoint is **NOT** presented as
  data.gov.in-compliant or as authoritative cadastral truth. It is a benchmark-grade
  demonstration of the training pipeline end to end.

## Trained Checkpoint — Real Metrics (no fabrication)

Trained 2026-09-24 from scratch (no third-party weights) on 1,264 usable tiles out of
1,322 (58 nodata-blank tiles excluded, 6 of which contained building pixels — reported,
not hidden). Split: contiguous by tile order (spatially disjoint; density shift between
splits is measured and reported, not corrected). Best epoch: 6 of 10 (early stopping).

| Evaluation | IoU | Dice/F1 | Precision | Recall | Tiles |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Test — contiguous (primary, honest)** | **0.241** | 0.322 | 0.304 | 0.594 | 190 |
| Test — stratified random (leakage-optimistic, reported for comparison only) | 0.440 | 0.499 | 0.497 | 0.656 | 190 |
| Validation (best epoch) | 0.372 | 0.471 | 0.470 | 0.735 | 190 |

Independent post-training sanity check: mean IoU 0.297 on 12 randomly sampled unseen
test tiles via the registry-loaded model (`load_trained_model`).

**Honest interpretation**: the model learned real structure (random-init IoU ≈ 0) but
the primary metric is depressed by (a) the deliberate leakage-resistant split carrying
a severe building-density shift (train 36.5% vs test 100% positive tiles) and (b)
single-day community annotations of uneven quality. The leakage-optimistic number is
shown to make that cost explicit — it is **not** the headline. CPU constraints
(base_channels 12) also limit capacity; a GPU run with the full-size config is the
natural next step.

## Component & Model Status Matrix

| Model / Component | Implementation Location | Trained Weights Present? | Type | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Footprint Segmenter (trained U-Net)** | `src/building_extraction/torch_unet.py` + `models/checkpoints/building_extraction_unet/` | **YES** (KAGGLE_BENCHMARK provenance) | **TRAINED (nn.Module)** | Real torch U-Net; loads via `src/inference/model_registry.py`; never served without provenance metadata. |
| **Footprint Segmenter (baseline)** | `src/building_extraction/dl_models.py` / `model.py` | No | BASELINE / HEURISTIC | `HeuristicFootprintSegmenter`; truthfully labelled untrained; used when no checkpoint is registered. |
| **Height Estimator** | `src/height/estimator.py`, `dl_height.py` | No | BASELINE / ANALYTICAL | `HeuristicHeightEstimator`; returns `None`/`NO_SIGNAL` with no signal — the old fabricated 9.0 m / 0.50-confidence fallback was removed 2026-09-23. |
| **Floor Count Detector** | `src/floors/detector.py` | No | BASELINE / RULE-BASED | Height-division heuristic; height/floor/unit datasets are DATA_BLOCKED (see DATASET_STATUS.md). |
| **Vertical Unit Segmenter** | `src/units/segmenter.py` | No | BASELINE / GEOMETRIC | Geometric partitioning. |
| **3D Volume Reconstruction** | `src/reconstruction/builder.py` | No | BASELINE / GEOMETRIC | LoD1/LoD2 extrusion. |
| **Evidence Fusion Engine** | `src/fusion/engine.py` | No | BASELINE / STATISTICAL | Bayesian / Dempster-Shafer fusion. |
| **Cadastral Rule Engine** | `src/validation/cadastral_rules.py` | No | BASELINE / TOPOLOGICAL | Containment / intersection / setback rules. |
| **Confidence Calibrator** | `src/confidence/calibrator.py` | No | BASELINE / STATISTICAL | Calibrated intervals + review status. |

## Registry & Health Contract
`GET /health` is driven by `src/inference/model_registry.py`, which counts a checkpoint
only when weights AND provenance metadata exist and it is not a smoke artifact:

```json
{
  "torch_available": true,
  "checkpoints_found": 1,
  "models_loaded": ["building_extraction_unet"],
  "trained_models_loaded": true,
  "inference_ready": "trained_models_available",
  "untraceable_checkpoints": [],
  "smoke_test_artifacts": []
}
```

Anti-fabrication guarantees (regression-tested in `tests/unit/test_model_registry.py`,
`tests/unit/test_server_honesty.py`, backend `tests/unit/test_ml_client_honesty.py`):
- No checkpoint without traceable dataset provenance is ever loadable or reported.
- No ML endpoint returns invented constants when the model or engine is unavailable;
  failures surface as errors (503), never as data.
- The in-process analytical baselines are never described as trained models.

## Provenance Label
`dataset_provenance: KAGGLE_BENCHMARK` — permitted only under the dated amendment in
`AGENTS.md` §3. Never present this checkpoint as data.gov.in-compliant, as
authoritative cadastral truth, or as a validated pan-India model.

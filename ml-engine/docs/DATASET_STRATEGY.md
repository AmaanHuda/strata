# Dataset Strategy — SIH 2026 PS 26011
# Phase 1: Dataset Foundation

---

## 1. Task-to-Dataset Mapping

| ML Task | Primary Dataset(s) | Ground Truth Status | Notes |
|---|---|---|---|
| 1. Building Extraction | Bhuvan Cartosat-3 (imagery) + SpaceNet 7 (labels) | INFERRED (Indian) / REAL (SpaceNet AOIs) | Indian ground truth absent — use SpaceNet for pre-training, validate on Indian imagery manually |
| 2. Point Cloud Processing | Copernicus GLO-30 / CartoDEM (pipeline testing) | No LiDAR ground truth — UNAVAILABLE | 30m DEMs only; building-scale LiDAR not publicly available for India |
| 3. Height Estimation | CartoDEM + Copernicus GLO-30 (terrain baseline) | UNAVAILABLE at building scale | 30m coarse only; building heights must be INFERRED or crowd-sourced |
| 4. Floor Detection | OSM building:levels (weak) | WEAKLY_SUPERVISED | Very sparse OSM coverage; no verified floor plans |
| 5. Unit Segmentation | No public dataset | UNAVAILABLE | Requires BIM/IFC or approved plans — access through pilot site only |
| 6. 3D Reconstruction | Derived from Tasks 1-5 outputs | DERIVED | No Indian 3D cadastral reference geometry exists publicly |
| 7. Evidence Fusion | All sources combined | MIXED | See evidence fusion specification |
| 8. Change Detection | SpaceNet 7 (multi-temporal) | REAL (benchmark) | For Indian pilot: Bhuvan multi-temporal (requires NRSC access) |
| 9. Spatial Validation | Derived from DILRMP parcels | REAL (parcels) | DILRMP access required for official parcel boundaries |

---

## 2. Ground Truth Availability Summary

| Task | Ground Truth | Label Quality | Action |
|---|---|---|---|
| Building footprint | Limited (OSM = noisy crowd-sourced) | LOW-MEDIUM | Pre-train on INRIA/WHU/SpaceNet; fine-tune on Bhuvan imagery + OSM pseudo-labels |
| Building height | NOT AVAILABLE (no public Indian LiDAR) | NOT AVAILABLE | Estimate from coarse DEM + facade heuristics; mark as INFERRED |
| Floor count | Very sparse (OSM:levels) | VERY LOW | Weakly supervised; cross-validate with height/2.8m heuristic |
| Unit boundary | NOT AVAILABLE publicly | NOT AVAILABLE | Pilot site only with official plans |
| 3D geometry reference | NOT AVAILABLE | NOT AVAILABLE | Fully derived; confidence = LOW until verified |
| Change detection | SpaceNet 7 (global) | MEDIUM | Domain gap to Indian cities must be assessed |
| Parcel boundary | DILRMP (access required) | HIGH (official) | Apply through government channel |

---

## 3. Train / Validation / Test Split Strategy

### 3.1 Guiding Principles
- **Spatial splits preferred** over random splits for all geospatial data
- **Never split by random sample alone** — geographic correlation will cause data leakage
- **Geographic holdout** is the primary test set strategy
- **Temporal split** for change detection tasks

### 3.2 Recommended Split Strategy

```
Building Extraction (Task 1):
  Train:      SpaceNet 7 (global AOIs excluding test)
              + INRIA (pre-training)
              + WHU (pre-training)
  Validation: SpaceNet 7 (held-out Indian-subcontinent AOIs)
  Test:       Bhuvan Cartosat imagery (Indian pilot site, manually annotated)
  Method:     Geographic holdout (separate cities/districts for train/val/test)

Height Estimation (Task 3):
  Train:      Copernicus DEM + CartoDEM (terrain features)
              + OSM:levels as weak labels
  Validation: Different district from training
  Test:       Pilot site with any available reference (building permits)
  Method:     Spatial split by district boundary
  Fallback:   Label all predictions as INFERRED if no ground truth available

Floor Detection (Task 4):
  Train:      OSM building:levels (filtered for quality > threshold)
  Validation: Held-out city / district
  Test:       Manually verified floor counts (pilot site)
  Method:     Geographic holdout

Change Detection (Task 8):
  Train:      SpaceNet 7 temporal pairs (t1 → t2)
  Validation: Held-out SpaceNet 7 AOIs
  Test:       Bhuvan multi-temporal Indian pair (requires NRSC access)
  Method:     Temporal split (earlier periods → train, later → test)
```

### 3.3 Data Leakage Prevention Rules
1. **No geographic overlap** between train/val/test areas
2. **No temporal overlap** for change detection
3. **Building/parcel-level split** where individual buildings could appear in multiple chips
4. **Image chip splits** must respect the building footprint boundaries (no chip straddles train/test boundary)
5. **Random augmentation** (flip, rotate, colour jitter) applied to training set only — never test
6. **All split indices** must be saved to `datasets/processed/splits/` for reproducibility

---

## 4. Data Access Roadmap

| Dataset | Access Status | Action Required |
|---|---|---|
| Bhuvan Cartosat-3 imagery | REGISTRATION REQUIRED | Register at bhuvan.nrsc.gov.in; submit project details |
| CartoDEM v3 | REGISTRATION REQUIRED | Same Bhuvan portal |
| Copernicus GLO-30 | FREELY AVAILABLE | Download from AWS Open Data |
| SRTM 30m | FREELY AVAILABLE | Download from USGS EarthExplorer |
| SpaceNet 7 | FREELY AVAILABLE (research) | AWS S3 or Radiant MLHub |
| INRIA Aerial | FREELY AVAILABLE | Direct download from INRIA |
| WHU Building | FREELY AVAILABLE (research) | Direct download from WHU |
| OSM India | FREELY AVAILABLE | Geofabrik daily extract |
| DILRMP cadastral | GOVERNMENT APPROVAL REQUIRED | Contact DoLR / state NIC |

---

## 5. Data Integrity Rules

All raw data must:
1. Be stored in `datasets/raw/` untouched (no modifications)
2. Have a corresponding manifest in `datasets/manifests/`
3. Pass `scripts/validate_manifest.py` before use
4. Have a quality report from `scripts/dataset_quality_check.py` in `datasets/quality_reports/`
5. Record download date, source URL, and file hash (SHA-256) in manifest or provenance log

Processed data:
1. Stored in `datasets/processed/`
2. Processing steps fully documented (script + parameters)
3. Source dataset version recorded
4. Reproducible from raw via documented pipeline

---

## 6. Synthetic Data Policy

Synthetic data may be generated ONLY when:
- Real data is insufficient for a specific task
- Clearly labelled as SYNTHETIC in manifest and output
- Generation method, parameters, and random seed documented
- Validated against real-world properties before use
- Never used to claim performance on real Indian cadastral data

Do NOT fabricate labels or claim synthetic results are real.

---

*See AGENTS.md Section 3-5 for policy summary.*
*See docs/ML_ENGINE_SPECIFICATION.md Section 4-5 for full dataset specification.*
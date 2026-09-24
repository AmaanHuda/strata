# Dataset Catalog — Verified Audit of All Manifests

> **Generated: 2026-09-24** — systematic audit of every manifest under
> `ml-engine/datasets/manifests/` cross-checked against `DATASET_STATUS.md`,
> `README.md`, `AGENTS.md`, the manifest schema
> (`ml-engine/schemas/dataset_manifest.json`), and the actual ML pipeline code.
> **No information is invented**: every claim below comes from a manifest file,
> the status documents, or the code itself. Where a fact is unknown, it is
> marked **UNKNOWN** rather than guessed.

---

## Master Table

| # | Manifest | Dataset name | Exact source | Source URL (from manifest) | Resource ID / slug | License | Used for | Actually used? | Sample / tile count |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `svamitva_drone_kaggle.json` | SVAMITVA Drone Aerial Imagery (Kaggle community mirror) | **Kaggle** (imagery origin: SVAMITVA / Smart India Hackathon, Govt of India) | https://www.kaggle.com/datasets/utkarshsaxenadn/svamitva-drone-aerial-images | Kaggle slug: `utkarshsaxenadn/svamitva-drone-aerial-images` | CC0 1.0 (Public Domain) | **Task 1: building-footprint extraction — TRAINING/VALIDATION/TEST** | ✅ **ACTIVELY USED** (the only trained dataset; real checkpoint `building_extraction_unet`) | 1,322 image/mask pairs; 1,264 usable after excluding 58 nodata-blank tiles (verified locally) |
| 2 | `dilrmp_cadastral.json` | DILRMP — Digital India Land Records Modernisation Programme | **data.gov.in** (DoLR, Ministry of Rural Development, Govt of India) | https://data.gov.in/resource/state-wise-computerization-land-records-dilrmp | data.gov.in resource title: *State-wise Computerization of Land Records (DILRMP)*; numeric resource ID: **UNKNOWN** (not recorded in manifest) | NDSAP / Govt of India; state land-record policies govern raw vectors | Ground anchor reference: official 2D parcel boundaries + ULPIN linkage (intended) | ❌ **NOT USED** — statistics/metadata only; raw GIS vectors require state clearance (never downloaded) | Not downloaded; **UNKNOWN** |
| 3 | `bhuvan_cartosat3.json` | Bhuvan Cartosat-3 Ortho Imagery (India) | ISRO / NRSC — Bhuvan (neither data.gov.in nor Kaggle) | https://bhuvan.nrsc.gov.in/bhuvan_links.php | **UNKNOWN** — no scene/product ID recorded | NRSC data policy; registration + clearance | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 4 | `nrsc_cartoDEM_v3.json` | Cartosat-1 DEM (CartoDEM v3 R1) | ISRO / NRSC — Bhuvan (neither data.gov.in nor Kaggle) | https://bhuvan.nrsc.gov.in/bhuvan_links.php# | **UNKNOWN** — no tile/product ID recorded | NRSC data policy; registration | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 5 | `copernicus_glo30_dem.json` | Copernicus DEM GLO-30 | ESA Copernicus (neither data.gov.in nor Kaggle) | https://registry.opendata.aws/copernicus-dem/ | **UNKNOWN** — no tile ID recorded | Free incl. commercial; attribution required | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 6 | `nasa_srtm30.json` | SRTM 30m | NASA / USGS (neither data.gov.in nor Kaggle) | https://earthexplorer.usgs.gov/ | **UNKNOWN** — no scene ID recorded | Public domain (US Govt work) | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 7 | `spacenet7_multitemporal.json` | SpaceNet 7 — Multi-Temporal Urban Development | SpaceNet LLC / DigitalGlobe / AWS (neither data.gov.in nor Kaggle) | https://spacenet.ai/sn7-challenge/ | AWS S3 bucket: `s3://spacenet-dataset/SpaceNet7/` (from manifest provenance) | SpaceNet Dataset License — research/non-commercial | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 8 | `inria_aerial_labeling.json` | INRIA Aerial Image Labeling Dataset | INRIA (neither data.gov.in nor Kaggle) | https://project.inria.fr/aerialimagelabeling/ | **UNKNOWN** — no version/hash recorded | CC BY 4.0 | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 9 | `whu_building_dataset.json` | WHU Building Dataset | Wuhan University GPCV Lab (neither data.gov.in nor Kaggle) | http://gpcv.whu.edu.cn/data/building_dataset.html | **UNKNOWN** — no version recorded | Free research w/ attribution | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |
| 10 | `osm_india_buildings.json` | OpenStreetMap India — Building Footprints | OpenStreetMap Contributors via Geofabrik (neither data.gov.in nor Kaggle) | https://download.geofabrik.de/asia/india.html | **UNKNOWN** — no snapshot date recorded (manifest says it must be recorded at download time; none was) | ODbL 1.0 (attribution: © OpenStreetMap contributors) | Historical metadata only | ❌ **NOT USED** — metadata-only, no download | 0 |

---

## 1. Which manifests are fully documented

- **`svamitva_drone_kaggle.json`** — the most complete by far. Has exact source,
  working URL, Kaggle slug, license, and a locally verified audit (mask colour
  convention, subset/overlap analysis, nodata census, seam-adjacency evidence,
  1,322/1,264 tile counts, provenance chain, third-party-weights exclusion).
- **All 9 remaining manifests** carry consistent schema-valid metadata: name,
  source, URL, geography, date, resolution, CRS, labels, license, provenance,
  status, limitations, intended use. All pass `tests/unit/test_dataset_manifests.py`
  (schema `additionalProperties: false`, 13 fields, unique names).

Fully documented in the sense of *schema completeness*: **10/10**.
Fully documented in the sense of *resource-level traceability* (resource IDs,
tile IDs, snapshot hashes): **1/10** (svamitva only).

## 2. Missing source links / IDs

| Manifest | What is missing |
|---|---|
| `dilrmp_cadastral.json` | The numeric data.gov.in **resource ID** (URL given is a resource page; the manifest does not record the catalogue ID). Also: no verified state-portal links for raw vectors. **Note (verified 2026-09-24):** the resource URL currently returns HTTP **500** from data.gov.in; the portal root (https://www.data.gov.in/) returns 200 — the link should be re-validated before submission. |
| `bhuvan_cartosat3.json` | No scene/product IDs (understandable — never ordered; but the manifest should say so explicitly) |
| `nrsc_cartoDEM_v3.json` | No tile IDs |
| `copernicus_glo30_dem.json` | No tile IDs |
| `nasa_srtm30.json` | No scene IDs |
| `spacenet7_multitemporal.json` | S3 bucket given, but no AOI list or requester-pays note |
| `inria_aerial_labeling.json` | No dataset version hash |
| `whu_building_dataset.json` | No version hash |
| `osm_india_buildings.json` | No snapshot date (its own manifest says one must be recorded at download time — none was, because no download happened) |

None of these gaps can be filled without downloading or ordering the data, which
was deliberately never done. They are marked UNKNOWN rather than invented.

## 3. Contradictions found (and their status)

| # | Contradiction | Location | Status |
|---|---|---|---|
| C1 | `DATASET_STATUS.md` headline policy says datasets must come from **data.gov.in only**, and labels Kaggle/others **"NOT ALLOWED"** — yet the repo's single trained checkpoint was trained on the Kaggle SVAMITVA mirror | DATASET_STATUS.md §Policy vs svamitva manifest + MODEL_STATUS.md | **RESOLVED before this audit** — DATASET_STATUS.md carries a dated 2026-09-24 amendment documenting the user-approved last-resort use and its five conditions; AGENTS.md §3 carries the same dated amendment. The policy text and the amendment coexist (policy = future rule; amendment = one authorised exception). No change needed now. |
| C2 | README (before 2026-09-24) said "Model checkpoints (empty until weights available)" and "53 unit tests" | README.md | **RESOLVED** — README updated in commit `d889f5f` to reflect the trained checkpoint, honest metrics, and 100-test ML suite. |
| C3 | `dl_models.py` docstring still references the retired `model_version = "1.0.0-unet-cartosat"` string (as a historical warning) | ml-engine/src/building_extraction/dl_models.py:10 | **COSMETIC ONLY** — this is a deliberate warning about the old fabricated version string, not a live claim. The live code reports `is_trained_model = False` honestly. No fix required; noted for transparency. |
| C4 | `run_benchmarks.py` no longer claims pre-training on SpaceNet/INRIA/WHU (fixed 2026-09-23), but the benchmark script never actually consumed any of the 8 non-used manifests | scripts/run_benchmarks.py vs manifests | **CONSISTENT NOW** — benchmarks run on synthetic smoke tiles; manifests are metadata-only. |
| C5 | Manifest statuses vary (`REAL`, `DERIVED`, `MIXED`) but none say `UNUSED` outright; the "actually used" truth lives in `intended_use`/`limitations` text | manifests vs code reality | **DOCUMENTED HERE** — this catalog's Master Table is the authoritative usage map (see column "Actually used?"). |

**Code-level reality check** (evidence, not assumption): `grep` across
`ml-engine/src/`, `scripts/`, `configs/` shows the only manifests/names referenced
by active code paths are the SVAMITVA Kaggle dataset (training harness + configs)
and *conceptual* mentions of OSM/Cartosat in baseline heuristics
(`floors/detector.py` OSM-metadata parsing path, `fusion/engine.py` "osm" source
reliability weight, `preprocessing/normalization.py` Cartosat mention). No code
loads the other 8 datasets; they have no loaders, no download paths, and no tests
beyond manifest schema validation.

## 4. Datasets that are NOT from data.gov.in or Kaggle

**8 of 10 manifests** describe sources outside the permitted two:

- Bhuvan Cartosat-3 (ISRO/NRSC)
- CartoDEM v3 (ISRO/NRSC)
- Copernicus DEM GLO-30 (ESA)
- NASA SRTM 30m (NASA/USGS)
- SpaceNet 7 (SpaceNet/AWS)
- INRIA Aerial Labeling (INRIA)
- WHU Building Dataset (Wuhan University)
- OpenStreetMap India (crowd-sourced, via Geofabrik)

All 8 are correctly self-labelled in their manifests and in DATASET_STATUS.md as
**HISTORICAL METADATA ONLY — NOT USED FOR TRAINING/VALIDATION/PRODUCTION
INFERENCE**, and the code confirms none is consumed. They exist as
provenance/audit records of sources *evaluated and rejected* during Phase 1.
The only trained dataset (SVAMITVA Kaggle mirror) is covered by the dated
AGENTS.md §3 amendment. **No dataset outside data.gov.in/Kaggle is used by the
pipeline.**

## 5. Exact fixes required before SIH submission

**Required (factual/verifiability):**

1. **Re-validate the DILRMP data.gov.in link** — currently HTTP 500 (verified
   2026-09-24). Find the live resource page and record its numeric resource ID in
   `dilrmp_cadastral.json` provenance. (The portal root works; the specific
   resource may have moved.)
2. **Add resource-ID fields where obtainable** for the two Indian-gov manifests
   (DILRMP resource ID; Cartosat-3/CartoDEM "not ordered — no product ID exists"
   note). Do not invent IDs for the foreign/benchmark manifests; a one-line
   "metadata-only, never downloaded" statement is the honest fix.
3. **Record the OSM snapshot date** question is moot (never downloaded) — but the
   manifest should explicitly say "no snapshot taken; dataset never downloaded".

**Recommended (presentation):**

4. Link `DATASET_CATALOG.md` (this file) from `DATASET_STATUS.md` and README so
   reviewers find the usage map.
5. In DATASET_STATUS.md, consider re-titling the audit table column
   "Local data: No" → "Local data: No (metadata-only by design)" to prevent the
   misreading that a download was attempted and lost.

**Not required:** any code change. The pipeline, manifests schema, and tests are
consistent and all green (90 backend + 100 ml-engine at audit time).

---

## Verification commands (reproducible)

```bash
# Manifest/schema validation + uniqueness
cd ml-engine && python -m pytest tests/unit/test_dataset_manifests.py -v

# Confirm no code consumes the metadata-only datasets
grep -rln "inria\|spacenet\|whu_building\|srtm\|copernicus" ml-engine/src ml-engine/scripts | grep -v __pycache__
# (expected: no loader hits; only docstring/heuristic mentions)

# Liveness of source URLs (as of 2026-09-24)
curl -sIL -o /dev/null -w "%{http_code}\n" https://www.kaggle.com/datasets/utkarshsaxenadn/svamitva-drone-aerial-images
curl -sIL -o /dev/null -w "%{http_code}\n" https://data.gov.in/resource/state-wise-computerization-land-records-dilrmp  # -> 500 at audit time
```

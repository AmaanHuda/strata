# On-Demand Ingestion & the Taj Mahal Palace Prototype

**SIH 2026 PS 26011 — STRATA (3D Cadastral Mapping & ULPIN)**
Status: implemented and verified against live data on 2026-09-25.

This document answers three questions:

1. What was actually causing "Not available" everywhere? (root cause)
2. What real code was added/changed, file by file?
3. How do you stand up **one accurate real prototype** — The Taj Mahal Palace Hotel,
   Mumbai — and what would it take to scale to nationwide coverage?

Everything in the worked example is traceable to the exact upstream source object
(`https://www.openstreetmap.org/way/28846517`). No geometry, ULPIN, or attribute in
this document is invented.

---

## 1. Root-cause summary

Your diagnosis is **confirmed on points 1 and 3, and confirmed-but-incomplete on point 2.**

| Your claim | Verdict | Evidence |
|---|---|---|
| **1.** ULPIN mapping is wired correctly end-to-end (`volume_id` → `candidate_ulpin`; `official_ulpin`/`candidate_ulpin` exist in `app/schemas/search.py` and `frontend/src/api/strataBackend.ts`) | **Confirmed** | `MLDataMapper.contract_v1_to_entities()` sets `candidate_ulpin = output.volume_id`; `SpatialEntityItem` and `PointLookupResponse` both carry the field; `strataBackend.ts` declares both on `SpatialEntityItem`, `FloorStructure`, `UnitStructure`. |
| **2.** The real problem is data coverage — only ~12 parcels from one Mumbai pocket were ever ingested, and there is no generic ingestion pipeline | **Confirmed, with a correction** | The DB held exactly **6** parcel/building records: five `SAMPLE-A-0001..0005` from `scripts/sample_buildings.geojson` (TCET, ~19.2086 N / 72.8794 E) plus one `PARCEL-MU-00006` from the GeoJSON import endpoint. The "12" figure looks like parcels+ULPIN rows counted together (the 6 seed buildings also have 6 building-level ULPIN rows). There **is** already a real import pipeline (`POST /api/v1/datasets/import-buildings-geojson`), but it only accepts a **file you upload** — it cannot fetch anything by coordinate, which is why coverage stops where the seed file stops. |
| **3.** `app/api/v1/spatial.py` has no hardcoded bbox/city; it is a generic PostGIS bbox/nearby/point query | **Confirmed** | Read in full: `/spatial/extent`, `/spatial/bbox`, `/spatial/nearby`, `/spatial/query`, `/spatial/search` are all driven by request parameters and `ST_Intersects`/`ST_DWithin`. The only hardcoded coordinates in the repo were frontend **view defaults** (`SelectMap.tsx` `{lat: 18.9220, lng: 72.8347}`, `areaStore.ts` `[{18.9250,72.8370},{18.9200,72.8320}]`, `MapboxSpace.tsx` initial view `{77.209, 28.6139}`) — those are camera starting points, not a data filter. They are however why the app *looks* like it only knows one place: the camera opens on Delhi while the data is in Mumbai, and `frameOnData()` then jumps to the real extent. |

### Three additional defects found while verifying

These were not part of your diagnosis, but they were blocking the prototype and each one is a
genuine bug (fixed here, with tests):

1. **`Parcel.area_sqm` was never populated.** Only buildings got a geodesic area. `/spatial/search`
   therefore returned a parcel with `area_sqm: null` while the building standing on it had a real
   `7391.14 m²`. Fixed in the ingestion path **and** backfilled for existing rows.
2. **`point_in_polygon()` mis-handled closed rings** (`ml-engine/src/geospatial/operations.py`).
   It looped `range(n + 1)` over an already-closed coordinate list, traversing every edge after the
   first **twice**, which flipped the inside/outside parity back. Result: a footprint identical to
   its own parcel reported *"Building footprint encroaches outside parcel boundary (3 vertices
   outside)"* and the record was scored `LOW_CONFIDENCE`. Fixed (plus an on-edge tolerance so shared
   vertices and edges count as inside).
3. **`CANDIDATE_ULPIN_REGEX` rejected building-level candidate ULPINs.** The pattern allowed
   `-F<n>` and `-U<n>` suffixes but not the `-B<n>` suffix that `_derive_candidate_ulpin()` and the
   GeoJSON importer both generate — so `POST /api/v1/ulpin/validate` classified a real building
   ULPIN such as `MH-30-530-349567-P-9AAF7AD1-B1` as **INVALID**. Fixed.

A fourth, milder issue: the ML engine **invented data**. `process_parcel()` fabricated a default
evidence source (`"Cartosat-3 Ortho"`) and, when no height was supplied, ran
`estimate_from_floor_count(floor_count=3)` and returned a hard-coded **9.0 m**. That was being
persisted as though the engine had measured the building. Now the engine derives height only from a
real signal and otherwise returns `height: null` with `review_status: INSUFFICIENT_EVIDENCE`.

---

## 2. File-by-file change list

### New backend files

| File | Purpose |
|---|---|
| `app/integrations/osm/__init__.py` | Public surface of the OSM package. |
| `app/integrations/osm/overpass.py` | Real Overpass API client (mirror failover, time budget, in-process TTL cache) + pure, unit-testable parsing of OSM footprints/tags. |
| `app/services/cadastral_codes.py` | Resolves the four candidate-ULPIN code segments from real administrative names (ISO 3166-2:IN state codes; deterministic, labelled numeric codes). |
| `app/services/on_demand_ingest.py` | The pipeline: OSM fetch → ML engine → PostGIS persistence, CANDIDATE-only. |
| `app/schemas/ingest.py` | Request/response contracts for the ingestion endpoints. |
| `app/api/v1/ingest.py` | `POST /api/v1/ingest/location`, `GET /api/v1/ingest/coverage`. |

### Modified backend files

| File | Change |
|---|---|
| `app/main.py` | Imports and registers the `ingest` router. |
| `app/services/ulpin.py` | Widens `CANDIDATE_ULPIN_REGEX` to accept the `-B<n>` building suffix. |
| `app/api/v1/datasets.py` | The GeoJSON importer now assigns ULPIN code segments via `assign_cadastral_codes()` instead of string slicing, so new imports pass candidate-format validation. |
| `app/integrations/ml_engine/contracts.py` | `MLProcessParcelRequest` gains `floor_count` + `height_source`. |
| `app/integrations/ml_engine/client.py` | In-process fallback forwards `floor_count_metadata`/`height_source`. |

### Modified ML-engine files

| File | Change |
|---|---|
| `ml-engine/src/inference/pipeline.py` | No fabricated evidence or height; `floor_count_metadata`, `height_source`, `has_official_parcel` inputs; "no evidence" is no longer mislabelled as a source conflict. |
| `ml-engine/src/server.py` | `ProcessParcelRequest` accepts `floor_count`/`height_source`. |
| `ml-engine/src/geospatial/operations.py` | `point_in_polygon()` ring/parity fix + on-edge tolerance. |

### Modified frontend files

| File | Change |
|---|---|
| `frontend/src/api/strataBackend.ts` | `ingestLocation()`, `getIngestCoverage()` + typed ingestion result interfaces. |
| `frontend/src/components/map/SelectMap.tsx` | "Fetch real data here" control, optional State/District inputs, provenance-aware status line. |
| `frontend/src/three/MapboxSpace.tsx` | 3D isolation of the selected **real** backend footprint (extrusion + outline + camera focus + isolation badge). |
| `frontend/src/components/scene/BuildingIsolateScene.tsx` | Shows `building_type` + verification state; honest ML-provenance copy; surfaces a real unit candidate ULPIN per floor. |

### Tests added

`tests/unit/test_overpass_osm.py` (35 tests), `tests/unit/test_cadastral_codes.py` (18),
`tests/unit/test_ingest_ulpin_honesty.py` (7) — plus two ML-engine contract tests and one
`point_in_polygon` regression expectation.

**Suite status:** `python -m pytest -q` → **177 passed**; `ml-engine` → **101 passed, 1 skipped**;
`frontend` → `tsc -b` clean and `vite build` succeeds.

---

## 3. The code that matters

### 3.1 Real source data — `app/integrations/osm/overpass.py`

Height and floors come only from tags OSM actually carries, and each value is labelled by how it
was obtained. This is the single most important honesty rule in the module:

```python
FLOOR_TO_FLOOR_M = 3.2  # documented storey constant, used ONLY levels -> height

def derive_height(tags, floor_count):
    raw = (tags or {}).get("height")
    if raw:
        match = _HEIGHT_PATTERN.search(str(raw))
        if match:
            value = float(match.group(1))
            if 0.0 < value <= 500.0:
                return value, "osm_height_tag"          # measured/declared -> REAL signal
    if floor_count and floor_count > 0:
        return round(floor_count * FLOOR_TO_FLOOR_M, 2), "osm_levels_derived"  # DERIVED
    return None, "unavailable"                          # never guess
```

`parse_building_element()` accepts both Overpass geometry encodings — `out geom` emits
`{"lat": .., "lon": ..}` objects, while some tooling yields `[lon, lat]` sequences:

```python
def _extract_lon_lat(point):
    if isinstance(point, dict):
        lon, lat = point.get("lon"), point.get("lat")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        lon, lat = point[0], point[1]
    else:
        return None
    ...
```

Robustness (learned the hard way — a run spent 240 s waiting on `overpass-api.de` and
`overpass.kumi.systems` before failing): a 30 s per-request timeout, a 75 s wall-clock budget
across all mirrors, and an in-process 10-minute query cache keyed by the exact query string.

### 3.2 Candidate code segments — `app/services/cadastral_codes.py`

`ULPINService.generate_parcel_ulpin()` requires `<STATE(2 letters)><DISTRICT(2 digits)>
<TALUK(3 digits)><VILLAGE(6 digits)>`. Real LGD tables are not bundled, so:

```python
ISO_3166_2_IN_STATE_CODES = {"maharashtra": "MH", "delhi": "DL", "karnataka": "KA", ...}

def _hash_segment(value: str, digits: int) -> str:
    digest = hashlib.sha256(f"strata:cadastral:{value.strip().lower()}".encode()).hexdigest()
    return str(int(digest[:16], 16) % (10 ** digits)).zfill(digits)
```

Caller-supplied real numeric codes always win (`code_basis="supplied_lgd"`); otherwise the segment
is derived from the real name (`code_basis="name_hash"`) and the basis is written into
`parcel.metadata_["cadastral_codes"]` with the note that these are **application-internal code
assignments, not gazetted LGD codes**.

### 3.3 The ingestion pipeline — `app/services/on_demand_ingest.py`

Height/floor resolution, in strict priority order, per building:

```python
height_m    = osm.height_m        # measured `height` tag  -> REAL
height_source = osm.height_source if osm.height_m is not None else None
floor_count = osm.floor_count     # real `building:levels` tag
floor_source = osm.floor_source if osm.floor_count is not None else None

if floor_count is None and ml_output and ml_output.floor_count:
    floor_count, floor_source = int(ml_output.floor_count), "ml_derived"
if height_m is None and ml_output and ml_output.height:
    height_m, height_source = float(ml_output.height), "ml_derived"
# ...and if none of the above applied, both stay None. Nothing is defaulted.
```

Every write of the government-only field is the literal `None`, and candidate identifiers are
derived from the cadastral parent chain — never from an internal UUID:

```python
official_ulpin=None,  # never fabricated
...
buildings_in_parcel = (... count of buildings on this parcel ...)
building.candidate_ulpin = f"{parcel.candidate_ulpin}-B{buildings_in_parcel}"
```

A source-scan guard pins this rule so it cannot silently regress:

```python
def test_no_non_null_official_ulpin_is_written_by_ingestion():
    for path in INGEST_SOURCES:
        for model, block in _constructor_blocks(path.read_text(encoding="utf-8")):
            for assign in re.finditer(r"official_ulpin\s*=\s*([^,\n]+)", block):
                assert assign.group(1).strip() == "None", f"{path.name}: {model}(){assign.group(0)}"
```

### 3.4 The ML engine's real output

`MLEnginePipeline.process_parcel()` now takes the real upstream metadata and refuses to invent:

```python
floor_count_metadata: Optional[int] = None,
height_source: Optional[str] = None,
has_official_parcel: Optional[bool] = None,
...
if height_m is not None and float(height_m) > 0:
    h_val, has_direct_h = float(height_m), True
elif floor_count_metadata is not None and int(floor_count_metadata) > 0:
    h_val, has_direct_h = round(int(floor_count_metadata) * FLOOR_TO_FLOOR_M, 2), False
else:
    h_val, has_direct_h = None, False
    validation_issues.append("HEIGHT_UNAVAILABLE: no measured height and no building:levels ...")
```

Also: `has_conflict` is now `fuse_res["review_status"] == "SOURCE_CONFLICT"` only — *"no evidence was
supplied"* is reported as `INSUFFICIENT_EVIDENCE`, not extrapolated into a conflict; and the
official-parcel confidence bonus is granted only when the identifier really has the 14-character
Bhu-Aadhaar shape, not to candidate identifiers.

### 3.5 Frontend isolation — `frontend/src/three/MapboxSpace.tsx`

The 3D view previously drew **nothing** of its own: it relied on Mapbox Standard's generic OSM
extrusions, so there was no way to tell a real backend record from the basemap. It now extrudes the
selected record's **stored** footprint to its **stored** height, and only when both exist:

```tsx
const realGeometry = (enriched.geometry as {type: string; coordinates: unknown} | null) ?? null;
if (realGeometry?.coordinates && (enriched.floors ?? 0) > 0) {
  const heightM = Number(enriched.height ?? 0) > 0 ? Number(enriched.height) : 0;
  if (heightM > 0) {
    setIsolatedBuilding({ id: backendBuildingId, geometry: realGeometry, heightM, floors: ..., label: ... });
    map.flyTo({ center: [focus.lon, focus.lat], zoom: 18.2, pitch: 62, bearing: -22, duration: 1800 });
  }
}
```

```tsx
<Source id="strata-isolated-building" type="geojson" data={isolatedGeoJSON as any}>
  <Layer id="strata-isolated-building-extrusion" type="fill-extrusion" slot="top"
         paint={{ "fill-extrusion-color": "#F59E0B",
                  "fill-extrusion-height": isolatedBuilding.heightM,
                  "fill-extrusion-base": 0,
                  "fill-extrusion-opacity": 0.92 }} />
  <Layer id="strata-isolated-building-outline" type="line" slot="top"
         paint={{ "line-color": "#B45309", "line-width": 2.5 }} />
</Source>
```

If the backend has no record, or a record with no height, `isolatedGeoJSON.features` is empty and
**no block is drawn** — the sidebar states the limitation instead.

---

## 4. The Taj Mahal Palace prototype — verified run

### Target

> The Taj Mahal Palace Hotel, Apollo Bandar, opposite the Gateway of India, Mumbai.
> Query coordinate 18.92170 N, 72.83320 E (your figure — it lands **inside** the real footprint).

### (a) Fetch the real footprint

Overpass query actually issued:

```overpassql
[out:json][timeout:40];way(around:60.0,18.9217,72.8332)["building"]["name"~"Taj Mahal Palace",i];out geom tags;
```

Result: **1 element — OSM way `28846517`**, 18 nodes, closed ring, tags include
`name=Taj Mahal Palace`, `building=yes`, `building:levels=6`, `tourism=hotel`,
`addr:city=Mumbai`, `addr:district=Mumbai`, `addr:postcode=400001`, `wikidata=Q19104`.
Real footprint bbox: `72.8324661, 18.9211335 → 72.8336353, 18.9226705`. There is **no `height`
tag**, so height is derived from `building:levels=6` and labelled `osm_levels_derived`.

### (b) One command does fetch → ML → persist

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8123/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"Demo@12345"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s -X POST http://127.0.0.1:8123/api/v1/ingest/location \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"lat":18.92170,"lon":72.83320,"radius_m":60,
       "name_contains":"Taj Mahal Palace","max_buildings":1,
       "state":"Maharashtra","district":"Mumbai","taluk":"Mumbai",
       "village":"Apollo Bandar","run_ml":true}'
```

Pass `"osm_id": 28846517` instead of `radius_m`/`name_contains` to ingest exactly one object via a
single-way query — this skips the radius scan entirely and is the recommended re-run path (it is
also covered by the 10-minute query cache).

### (c) Real observed result

```
buildings_found     1          buildings_ingested  1      buildings_skipped  0
parcels_created     1          floors_created      6      units_created      438
candidate_ulpins    ['MH-30-530-349567-P-9AAF7AD1-B1']

name                Taj Mahal Palace          type              hotel
OSM source          https://www.openstreetmap.org/way/28846517
footprint area      7391.1 m² (geodesic, ST_Area(::geography))
centroid            72.83316381764706, 18.9220928
height_m            19.2   source: osm_levels_derived        (6 x 3.2 m)
floor_count         6      source: osm_levels_tag
official_ulpin      None                       candidate_ulpin   MH-30-530-349567-P-9AAF7AD1-B1
status              CANDIDATE
ML                  model 0.1.0 · confidence 0.52 · data_status INFERRED · REVIEW_REQUIRED
ML validation       {'status': 'VALID', 'issues': ['HEIGHT_SOURCE: osm_levels_derived']}
floors / units      6 / 438
```

The ML contract produced for **exactly this geometry** (validated against
`ml-engine/schemas/ml_output_contract.json`) is:

```json
{
  "schema_version": "1.0.0",
  "official_ulpin": "MH-30-530-349567-P-9AAF7AD1",
  "building_id": "BLD-MH-30-53",
  "volume_id": "VOL-MH-30-530-349567-P-9AAF7AD1-FL-01-U-001",
  "geometry": { "type": "Polygon", "coordinates": [ ...18 real OSM vertex pairs... ] },
  "geometry_crs": "EPSG:4326",
  "height": 19.2,
  "floor_count": 6,
  "confidence": 0.52,
  "uncertainty": 0.48,
  "evidence": [{ "source": "OpenStreetMap way/28846517", "type": "other", "reliability": 0.4 }],
  "validation": { "status": "VALID", "issues": ["HEIGHT_SOURCE: osm_levels_derived"] },
  "review_status": "REVIEW_REQUIRED",
  "data_status": "INFERRED",
  "model_version": "0.1.0",
  "provenance_id": "80bde8a6-58b3-491e-8ea8-44a537c16976"
}
```

Note the engine's `official_ulpin` key carries a **candidate** reference. That is safe because
`MLDataMapper.contract_v1_to_entities()` only ever copies `official_ulpin` from the *caller's
existing* parcel record (`official_ulpin=parcel.official_ulpin`), never from the engine output —
verified by `tests/unit/test_ingest_ulpin_honesty.py`.

### (d) `GET /api/v1/spatial/search?lat=18.92170&lon=72.83320`

```
floors_count 6     units_count 438     search_radius_m 50.0

PARCEL   identifier       OSM-W28846517
         candidate_ulpin  MH-30-530-349567-P-9AAF7AD1
         official_ulpin   null          status CANDIDATE
         area_sqm         7391.1415     distance_m 0.0   match_type "inside"
         geometry_geojson {"type":"MultiPolygon", ...18-point ring...}

BUILDING identifier       Taj Mahal Palace
         candidate_ulpin  MH-30-530-349567-P-9AAF7AD1-B1
         official_ulpin   null          status CANDIDATE
         area_sqm         7391.1415     height_m 19.2   floor_count 6
         distance_m 0.0                 match_type "inside"
         geometry_geojson {"type":"Polygon", ...18-point ring...}
```

`match_type: "inside"` confirms the click coordinate genuinely falls **within** the stored footprint
(not a proximity guess).

### (e) `GET /api/v1/buildings/ce5dbafb-5a94-4576-8529-1dd63ce0ceb8/structure`

```
building_name       Taj Mahal Palace      building_type  hotel
floor_count         6                     height_m       19.2
footprint_area_sqm  7391.1415             status         CANDIDATE   is_verified false
official_ulpin      null                  candidate_ulpin MH-30-530-349567-P-9AAF7AD1-B1
centroid            {lat: 18.92187872, lon: 72.833135008}
address             "Taj Mahal Palace, Parcel OSM-W28846517"
district            Mumbai                state          Maharashtra
provenance          {"ml_derived": false, "ml_model_version": "0.1.0", "ml_confidence_score": 0.52, ...}
floors[0]           floor 0 "G"  floor_use hotel  ceiling 3.2 m  area 7391.1415 m²
                    candidate_ulpin MH-30-530-349567-P-9AAF7AD1-B1-F0   units 73
floors[0].units[0]  U-01 hotel 101.25 m²  candidate_ulpin MH-30-530-349567-P-9AAF7AD1-B1-F0-U01
floors[5]           "F5"  candidate_ulpin ...-B1-F5   units 73
total units         438
```

`ml_derived: false` while `ml_model_version` is populated is **correct and deliberate**: the ML
engine ran (it produced the confidence and validation), but the height and floor values this record
stores came from OSM's `building:levels` tag, not from inference. The sidebar copy was corrected to
say exactly that.

### (f) Idempotency

Re-running the identical request returns `already_existed: true` in ~1.4 s with
`parcels_reused: 1` and creates **no** duplicate parcel, building, floor, ULPIN record, or unit. The
natural key is the OSM reference (`way/28846517`) stored in `parcel.metadata_`/`building.metadata_`.
Re-running also **completes a missing hierarchy in place** — if the ML service was down when the
footprint was first ingested, a later run backfills the candidate units for floors that have none,
without duplicating anything.

### Coverage proof — `GET /api/v1/ingest/coverage`

```json
{ "parcels": 7, "buildings": 7, "buildings_with_geometry": 7,
  "buildings_with_candidate_ulpin": 7, "buildings_from_osm_ingest": 1,
  "floors": 6, "units": 438 }
```

Before this work the same endpoint reported 6 buildings, 0 floors, 0 units.

### Known limitations of the prototype (stated deliberately)

- **438 candidate units ≠ 438 hotel rooms.** The ML vertical-unit generator partitions a floor by
  area (`floor_area_sqm / 100 m²`, documented in `ml-engine/src/server.py`). Each unit row carries
  `metadata_.basis` saying it is an analytical subdivision, `is_authoritative: false`, and
  `source_status: CANDIDATE_VERTICAL_UNIT_GENERATION`. It is a candidate delineation, not a room
  inventory. Feeding a real `rooms` tag or a surveyed plan would replace the heuristic.
- **No `height` tag on this OSM object.** 19.2 m is `building:levels × 3.2 m`, tagged DERIVED. Real
  heights need a DSM/LiDAR or municipal source (see §6).
- **The parcel boundary is derived from the building footprint** (`parcel_boundary_basis:
  DERIVED_FROM_OSM_BUILDING_FOOTPRINT`). OSM usually has no cadastral parcel boundary; a real
  boundary needs a cadastral vector source.
- **The engine's `floor_id`/`unit_id` (`FL-01`, `U-001`) are internal placeholders.** The backend
  never turns them into identifiers: every floor/unit gets its candidate ULPIN from the cadastral
  parent chain (`…-B1-F0-U01`) instead.
- **No OFFICIAL ULPIN anywhere.** Every identifier produced here is CANDIDATE / non-authoritative.
  Official ULPINs can only arrive from a Survey of India / gazetted source via the registry.

---

## 5. Backend ↔ frontend sync audit

### 5.1 Lifecycle, end to end (all links verified)

```
map click (MapboxSpace.handleMapClick)
  → map.queryRenderedFeatures()                        [basemap preview only]
  → pointLookup()      GET  /api/v1/spatial/search      → ST_Intersects / ST_DWithin (PostGIS, GiST)
        └─ building found → getBuildingStructure()  GET /api/v1/buildings/{id}/structure
                          getBuildingGeometry()     GET /api/v1/buildings/{id}/geometry
  → areaStore.setBackendBuilding{Structure,Geometry}
  → setAppStep(2) → BuildingIsolateScene
        → IsolatedMapboxObject: per-floor fill-extrusion from REAL footprint + REAL height
  → MapboxSpace: strata-isolated-building fill-extrusion (amber) + camera flyTo
```

No missing links: every arrow above returns real data for the Taj. Ingestion
(`POST /api/v1/ingest/location`) sits upstream of this and is now reachable from the UI
("Fetch real data here" in `SelectMap.tsx`), so a user can populate a region and then click it.

### 5.2 Fields returned but **not** consumed (silent-data gaps)

| Endpoint | Field | Status |
|---|---|---|
| `/spatial/search` | `floors_count` | **Not consumed.** `MapboxSpace` prefers `structure.floor_count`; the direct count is dropped. |
| `/spatial/search` | `search_radius_m` | **Not consumed.** The UI reports `distance_m` but cannot explain the tolerance applied. |
| `/spatial/search` | `parcel.status`, `building.status` | **Not consumed.** Only the ULPIN carries a CANDIDATE/OFFICIAL badge; entity-level status is invisible in the sidebar. |
| `/spatial/bbox` | `status` | **Not consumed.** Drawn features do not visually distinguish CANDIDATE from AUTHORITATIVE. |
| `/spatial/extent` | `center_lon`, `center_lat`, `building_count`, `parcel_count` | **Not consumed** (only `has_data` + `bbox` drive `fitBounds`). |
| `/buildings/{id}/structure` | `building_type` | **Was not consumed** — now shown (this is what displays "hotel"). |
| `/buildings/{id}/structure` | `is_verified`, `parcel_id` | `is_verified` now shown; `parcel_id` still unused. |
| `/buildings/{id}/structure` | `district`, `state` | **Not consumed** (only reachable inside the composed `address` string). |
| `/buildings/{id}/structure` | `floors[].height_above_ground_m`, `ceiling_height_m`, `floor_area_sqm`, `volume_cum`, `official_ulpin`, `candidate_ulpin`, `status`, `is_verified` | **Mostly not consumed.** The floor list previously rendered only `units.length`; a floor's own candidate ULPIN is now surfaced. Heights/areas per floor are still fetched and dropped. |
| `/buildings/{id}/structure` | `floors[].units[].*` (unit_type, area_sqm, volume_cum, is_occupied, official_ulpin, candidate_ulpin, status, is_verified, ml_derived) | **Not consumed.** The unit-level hierarchy — the core of PS 26011 — is returned by the API and rendered only as a count. This is the single largest remaining UI gap. |
| `/buildings/{id}/geometry` | `geometry_3d_lod2` | **Not consumed.** The reconstructed LoD2 solid is fetched and discarded; the UI re-extrudes the 2D footprint instead. |
| `/buildings/{id}/geometry` | `bounds`, `elevation_m`, `source_crs`, `processing_crs`, `footprint_wkt` | Not consumed. |
| `/ingest/location` | `disclaimers`, `skipped_reasons`, `height_source`, `floor_source`, `osm_tags`, `source_url` | `skipped_reasons`/provenance summary now surfaced in the status line; `source_url` and `osm_tags` are stored for audit but not yet rendered. |

### 5.3 Fields the frontend needs but the backend does **not** return

| Frontend field | Reality |
|---|---|
| `BuildingInfo.occupancy` | Hard-set to `"Not available"` in `MapboxSpace`. There is no ownership/occupancy source in this system, by design (privacy). Correct as-is. |
| `BuildingInfo.energyRating` | Hard-set to `"N/A"`. No energy data source exists. Correct as-is, though the rail still renders it. |
| `BuildingInfo.category` | Mapped from Mapbox feature class, not from the backend. `building_type` (now displayed) is the honest replacement. |
| `flats` (unit count) | Derived in the frontend by summing `structure.floors[].units.length`, falling back to `lookup.units_count`. Works, but duplicates backend state; a `units_count` on the structure response would be cleaner. |

---

## 6. Scaling from one building to nationwide

**What is already general.** `POST /api/v1/ingest/location` takes *any* coordinate in India
(rejected outside 68.0–97.5 E / 6.5–37.5 N before any network call), fetches real footprints, runs
the same ML path, and persists the same hierarchy. The Taj run is one invocation, not a special
case. Nothing in `/spatial/*` is region-specific.

**One inconsistency fixed for new imports, deliberately not back-filled:** the older `POST /api/v1/datasets/import-buildings-geojson` path built its ULPIN segments by string slicing (`district[:2]`, `village[:6]`), so the six pre-existing seed records carry identifiers such as `MA-MU-AND-KURLA0-P-35CF46BC-B1`. Those do **not** satisfy `CANDIDATE_ULPIN_REGEX` (the district segment must be 2 digits) and are therefore reported as syntactically INVALID by `/api/v1/ulpin/validate`, even after the `-B` fix. The importer now routes every code segment through `app/services/cadastral_codes.py`, so **every new import produces a format-valid candidate ULPIN** (two tests pin both the old failure and the new behaviour). The six historical rows are left exactly as they are on purpose: rewriting an existing identifier is a cadastral decision, not a code cleanup, and the `PARCEL-<xx>-nnnnn` natural key must stay stable or a re-import would create duplicate parcels.

**What has to change next, in rough priority order:**

1. **Bulk ingestion instead of per-coordinate calls.** One Overpass query per building is the
   bottleneck (and the best way to get rate-limited). For a district, fetch once with a bounding-box
   query (`way[building](south,west,north,east);out geom tags;`) — Geofabrik's India extract
   (`ml-engine/datasets/manifests/osm_india_buildings.json` already references it) gives the whole
   country as a PBF with no rate limits. Both go through the identical parse → ML → persist path.
2. **Real heights.** OSM `height` is rare; `building:levels` is common but coarse. Add a DSM
   source (Bhuvan CartoDEM/Bhuvan 3D, or DSMs the ML engine's `estimate_from_ndsm()` already
   supports) and route it through `EvidenceFusionEngine` so a lidar/DSM height outranks a
   levels-derived one. The evidence plumbing (`evidence[]` with per-source reliability and the
   `lidar/dsm/dem` weights in `fusion/engine.py`) is already there.
3. **Real parcel boundaries.** A building footprint is not a cadastral parcel. Plug a real
   cadastral vector source (state Bhu-Naksha/ULPIN layers, Bhuvan, or the Survey of India dataset
   you mentioned) into the ingestion step so `parcels.geometry_2d` is surveyed rather than derived —
   and make that the *first* thing to replace, because parcel geometry is the legal anchor.
4. **Cadastral codes from a real authority table.** Bundle the LGD directory (states/districts/
   sub-districts/villages) and reverse-geocode `(lat, lon)` → codes. Until then `cadastral_codes.py`
   labels its deterministic segments `name_hash`, and the operator can pass real codes (they win).
5. **Async job queue.** 438 unit rows per building is fine; 500 k buildings is not. `AsyncJob`
   already exists (`app/db/models/job.py`, `/api/v1/jobs.py`) and `MLIngestionService` already
   updates `AsyncJob.status/progress/result` — wire ingestion into it and return a job id instead of
   blocking the request.
6. **Versioning and change detection.** The models already carry `version`/`valid_from`/`valid_to`/
   `is_active`/`expire()`/`create_new_version()`. Re-ingesting a changed footprint should call
   `create_new_version()` rather than mutate, and the ML change-detection task
   (`ml-engine/src/change_detection/`) should flag it. Today re-ingestion is a no-op for an
   unchanged object, which is the safe default but will hide real-world change.
7. **Throughput and storage.** Ingest in batches of a few hundred with `COPY`/`executemany` instead
   of per-row `UPDATE … ST_GeomFromText`, keep the 10-minute Overpass cache for demo reruns, and
   remember that units multiply rows ~70× per floor for large buildings — consider generating units
   lazily on drill-down rather than eagerly at ingest.
8. **Provenance at scale.** Every record already writes a `ProvenanceRecord` with the OSM reference,
   input hash, licence, and height/floor source. Keep that: nationwide coverage is only defensible
   if any single record can be traced back to its source object or labelled ML-derived.

---

## Appendix — how to reproduce from a clean checkout

```bash
# 1. Infrastructure (Docker Desktop must already be running)
docker start 3d-mapping-db-1 3d-mapping-redis-1        # `docker compose up -d` hangs here
python -m alembic upgrade head                          # head: 003_dataset_registry_columns

# 2. Enable the ML engine path (in .env)
ML_ENGINE_ENABLED=true

# 3. Services
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123          # backend
cd ml-engine && python -m uvicorn src.server:app --host 127.0.0.1 --port 8001
cd frontend && npx vite --port 3000 --host 127.0.0.1

# 4. Tests
python -m pytest -q                                     # 177 passed
cd ml-engine && ../.venv/Scripts/python.exe -m pytest tests -q   # 101 passed, 1 skipped
```

**Two operational gotchas that cost real time here:**

- The ML engine's `/generate/vertical-units` has **no** in-process fallback (unlike
  `process_parcel`), so units are only produced when the ML service is actually listening on
  `ML_ENGINE_URL`. If it is down, ingestion still succeeds and stores the real geometry, floors, and
  heights — re-run the same request later and the units are backfilled.
- A **stale dev server on port 8123** silently serves the old routes (the new one fails to bind with
  `WinError 10048` and exits). Check `netstat -ano | grep :8123` and kill the old PID before
  concluding a route is missing.

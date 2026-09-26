# Deterministic 3D ULPIN + Interactive 3D Selection — Final Validation Report

Spec: SIH 2026 PS26011 — "3D ULPIN Generation and Vertical Property Mapping System".
Scope of this change: add a **deterministic, versioned 3D ULPIN system** and
**interactive building / floor / unit selection** to the existing repository
**without rewriting it**. All numbers, identifiers and statuses below were
observed on this machine against the live stack (PostGIS 3.4 + FastAPI on
`127.0.0.1:8123`). Nothing untested is claimed as working.

---

## 1. Files inspected (before any edit)

Backend
- `app/services/ulpin.py` (legacy generator — kept working)
- `app/db/models/ulpin.py` (`ULPINRecord`, `ULPINStatus`)
- `app/db/models/property.py` (`Parcel`, `Building`, `Floor`, `Unit`, `ScientificStatus`)
- `app/integrations/ml_engine/mapper.py`, `adapter.py`, `client.py`, `contracts.py`
- `app/services/on_demand_ingest.py`, `cadastral_codes.py`
- `app/api/v1/{buildings,floors,units,spatial,search,ulpin,deps,ingest,datasets}.py`
- `app/schemas/{property,ulpin,common}.py`
- `alembic/versions/001_initial_schema.py`, `003_dataset_registry_columns.py`
- `tests/conftest.py`, `tests/integration/test_building_structure.py`,
  `tests/integration/test_ml_e2e_integration.py`

Frontend
- `src/api/strataBackend.ts`, `src/state/areaStore.ts`
- `src/three/MapboxSpace.tsx`, `src/three/classifyFeature.ts`
- `src/components/map/SelectMap.tsx`, `src/components/map/SearchBar.tsx`
- `src/components/scene/{BuildingIsolateScene,IsolatedMapboxObject}.tsx`
- `src/components/panels/BuildingSidebar.tsx`, `src/ui/App.tsx`

## 2. Files modified

| File | Change |
|---|---|
| `app/services/ulpin_3d.py` | *(new — see §3)* |
| `app/services/geometry_canonical.py` | *(new — see §3)* |
| `app/db/models/ulpin.py` | `candidate_ulpin` widened `String(60)` → `String(120)`; added `algorithm_version`, `canonicalization_version`, `object_type` |
| `alembic/versions/004_ulpin_3d_columns.py` | *(new migration)* |
| `app/integrations/ml_engine/mapper.py` | ML `volume_id` is **provenance only** — no longer written to `candidate_ulpin` at building/floor/unit level |
| `app/api/v1/ulpin.py` | added `POST /ulpin/3d/sync/{building_id}`, `GET /ulpin/3d/validate/{ulpin}`, `GET /ulpin/3d/{ulpin}` |
| `app/api/v1/buildings.py` | `/buildings/{id}/structure` now materialises (idempotently) and returns 3D ULPINs — guarded, best-effort, never fails the read |
| `app/schemas/property.py` | added `three_d_ulpin`, `parcel_three_d_ulpin`, `object_type`, `algorithm_version`, `canonicalization_version`, `three_d_ulpin_status`, `floor_code`, `z_min_m`, `z_max_m` to the structure schemas |
| `app/services/on_demand_ingest.py` | seeds the 3D ULPIN hierarchy after a successful ingest (best-effort) |
| `frontend/src/api/strataBackend.ts` | types for the new fields |
| `frontend/src/state/areaStore.ts` | added `selectedFloorId`, `selectedUnitId`, `setSelectedFloorId`, `setSelectedUnitId`, `clearFloorUnitSelection` |
| `frontend/src/components/scene/BuildingIsolateScene.tsx` | clickable floor list, floor information panel, unit list + unit information panel, 3D ULPIN rows |
| `frontend/src/components/scene/IsolatedMapboxObject.tsx` | floor click → floor id; selected floor highlighted (amber) and lifted |
| `frontend/src/components/panels/BuildingSidebar.tsx` | "3D ULPIN — System Generated" block + explicit "Official ULPIN: Not supplied / Not verified" |
| `frontend/src/three/MapboxSpace.tsx` | clears floor/unit selection on a new click; shows the 3D ULPIN in the isolation badge |
| `tests/integration/test_ml_e2e_integration.py` | assertions updated to the now-mandated behaviour (volume_id is provenance, not an identifier) |

## 3. Files created

- `app/services/geometry_canonical.py` — `CANON_V1` canonicalization + `bucket()`.
- `app/services/ulpin_3d.py` — `3D_GEOMETRY_HASH_V1` generator + `ULPIN3DService`.
- `alembic/versions/004_ulpin_3d_columns.py` — additive migration.
- `tests/unit/test_geometry_canonicalization.py` — 14 tests (cases A–E + edges).
- `tests/unit/test_ulpin_3d.py` — 21 tests (cases D–O + collision + API guards).

## 4. Existing files intentionally untouched

- `app/services/ulpin.py` — legacy service unmodified (verified by test).
- `app/db/models/property.py` — no new columns/tables on Parcel/Building/Floor/Unit.
- `app/api/v1/{floors,units,spatial,search,parcels,ingest}.py` — already provided the
  hierarchy reads; reused rather than duplicated.
- `ml-engine/**` — no ML-engine source changes.
- `app/db/models/ulpin.py` `ULPINRecord` table itself — reused, not duplicated;
  legacy rows keep `algorithm_version = NULL`.
- Frontend 3D engine (Mapbox GL + react-map-gl) — kept; interaction added to it.

## 5. Database migrations

`004_ulpin_3d_columns` (down_revision `003_dataset_registry_columns`):

```
ALTER COLUMN ulpin_records.candidate_ulpin TYPE varchar(120)   -- 62–78 char 3D ULPINs
ADD COLUMN ulpin_records.algorithm_version          varchar(50)  NULL
ADD COLUMN ulpin_records.canonicalization_version   varchar(30)  NULL
ADD COLUMN ulpin_records.object_type                varchar(30)  NULL
CREATE INDEX ix_ulpin_records_algorithm_version
CREATE INDEX ix_ulpin_records_entity_algorithm
```

Applied and round-tripped on the live database:

```
$ python -m alembic current
004_ulpin_3d_columns (head)
```

Verified column widths afterwards: `candidate_ulpin = 120`, `algorithm_version = 50`,
`canonicalization_version = 30`, `object_type = 30`.

> The `varchar(60)` → `varchar(120)` widen was **required**: live testing produced the
> 62-character identifier
> `3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-BBB2XPWZ5-X00-U00000000-X7ZC` and PostgreSQL
> rejected it with `StringDataRightTruncationError`. Worst case for a 10-character
> state/district is 78 characters.

## 6. ULPIN algorithm

```
3DULPIN-01-IN-{STATE}-{DISTRICT}-{PARCEL_ID}-{BUILDING_ID}-{FLOOR_CODE}-{UNIT_ID}-{CHECKSUM}
```

| Segment | Rule |
|---|---|
| `PARCEL_ID` | `"P"` + Base32(SHA256(`3D_GEOMETRY_HASH_V1`\|PARCEL\|country\|state\|district\|admin context\|canonical parcel geometry)) [12 chars] |
| `BUILDING_ID` | `"B"` + Base32(SHA256(…\|BUILDING\|parcel_id\|canonical footprint\|`bucket(height, 0.5)`)) [8 chars] |
| `FLOOR_CODE` | not hashed: `F00` ground, `F01..F99` above ground, `B01..` basement, `E01..` elevated |
| `UNIT_ID` | `"U"` + Base32(SHA256(…\|UNIT\|building_id\|floor_code\|canonical unit geometry\|`bucket(z_min,0.1)`\|`bucket(z_max,0.1)`)) [8 chars] |
| `CHECKSUM` | first 4 Base32 chars of SHA256(full id without checksum) |

- `algorithm_version = "3D_GEOMETRY_HASH_V1"`, `canonicalization_version = "CANON_V1"`.
- No random UUID, timestamp, auto-increment, request id or ML run id is ever part of an id.
- Aggregate levels use provably-unreachable sentinels: `B00000000` (no building),
  `X00` (no floor), `U00000000` (no unit) — the digit `0` is **not** in the Base32
  alphabet `A-Z2-7`, and `X00` cannot be produced by the `F/B/E + %02d` floor derivation.
- `validate_3d_ulpin(ulpin) -> bool` re-parses every segment and recomputes the checksum.
- **Collision handling:** no `-2` suffix. On a clash the registry is checked first (same
  entity ⇒ idempotent reuse), and a genuine clash is logged at `CRITICAL` and resolved by
  deterministically widening the hash (`+4` chars per step, ladder `0/4/8/12`); the DB
  `UNIQUE` constraint remains authoritative and a rejected write raises
  `ULPIN3DCollisionError` — nothing is overwritten or randomised.

### Live output (real Taj Mahal Palace Hotel, Apollo Bandar, Mumbai)

```
building 3D ULPIN : 3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-BBB2XPWZ5-X00-U00000000-X7ZC
parcel   3D ULPIN : 3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-B00000000-X00-U00000000-WS6N
floor F00         : 3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-BBB2XPWZ5-F00-U00000000-VR2H   (z 0.0–3.2)
floor F01         : 3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-BBB2XPWZ5-F01-U00000000-H44I   (z 3.2–6.4)
floor F02..F05    : …-F02… / …-F03… / …-F04… / …-F05…                              (up to z 19.2)
official_ulpin    : None        is_authoritative: False      status: CANDIDATE
```

Determinism observed: three consecutive `/structure` reads returned the identical
building id, with the first call at 0.27 s (materialising) and later calls at 0.16 s (reuse).

## 7. Collision analysis

Base32 (RFC 4648, unpadded) carries **5 bits per character**.

| Segment | Chars | Effective bits | Space |
|---|---|---|---|
| `PARCEL_ID` | 12 | 60 | 1.15 × 10¹⁸ |
| `BUILDING_ID` | 8 | 40 | 1.10 × 10¹² |
| `UNIT_ID` | 8 | 40 | 1.10 × 10¹² |
| `CHECKSUM` | 4 | 20 | 1.05 × 10⁶ |

Birthday bound: expected collisions ≈ `n² / (2 · 2^b)`.

- **Parcel, global scope (b = 60).** At a national estimate of n = 3 × 10⁸ parcels:
  `(3e8)² / (2 · 2^60) ≈ 0.039` — a **~3.9% chance of at least one** parcel-parcel
  collision somewhere in the country. That is tolerable *because it cannot be silent*:
  the `UNIQUE` constraint fires, `CRITICAL` is logged, and the identifier is widened to
  16 chars (80 bits), dropping the expectation to `(3e8)² / (2 · 2^80) ≈ 3.7 × 10⁻⁸`.
  Parcel length was therefore kept at the spec's preferred 12 (the spec asked to verify
  mathematically and only increase if unsafe — 12 + deterministic escalation is safe).
- **Building, hierarchically scoped (b = 40).** `building_id` is seeded with the parent
  `parcel_id`, so its collision *domain is one parcel*, not the nation. At ≤ 10³ buildings
  in a parcel: `10⁶ / 2.2 × 10¹² ≈ 4.5 × 10⁻⁷`. Even a pathological 10⁵-building parcel
  gives `4.5 × 10⁻³`, still caught and widened. Crucially the national building count
  (~3 × 10⁸) **does not enter this bound** — different parcels cannot collide.
- **Unit, hierarchically scoped (b = 40).** Seeded with `building_id` + `floor_code`:
  at ≤ 10² units on a floor, `10⁴ / 2.2 × 10¹² ≈ 4.5 × 10⁻⁹`.

Hierarchical scoping is what makes short segments safe: effective addressing space is
**60 bits globally** for a parcel, **60 + 40 bits** for a building, and **60 + 40 + 40 bits**
for a unit, because each child segment is only ever compared against siblings of the same
parent.

Checksum: 4 Base32 chars = 20 bits, so a random single-character mutation is accepted with
probability `2⁻²⁰ ≈ 9.5 × 10⁻⁷` (~99.9999% rejected). Verified exhaustively:
every non-dash position of a valid identifier was mutated and all mutations were rejected.

## 8. Geometry canonicalization result (`CANON_V1`)

Documented contract: EPSG:4326, GeoJSON axis order `[lon, lat]` (never swapped), XY
quantized to 1e-7° (~1.1 cm) with `Decimal ROUND_HALF_UP`, `-0.0` collapsed to `0.0`,
`make_valid` applied, exterior rings CCW / holes CW, every ring rotated so the
lexicographically smallest coordinate is first, MultiPolygon components sorted, non-areal
parts dropped, serialized as `MULTIPOLYGON[(ring,hole);(ring)]`.

Verified identical canonical strings for: reversed vertex order, rotated start vertex,
reversed+rotated, reversed MultiPolygon component order, hole reordering, and WKT vs GeoJSON.
A point/line or empty geometry raises `GeometryCanonicalizationError` (never a silent hash).

`bucket(value, step)` is a shared utility with an explicit half-step rule (half rounds away
from zero); `21.73 m` and `21.74 m` both bucket to `21.5 m` at the 0.5 m height step, and
`19.21`/`19.24` bucket together at the 0.1 m Z step.

## 9. ML integration result

- `app/integrations/ml_engine/mapper.py` no longer assigns
  `candidate_ulpin = output.volume_id` at building, floor or unit level
  (it previously wrote both `output.volume_id` and `f"{volume_id}-FL{n:02d}"`).
- `volume_id` remains stored in `metadata_["volume_id"]` as **provenance/lineage**.
- Test guard `test_l_volume_id_is_never_a_3d_ulpin` both checks behaviour and scans the
  mapper source so the old pattern cannot be reintroduced.
- The 3D ULPIN is only generated where real geometry **and** real vertical information
  exist: a building with no height, or a unit with no stored geometry, gets **no** id and
  an explicit reason in `skipped`.

## 10. API changes

| Route | Purpose |
|---|---|
| `GET /api/v1/buildings/{id}/structure` (extended) | now also returns `three_d_ulpin`, `parcel_three_d_ulpin`, `object_type`, `algorithm_version`, `canonicalization_version`, `three_d_ulpin_status`, per-floor `three_d_ulpin`/`floor_code`/`z_min_m`/`z_max_m`, per-unit `three_d_ulpin`/`object_type`/`z_min_m`/`z_max_m` |
| `POST /api/v1/ulpin/3d/sync/{building_id}` | idempotently materialise the 3D ULPIN hierarchy; returns per-entity results + `skipped` reasons |
| `GET /api/v1/ulpin/3d/validate/{ulpin}` | recompute the checksum, report registry match |
| `GET /api/v1/ulpin/3d/{ulpin}` | registry lookup for a 3D ULPIN |
| `GET /api/v1/floors/{id}`, `GET /api/v1/floors/{id}/units`, `GET /api/v1/buildings/{id}/floors`, `GET /api/v1/units/{id}` | reused as-is (already existed — no duplicates created) |

## 11–14. Building / floor / unit click and 3D isolation

- **Building click** (`MapboxSpace.tsx`): existing Mapbox `queryRenderedFeatures` +
  backend `pointLookup` flow retained. It now clears `selectedFloorId`/`selectedUnitId`,
  isolates the record with a real PostGIS footprint extruded to the stored height (never a
  synthesised box), and the isolation badge shows the building's 3D ULPIN.
- **Floor click**: floors render as one `fill-extrusion` per real floor
  (`IsolatedMapboxObject`). Clicking an extrusion resolves `selected-floor-{i}` →
  `orderedFloors[i].id`, so the selection maps to a real backing floor id. The selected
  floor turns amber, is lifted 1.5 m and stays recognisable as part of the building
  (the pre-existing exploder slider still works additively). Clicking empty space clears.
- **Floor information panel** (`BuildingIsolateScene`): renders floor number, floor code,
  3D ULPIN (badged `SYSTEM GENERATED`), floor type, building id, parcel id, `z_min`/`z_max`,
  floor height, floor area, unit count and status. Missing values render `Not available`
  rather than an invented value.
- **Unit click**: the floor panel lists that floor's real units; clicking one opens a unit
  panel with 3D ULPIN, unit type, area, vertical range, object type and status. When a unit
  has no stored 3D geometry the panel says so explicitly and the 3D ULPIN is `Not generated`.
- **Sidebar**: new "3D ULPIN — System Generated" block always renders the label
  *SYSTEM GENERATED* with the algorithm/canonicalization version, plus an explicit
  **Official ULPIN: Not supplied / Not verified** row. A generated value is never shown
  under "Official ULPIN".
- State lives in the existing Zustand store (no new state framework).

## 15. Taj prototype status

Real data, real PostGIS, no fabricated geometry:

| Item | Observed |
|---|---|
| Lookup | `GET /spatial/search?lat=18.92170&lon=72.83320` → building `Taj Mahal Palace`, `match_type: inside`, height `19.2 m`; parcel `OSM-W28846517`, `inside` |
| 3D ULPIN | `3DULPIN-01-IN-MH-30-PMSYEHQLFKFRS-BBB2XPWZ5-X00-U00000000-X7ZC`, status `SYSTEM GENERATED` |
| Floors | 6 (`F00`–`F05`) each with its own 3D ULPIN and real `z` range 0.0 → 19.2 m |
| Units | 438 candidate units exist; **no unit 3D ULPIN** because `units.geometry_3d` is not stored — reported in `skipped`, not fabricated |
| `official_ulpin` | `None` |
| Validation | `valid: true`, registry match, `object_type: BUILDING` |
| Tamper test | one-character mutation → `valid: false` |
| Sync endpoint | `201`, 6 floors, 0 units, explicit skip reasons |

**Real Taj footprint geometry was available** (OpenStreetMap way 28846517, ingested in the
earlier verified ingestion work), so no "unavailable" stop was required and no geometry was
invented.

## 16. Tests passed

- **Backend: 212 passed, 0 failed** (`python -m pytest -q`, 12.3 s).
  - 177 pre-existing tests still pass (no regressions).
  - `tests/unit/test_geometry_canonicalization.py` — 14 passed (cases A, B, C, D, E,
    half-step rule, axis order, `make_valid` bow-tie, hole ordering, WKT↔GeoJSON, empty
    geometry, negative zero, version pin).
  - `tests/unit/test_ulpin_3d.py` — 21 passed (cases D–O, exhaustive single-character
    mutation sweep, checksum fidelity, collision widening, sentinels, floor codes,
    unit id sensitivity, service-level registry honesty, API schema/route guards, legacy
    compatibility).
- **Frontend: `npx tsc -b` clean; `npx vite build` succeeded** (1734 modules).
- **Live end-to-end**: login → `pointLookup` → `/structure` → `/ulpin/3d/validate` →
  tamper → `/ulpin/3d/sync` → `/ulpin/3d/{ulpin}` all exercised against the running stack.

## 17. Tests failed

None. The only test file whose expectation changed is
`tests/integration/test_ml_e2e_integration.py`, whose assertions encoded the *now-forbidden*
behaviour (`candidate_ulpin.startswith("VOL-")`). It was updated to assert the mandated
behaviour instead: `candidate_ulpin is None` and `metadata["volume_id"].startswith("VOL-")`.
No test was deleted.

## 18. Remaining limitations (honest list)

1. **Units have no 3D geometry in the data model yet.** `units.geometry_3d` is NULL for
   every ingested unit, so per §17/§34 no unit 3D ULPIN is generated for them. The unit
   code path and the unit panel are implemented and unit-level tests pass using real unit
   geometry WKT; the live Taj units stay `Not generated` until unit geometry is produced.
2. **Buildings without a height get no 3D ULPIN.** 13 of the ingested Mumbai buildings
   (`height_m` NULL because OSM has neither `height` nor `building:levels`) correctly sit
   in `skipped`. Wiring a government DSM/CartoDEM height source is the next step.
3. **`official_ulpin` remains NULL everywhere.** No official dataset or API was supplied,
   so nothing authoritative can be joined or fabricated.
4. **Browser click-through partially verified.** Verified in the browser: the app builds,
   boots, authenticates, reaches the 3D City step with backend records loaded, and the
   building-click → isolated 3D view → information panel path runs, correctly showing
   `3D ULPIN (SYSTEM GENERATED): Not generated` and
   `OFFICIAL ULPIN (GOVERNMENT): Not supplied / Not verified` for a basemap parcel with no
   backend record. The Taj-specific click-through (click the Taj → click floor `F03` →
   floor panel) was **not** completed under automation: the harness has no real
   drag/coordinate-click input, and Mapbox GL ignores synthetic wheel/pan gestures, so the
   camera could not be steered onto the Taj. The same code path was validated at the API
   and unit-test level. To see it manually: open http://127.0.0.1:3000, draw a box over the
   Gateway of India, then click the Taj footprint and any floor extrusion. (The app no
   longer has a sign-in screen; this report was written while it still did.)
5. **`GET /buildings/{id}/structure` performs the one-off materialisation write.** It is
   idempotent and cheap after the first call (0.27 s → 0.16 s), but a purist would move the
   initial generation into an explicit job rather than a read.
6. **Six legacy seed candidate ULPINs still fail `validate_ulpin`** by design (they were
   string-sliced); they were intentionally left untouched rather than rewriting identifiers.
7. **`docker-compose.yml` still contains a `SECRET_KEY` fallback**, and the old key remains
   in git history; rotation is the mitigation. No secret was printed, read or modified.

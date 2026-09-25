"""
Deterministic, versioned 3D ULPIN generator (``3D_GEOMETRY_HASH_V1``).

Covers spec cases D-O:
  D. 21.73 m vs 21.74 m -> same bucket AND same building ID
  E. different height bucket -> different building ID
  F. single-character mutation -> validation fails
  G. identical inputs -> identical 3D ULPIN (determinism)
  H. different building geometry under one parcel -> different building ID
  I. different parent parcel -> different building identity
  J. official_ulpin stays NULL unless supplied externally
  K. generated 3D ULPIN has is_authoritative=False
  L. ML volume_id is never used as the 3D ULPIN
  M. floor click metadata is correct (floor code, z range, ULPIN)
  N. building click metadata is correct
  O. unit click metadata exists when real unit geometry exists
"""
import pathlib
import re
import uuid

import pytest

from app.db.models.property import Building, Floor, Parcel, Unit
from app.db.models.ulpin import ULPINRecord
from app.services.geometry_canonical import canonicalize_geometry
from app.services.ulpin_3d import (
    ALGORITHM_VERSION,
    BUILDING_HASH_CHARS,
    CANONICALIZATION_VERSION,
    CHECKSUM_CHARS,
    OBJECT_BUILDING,
    OBJECT_LAND_PARCEL,
    OBJECT_TYPES,
    PARCEL_HASH_CHARS,
    ULPIN_3D_FORMAT,
    ULPIN3DService,
    assemble_3d_ulpin,
    building_id,
    checksum,
    floor_code,
    is_3d_ulpin,
    parcel_id,
    parse_3d_ulpin,
    unit_id,
    validate_3d_ulpin,
)
from tests.conftest import MockAsyncSession, MockDbStore

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Real-ish footprint rectangle (Taj Mahal Palace Hotel scale, Apollo Bandar).
FOOTPRINT_A = {
    "type": "Polygon",
    "coordinates": [[
        [72.83300, 18.92160],
        [72.83340, 18.92160],
        [72.83340, 18.92190],
        [72.83300, 18.92190],
        [72.83300, 18.92160],
    ]],
}
FOOTPRINT_B = {
    "type": "Polygon",
    "coordinates": [[
        [72.83300, 18.92160],
        [72.83355, 18.92160],
        [72.83355, 18.92195],
        [72.83300, 18.92195],
        [72.83300, 18.92160],
    ]],
}
PARCEL_GEO = {
    "type": "Polygon",
    "coordinates": [[
        [72.83280, 18.92140],
        [72.83360, 18.92140],
        [72.83360, 18.92210],
        [72.83280, 18.92210],
        [72.83280, 18.92140],
    ]],
}
PARCEL_GEO_OTHER = {
    "type": "Polygon",
    "coordinates": [[
        [72.83480, 18.92340],
        [72.83560, 18.92340],
        [72.83560, 18.92410],
        [72.83480, 18.92410],
        [72.83480, 18.92340],
    ]],
}

CANON_FOOTPRINT_A = canonicalize_geometry(FOOTPRINT_A)
CANON_FOOTPRINT_B = canonicalize_geometry(FOOTPRINT_B)
CANON_PARCEL = canonicalize_geometry(PARCEL_GEO)
CANON_PARCEL_OTHER = canonicalize_geometry(PARCEL_GEO_OTHER)

PARCEL_ID = parcel_id(
    state="MH", district="MUM", admin_context="Maharashtra/Mumbai/Colaba/OSM", canonical_geometry=CANON_PARCEL
)
PARCEL_ID_OTHER = parcel_id(
    state="MH", district="MUM", admin_context="Maharashtra/Mumbai/Colaba/OSM-2", canonical_geometry=CANON_PARCEL_OTHER
)


def test_layout_constants_are_the_documented_baseline():
    """Base32 = 5 bits/char: 12/8/8/4 characters per the documented baseline."""
    assert PARCEL_HASH_CHARS == 12
    assert BUILDING_HASH_CHARS == 8
    assert CHECKSUM_CHARS == 4
    # 12 chars * 5 bits = 60 effective bits for the parcel segment.
    assert PARCEL_HASH_CHARS * 5 == 60
    assert BUILDING_HASH_CHARS * 5 == 40
    assert ALGORITHM_VERSION == "3D_GEOMETRY_HASH_V1"
    assert CANONICALIZATION_VERSION == "CANON_V1"
    assert len(OBJECT_TYPES) >= 9  # extensible taxonomy, not apartments-only


# ------------------------------------------------------------------ D + E ---- #


def test_d_heights_in_one_bucket_share_a_building_id():
    a = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=21.73)
    b = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=21.74)
    assert a == b
    assert a.startswith("B") and len(a) == 1 + BUILDING_HASH_CHARS


def test_e_different_height_bucket_changes_the_building_id():
    a = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=21.74)
    b = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=22.10)
    assert a != b


# --------------------------------------------------------------------- F ---- #

FULL = assemble_3d_ulpin(
    state="MH",
    district="MUM",
    parcel=PARCEL_ID,
    building=building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=19.2),
    floor="F05",
    unit=unit_id(
        parent_building_id="B3F8D1A2",
        parent_floor_code="F05",
        canonical_unit_geometry=CANON_FOOTPRINT_A,
        z_min=16.0,
        z_max=19.2,
    ),
)


def test_full_identifier_shape_and_validity():
    assert FULL.startswith("3DULPIN-01-IN-MH-MUM-")
    assert validate_3d_ulpin(FULL) is True
    segments = parse_3d_ulpin(FULL)
    assert segments is not None
    assert segments["parcel_id"] == PARCEL_ID
    assert segments["floor_code"] == "F05"
    assert len(segments["checksum"]) == CHECKSUM_CHARS


def test_f_any_single_character_mutation_fails_validation():
    assert validate_3d_ulpin(FULL) is True
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    failures = 0
    for index, char in enumerate(FULL):
        if char == "-":
            continue
        replacement = "A" if char != "A" else "B"
        mutated = FULL[:index] + replacement + FULL[index + 1:]
        if mutated == FULL:
            continue
        assert validate_3d_ulpin(mutated) is False, f"mutation at {index} ({replacement}) was accepted"
        failures += 1
    assert failures > 40  # every non-dash position was actually exercised
    assert alphabet  # documented alphabet reference


def test_f2_checksum_tampering_and_truncation_fail():
    body, _, existing = FULL.rpartition("-")
    wrong = "AAAA" if existing != "AAAA" else "BBBB"
    assert validate_3d_ulpin(f"{body}-{wrong}") is False
    assert validate_3d_ulpin(FULL[:-1]) is False
    assert validate_3d_ulpin(FULL + "-EXTRA") is False
    assert validate_3d_ulpin("") is False
    assert validate_3d_ulpin("not-a-ulpin") is False
    assert checksum(body) == existing  # recomputation is stable


# --------------------------------------------------------------------- G ---- #


def test_g_identical_inputs_produce_identical_identifiers():
    def build():
        p = parcel_id(state="MH", district="MUM", admin_context="ctx", canonical_geometry=CANON_PARCEL)
        b = building_id(parent_parcel_id=p, canonical_footprint=CANON_FOOTPRINT_A, height_m=19.2)
        return assemble_3d_ulpin(state="MH", district="MUM", parcel=p, building=b, floor="F00", unit=None)

    assert build() == build()
    # Vertex order / start vertex must not change the result either (via CANON).
    reordered = canonicalize_geometry({"type": "Polygon", "coordinates": [list(reversed(FOOTPRINT_A["coordinates"][0]))]})
    assert reordered == CANON_FOOTPRINT_A


# ----------------------------------------------------------------- H + I ---- #


def test_h_different_building_geometry_changes_the_building_id():
    a = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=19.2)
    b = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_B, height_m=19.2)
    assert a != b


def test_i_different_parent_parcel_changes_building_identity():
    a = building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=19.2)
    b = building_id(parent_parcel_id=PARCEL_ID_OTHER, canonical_footprint=CANON_FOOTPRINT_A, height_m=19.2)
    assert a != b
    assert PARCEL_ID != PARCEL_ID_OTHER


# --------------------------------------------------------------------- L ---- #


def test_l_volume_id_is_never_a_3d_ulpin():
    volume_id = "VOL-MH-MUM-2026-009876-BUILDING"
    assert is_3d_ulpin(volume_id) is False
    assert FULL != volume_id
    assert volume_id not in FULL
    assert validate_3d_ulpin(volume_id) is False
    # Source guard: the ML mapper must not assign candidate_ulpin from volume_id.
    source = (REPO_ROOT / "app" / "integrations" / "ml_engine" / "mapper.py").read_text(encoding="utf-8")
    for line in source.splitlines():
        if "candidate_ulpin" in line and "=" in line.split("#")[0]:
            assert "volume_id" not in line, line
    assert 'meta["volume_id"]' in source or '"volume_id": output.volume_id' in source


def test_floor_codes_and_aggregate_sentinels():
    assert floor_code(0) == "F00"
    assert floor_code(1) == "F01"
    assert floor_code(12) == "F12"
    assert floor_code(-1) == "B01"
    assert floor_code(2, "elevated") == "E02"
    aggregate = assemble_3d_ulpin(state="MH", district="MUM", parcel=PARCEL_ID, building=None, floor=None, unit=None)
    assert validate_3d_ulpin(aggregate) is True
    assert parse_3d_ulpin(aggregate)["building_id"] == "B00000000"
    assert parse_3d_ulpin(aggregate)["floor_code"] == "X00"
    assert parse_3d_ulpin(aggregate)["unit_id"] == "U00000000"


def test_unit_id_reacts_to_geometry_and_vertical_position():
    base = dict(parent_building_id="B3F8D1A2", parent_floor_code="F05", canonical_unit_geometry=CANON_FOOTPRINT_A)
    a = unit_id(z_min=16.0, z_max=19.2, **base)
    same_bucket = unit_id(z_min=16.04, z_max=19.24, **base)  # 0.1 m buckets
    shifted = unit_id(z_min=16.5, z_max=19.7, **base)
    other_geom = unit_id(parent_building_id="B3F8D1A2", parent_floor_code="F05",
                         canonical_unit_geometry=CANON_FOOTPRINT_B, z_min=16.0, z_max=19.2)
    assert a == same_bucket
    assert a != shifted
    assert a != other_geom


def test_unit_id_requires_real_geometry_and_z_range():
    from app.services.ulpin_3d import ULPIN3DError

    with pytest.raises(ULPIN3DError):
        unit_id(parent_building_id="B3F8D1A2", parent_floor_code="F05",
                canonical_unit_geometry="", z_min=0.0, z_max=3.0)
    with pytest.raises(ULPIN3DError):
        unit_id(parent_building_id="B3F8D1A2", parent_floor_code="F05",
                canonical_unit_geometry=CANON_FOOTPRINT_A, z_min=None, z_max=3.0)


def test_building_id_requires_a_real_height():
    from app.services.ulpin_3d import ULPIN3DError

    with pytest.raises(ULPIN3DError):
        building_id(parent_parcel_id=PARCEL_ID, canonical_footprint=CANON_FOOTPRINT_A, height_m=None)


# ------------------------------------------------------------------ J K M N O #

UNIT_POLY_WKT = (
    "POLYGON Z ((72.83310 18.92170 16.0, 72.83320 18.92170 16.0, "
    "72.83320 18.92180 16.0, 72.83310 18.92180 16.0, 72.83310 18.92170 16.0))"
)


def _seed_hierarchy(*, unit_geometry=UNIT_POLY_WKT):
    store = MockDbStore()
    parcel = Parcel(
        id=uuid.uuid4(),
        parcel_number="OSM-W28846517",
        district="Mumbai",
        taluk="Colaba",
        village="Apollo Bandar",
        state="Maharashtra",
        official_ulpin=None,
        candidate_ulpin=None,
        status="CANDIDATE",
        boundary_wkt=(
            "POLYGON((72.83280 18.92140, 72.83360 18.92140, 72.83360 18.92210, "
            "72.83280 18.92210, 72.83280 18.92140))"
        ),
        source_crs="EPSG:4326",
        is_active=True,
    )
    building = Building(
        id=uuid.uuid4(),
        parcel_id=parcel.id,
        building_name="The Taj Mahal Palace Hotel",
        building_type="hotel",
        floor_count=2,
        height_m=19.2,
        height_confidence=0.7,
        footprint_wkt=(
            "POLYGON((72.83300 18.92160, 72.83340 18.92160, 72.83340 18.92190, "
            "72.83300 18.92190, 72.83300 18.92160))"
        ),
        source_crs="EPSG:4326",
        official_ulpin=None,
        candidate_ulpin=None,
        status="CANDIDATE",
        ml_derived=True,
        ml_model_version="0.1.0",
        is_active=True,
        metadata_={"osm_reference": "way/28846517", "height_source": "osm_building_levels"},
    )
    floors = [
        Floor(
            id=uuid.uuid4(),
            building_id=building.id,
            floor_number=0,
            floor_label="G",
            floor_use="hotel",
            height_above_ground_m=0.0,
            ceiling_height_m=9.6,
            floor_area_sqm=7391.1,
            official_ulpin=None,
            candidate_ulpin=None,
            status="CANDIDATE",
            is_active=True,
        ),
        Floor(
            id=uuid.uuid4(),
            building_id=building.id,
            floor_number=1,
            floor_label="F1",
            floor_use="hotel",
            height_above_ground_m=9.6,
            ceiling_height_m=9.6,
            floor_area_sqm=7391.1,
            official_ulpin=None,
            candidate_ulpin=None,
            status="CANDIDATE",
            is_active=True,
        ),
    ]
    unit = Unit(
        id=uuid.uuid4(),
        floor_id=floors[0].id,
        unit_number="U-01",
        unit_type="residential",
        area_sqm=100.0,
        official_ulpin=None,
        candidate_ulpin=None,
        status="CANDIDATE",
        ml_derived=True,
        ml_confidence_score=0.6,
        is_active=True,
        geometry_3d=unit_geometry,
        metadata_={"volume_id": "VOL-MH-MUM-2026-009876", "unit_delineation": "ML_ENGINE"},
    )
    building.floors = floors
    floors[0].units = [unit]
    floors[1].units = []

    store.save(parcel)
    store.save(building)
    store.save(floors[0])
    store.save(floors[1])
    store.save(unit)
    return store, parcel, building, floors, unit


@pytest.mark.asyncio
async def test_generate_hierarchy_identifiers_and_provenance():
    store, parcel, building, floors, unit = _seed_hierarchy()
    session = MockAsyncSession(store)

    result = await ULPIN3DService(session).sync_building(building.id)

    # N. building click metadata
    assert result["algorithm_version"] == ALGORITHM_VERSION
    assert result["canonicalization_version"] == CANONICALIZATION_VERSION
    assert result["building"]["ulpin"].startswith("3DULPIN-01-IN-MH-")
    assert result["building"]["object_type"] == OBJECT_BUILDING
    assert validate_3d_ulpin(result["building"]["ulpin"]) is True
    # J. official ULPIN never fabricated
    assert result["building"]["official_ulpin"] is None
    # K. never authoritative
    assert result["building"]["is_authoritative"] is False

    # parcel record
    assert result["parcel"]["object_type"] == OBJECT_LAND_PARCEL
    assert result["parcel"]["official_ulpin"] is None
    assert result["parcel"]["is_authoritative"] is False

    # M. floor click metadata — real floor codes and z ranges from stored values
    assert len(result["floors"]) == 2
    f0 = result["floors"][str(floors[0].id)]
    f1 = result["floors"][str(floors[1].id)]
    assert f0["floor_code"] == "F00"
    assert f1["floor_code"] == "F01"
    assert f0["z_min_m"] == 0.0 and f0["z_max_m"] == 9.6
    assert f1["z_min_m"] == 9.6 and f1["z_max_m"] == 19.2
    assert validate_3d_ulpin(f0["ulpin"]) is True
    assert parse_3d_ulpin(f0["ulpin"])["floor_code"] == "F00"

    # O. unit click metadata exists because real unit geometry was stored
    assert len(result["units"]) == 1
    u = result["units"][str(unit.id)]
    assert u["ulpin"].startswith("3DULPIN-01-IN-")  # full identifier, not a bare segment
    assert validate_3d_ulpin(u["ulpin"]) is True
    assert parse_3d_ulpin(u["ulpin"])["floor_code"] == "F00"
    assert u["is_authoritative"] is False
    assert u["official_ulpin"] is None

    # L. the ML volume_id is provenance, never the identifier. (Base32 output can
    # incidentally spell any letters, so compare against the real segments.)
    volume_id = "VOL-MH-MUM-2026-009876"
    assert u["ulpin"] != volume_id
    u_segments = parse_3d_ulpin(u["ulpin"])
    assert volume_id not in set(u_segments.values())
    assert not any(str(v).startswith("VOL-") for v in u_segments.values())

    # Registry rows carry the versioning columns and no official id.
    records = [v for v in store.entities.values() if isinstance(v, ULPINRecord)]
    assert records
    for record in records:
        assert record.official_ulpin is None
        assert record.is_authoritative is False
        assert record.status == "CANDIDATE"
        assert record.algorithm_version == ALGORITHM_VERSION
        assert record.canonicalization_version == CANONICALIZATION_VERSION
        assert record.generation_method == ALGORITHM_VERSION

    # Determinism: re-running the sync yields the identical identifier, and the
    # collision resolver recognises the existing record as its own.
    first = result["building"]["ulpin"]
    result_again = await ULPIN3DService(session).sync_building(building.id)
    assert result_again["building"]["ulpin"] == first


@pytest.mark.asyncio
async def test_no_unit_geometry_means_no_unit_ulpin():
    """Honesty: without real unit geometry nothing is hashed for the unit."""
    store, parcel, building, floors, unit = _seed_hierarchy(unit_geometry=None)
    session = MockAsyncSession(store)

    result = await ULPIN3DService(session).sync_building(building.id)

    assert result["units"] == {}
    reasons = [s for s in result["skipped"] if s["entity"] == "unit"]
    assert reasons and "geometry" in reasons[0]["reason"]
    # The rest of the hierarchy still resolves.
    assert validate_3d_ulpin(result["building"]["ulpin"]) is True


@pytest.mark.asyncio
async def test_building_without_height_gets_no_ulpin():
    store, parcel, building, floors, unit = _seed_hierarchy()
    building.height_m = None  # real OSM footprint, but no vertical information
    session = MockAsyncSession(store)

    result = await ULPIN3DService(session).sync_building(building.id)

    assert result["building"] is None
    skipped = [s for s in result["skipped"] if s["entity"] == "building"]
    assert skipped and "height" in skipped[0]["reason"]


@pytest.mark.asyncio
async def test_collision_is_widened_not_suffixed():
    """A genuine truncated-hash collision widens the hash; it never appends '-2'."""
    store = MockDbStore()
    session = MockAsyncSession(store)
    svc = ULPIN3DService(session)

    other_entity = uuid.uuid4()
    store.save(
        ULPINRecord(
            id=uuid.uuid4(),
            candidate_ulpin="COLLIDES",
            official_ulpin=None,
            entity_type="building",
            status="CANDIDATE",
            building_id=other_entity,
            generation_method=ALGORITHM_VERSION,
            is_authoritative=False,
            legal_disclaimer="test",
        )
    )

    def factory(bonus: int) -> str:
        return "COLLIDES" if bonus == 0 else "COLLIDES" + "A" * bonus

    candidate, report = await svc._resolve_candidate_with_flag(factory, "building", uuid.uuid4())
    assert report["escalated"] is True
    assert candidate == "COLLIDESAAAA"
    assert not candidate.endswith("-2")
    assert report["attempts"][0]["bonus"] == 0


def test_api_schema_exposes_the_click_metadata_fields():
    from app.schemas.property import BuildingStructureOut, FloorStructureOut, UnitStructureOut

    building_fields = BuildingStructureOut.model_fields
    assert "three_d_ulpin" in building_fields
    assert "parcel_three_d_ulpin" in building_fields
    assert "three_d_ulpin_status" in building_fields
    assert "algorithm_version" in building_fields
    assert "canonicalization_version" in building_fields

    floor_fields = FloorStructureOut.model_fields
    for field in ("three_d_ulpin", "floor_code", "z_min_m", "z_max_m", "object_type"):
        assert field in floor_fields, field

    unit_fields = UnitStructureOut.model_fields
    for field in ("three_d_ulpin", "object_type", "z_min_m", "z_max_m"):
        assert field in unit_fields, field


def test_ulpin_3d_endpoints_are_registered():
    from app.main import app

    paths = set(app.openapi().get("paths", {}).keys())
    assert "/api/v1/ulpin/3d/sync/{building_id}" in paths
    assert "/api/v1/ulpin/3d/validate/{ulpin_str}" in paths
    assert "/api/v1/ulpin/3d/{ulpin_str}" in paths


def test_legacy_ulpin_service_is_untouched_and_still_works():
    """Backward compatibility: the legacy service must remain importable + working."""
    from app.services.ulpin import ULPINService

    assert ULPINService.is_candidate_format("MH-30-530-349567-P-9AAF7AD1-B1")
    assert ULPINService.is_official_format("1234567890ABCD")
    legacy = ULPINService.generate_parcel_ulpin(
        state="MH", district="30", taluk="530", village="349567", survey_number="OSM-W28846517"
    )
    assert legacy.startswith("MH-30-530-349567-P-")
    assert re.match(r"^MH-30-530-349567-P-[0-9A-F]{8}$", legacy) is not None

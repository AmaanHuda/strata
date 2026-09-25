"""Offline unit tests for the OpenStreetMap/Overpass integration helpers.

These do NOT hit the network. They pin the parsing rules that decide what real
OSM tags mean, so an ingestion run can be trusted before PostGIS is involved.

Note on the coordinates below: they are obviously-synthetic test values, used
only to exercise the parsers. No test fixture is presented as real cadastral
data — the real footprint verification happens against the live API instead.
"""
import pytest

from app.integrations.osm.overpass import (
    FLOOR_TO_FLOOR_M,
    OverpassClient,
    OverpassError,
    build_around_query,
    build_osm_id_query,
    derive_floor_count,
    derive_height,
    is_within_india,
    parse_building_element,
    pick_target_buildings,
)

SQUARE = [{"lon": 0.0, "lat": 0.0}, {"lon": 0.1, "lat": 0.0},
          {"lon": 0.1, "lat": 0.1}, {"lon": 0.0, "lat": 0.1}, {"lon": 0.0, "lat": 0.0}]


def _way(tags=None, geometry=None, osm_id=1):
    return {
        "type": "way",
        "id": osm_id,
        "tags": tags if tags is not None else {"building": "yes"},
        "geometry": geometry if geometry is not None else SQUARE,
    }


class TestHeightDerivation:
    def test_height_tag_wins_and_is_flagged_real(self):
        height, source = derive_height({"height": "62 m", "building:levels": "6"}, 6)
        assert height == pytest.approx(62.0)
        assert source == "osm_height_tag"

    def test_levels_used_only_when_height_absent_and_is_flagged_derived(self):
        height, source = derive_height({"building:levels": "6"}, 6)
        assert height == pytest.approx(6 * FLOOR_TO_FLOOR_M)
        assert source == "osm_levels_derived"

    def test_no_signal_yields_none_never_a_default(self):
        height, source = derive_height({}, None)
        assert height is None
        assert source == "unavailable"

    @pytest.mark.parametrize("bad", ["-5", "0", "9999", "abc", ""])
    def test_implausible_height_tag_is_rejected(self, bad):
        height, source = derive_height({"height": bad}, None)
        assert height is None
        assert source == "unavailable"


class TestFloorDerivation:
    @pytest.mark.parametrize(
        "raw,expected",
        [("6", 6), ("6.0", 6), ("2;3", 2), ("12", 12)],
    )
    def test_levels_variants(self, raw, expected):
        assert derive_floor_count({"building:levels": raw}) == (expected, "osm_levels_tag")

    @pytest.mark.parametrize("raw", [None, "", "ground", "0", "999"])
    def test_unusable_levels_rejected(self, raw):
        tags = {} if raw is None else {"building:levels": raw}
        assert derive_floor_count(tags)[0] is None


class TestParseBuildingElement:
    def test_full_parse_closes_ring_and_carries_provenance(self):
        building = parse_building_element(
            _way({"building": "yes", "name": "Test Object", "building:levels": "6"}, osm_id=42)
        )
        assert building is not None
        assert building.osm_type == "way"
        assert building.osm_id == 42
        assert building.name == "Test Object"
        assert building.height_m == pytest.approx(6 * FLOOR_TO_FLOOR_M)
        assert building.floor_count == 6
        assert building.outer_ring[0] == building.outer_ring[-1]
        assert building.source_url == "https://www.openstreetmap.org/way/42"
        assert building.to_geojson_polygon()["type"] == "Polygon"

    def test_non_building_element_is_skipped(self):
        assert parse_building_element(_way({"highway": "residential"})) is None

    def test_node_element_is_skipped(self):
        assert parse_building_element({"type": "node", "id": 1, "tags": {"building": "yes"}}) is None

    def test_unclosed_geometry_that_is_degenerate_is_skipped(self):
        way = _way(geometry=[{"lon": 0.0, "lat": 0.0}, {"lon": 0.1, "lat": 0.1}])
        assert parse_building_element(way) is None

    def test_duplicate_consecutive_points_are_removed(self):
        geometry = [
            {"lon": 0.0, "lat": 0.0},
            {"lon": 0.0, "lat": 0.0},
            {"lon": 0.1, "lat": 0.0},
            {"lon": 0.1, "lat": 0.1},
            {"lon": 0.0, "lat": 0.1},
            {"lon": 0.0, "lat": 0.0},
        ]
        building = parse_building_element(_way(geometry=geometry))
        assert len(building.outer_ring) == 5

    def test_evidence_item_points_back_at_the_source_object(self):
        building = parse_building_element(_way(osm_id=7))
        item = building.evidence_item()
        assert "way/7" in item["source"]
        assert item["reliability"] == pytest.approx(0.40)


class TestTargetSelection:
    def _collection(self):
        small = parse_building_element(_way({"building": "yes", "name": "Small Annex"}, osm_id=1))
        big = parse_building_element(
            _way(
                {"building": "yes", "name": "Taj Mahal Palace"},
                geometry=[
                    {"lon": 0.0, "lat": 0.0},
                    {"lon": 0.5, "lat": 0.0},
                    {"lon": 0.5, "lat": 0.5},
                    {"lon": 0.0, "lat": 0.5},
                    {"lon": 0.0, "lat": 0.0},
                ],
                osm_id=2,
            )
        )
        return [small, big]

    def test_name_filter_is_case_insensitive_substring(self):
        picked = pick_target_buildings(self._collection(), name_contains="taj mahal")
        assert [b.osm_id for b in picked] == [2]

    def test_osm_id_filter_selects_one_object(self):
        picked = pick_target_buildings(self._collection(), osm_id=1)
        assert [b.osm_id for b in picked] == [1]

    def test_no_filter_returns_all_largest_first(self):
        picked = pick_target_buildings(self._collection())
        assert [b.osm_id for b in picked] == [2, 1]

    def test_unmatched_name_returns_empty_not_everything(self):
        assert pick_target_buildings(self._collection(), name_contains="nothing here") == []


class TestQueryBuilders:
    def test_around_query_targets_building_ways(self):
        query = build_around_query(18.9217, 72.8332, 60)
        assert "around:60.0,18.9217,72.8332" in query
        assert '["building"]' in query

    def test_around_query_embeds_name_filter(self):
        query = build_around_query(18.9, 72.8, 50, name_contains="Taj Mahal Palace")
        assert '["name"~"Taj Mahal Palace",i]' in query

    def test_osm_id_query(self):
        assert "way(28846517)" in build_osm_id_query(28846517)


class TestIndiaGuard:
    @pytest.mark.parametrize(
        "lon,lat,expected",
        [
            (72.8332, 18.9217, True),   # Mumbai
            (77.2090, 28.6139, True),   # Delhi
            (2.3522, 48.8566, False),   # Paris
            (139.6917, 35.6895, False),  # Tokyo
        ],
    )
    def test_extent_check(self, lon, lat, expected):
        assert is_within_india(lon, lat) is expected

    @pytest.mark.asyncio
    async def test_out_of_india_coordinate_is_refused_before_any_network_call(self):
        client = OverpassClient(endpoints=("http://127.0.0.1:9/never",))
        with pytest.raises(OverpassError):
            await client.buildings_around(48.8566, 2.3522, 100)

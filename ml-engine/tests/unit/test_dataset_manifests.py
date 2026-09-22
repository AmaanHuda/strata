"""
test_dataset_manifests.py
SIH 2026 PS 26011 — ML Engine, Phase 1

Tests that all dataset manifests:
  - Exist and are valid JSON
  - Pass JSON Schema validation
  - Have required fields with non-empty content
  - Use allowed status values
  - Reference a valid URL format
  - Are not duplicated (unique names)
"""
import json
import pathlib
import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "dataset_manifest.json"
MANIFESTS_DIR = PROJECT_ROOT / "datasets" / "manifests"

ALLOWED_STATUS = {"REAL", "DERIVED", "SYNTHETIC", "INFERRED", "MIXED"}

EXPECTED_MANIFESTS = [
    "bhuvan_cartosat3.json",
    "nrsc_cartoDEM_v3.json",
    "copernicus_glo30_dem.json",
    "nasa_srtm30.json",
    "spacenet7_multitemporal.json",
    "inria_aerial_labeling.json",
    "whu_building_dataset.json",
    "osm_india_buildings.json",
    "dilrmp_cadastral.json",
]


@pytest.fixture(scope="module")
def manifest_schema():
    assert SCHEMA_PATH.exists(), f"Dataset manifest schema not found: {SCHEMA_PATH}"
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_manifests() -> list[dict]:
    manifests = []
    for name in EXPECTED_MANIFESTS:
        path = MANIFESTS_DIR / name
        assert path.exists(), f"Expected manifest not found: {path}"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["_filename"] = name
        manifests.append(data)
    return manifests


class TestManifestFiles:
    def test_manifests_dir_exists(self):
        assert MANIFESTS_DIR.exists(), f"Manifests directory missing: {MANIFESTS_DIR}"

    def test_all_expected_manifests_exist(self):
        for name in EXPECTED_MANIFESTS:
            path = MANIFESTS_DIR / name
            assert path.exists(), f"Missing manifest: {name}"

    def test_all_manifests_are_valid_json(self):
        for name in EXPECTED_MANIFESTS:
            path = MANIFESTS_DIR / name
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"{name} is not valid JSON: {e}")


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestManifestSchema:
    def test_all_manifests_pass_schema(self, all_manifests, manifest_schema):
        validator = jsonschema.Draft7Validator(manifest_schema)
        for manifest in all_manifests:
            name = manifest["_filename"]
            clean = {k: v for k, v in manifest.items() if k != "_filename"}
            errors = list(validator.iter_errors(clean))
            assert not errors, (
                f"{name} schema errors:\n" +
                "\n".join(f"  - {e.path}: {e.message}" for e in errors)
            )


class TestManifestContent:
    def test_required_fields_non_empty(self, all_manifests):
        required = ["name", "source", "url", "geography", "date",
                    "resolution", "crs", "labels", "license",
                    "provenance", "status", "limitations", "intended_use"]
        for manifest in all_manifests:
            name = manifest["_filename"]
            for field in required:
                value = manifest.get(field, "")
                assert value and str(value).strip(), (
                    f"{name}: field '{field}' is empty or missing"
                )

    def test_status_is_allowed_value(self, all_manifests):
        for manifest in all_manifests:
            name = manifest["_filename"]
            status = manifest.get("status", "")
            assert status in ALLOWED_STATUS, (
                f"{name}: status '{status}' not in {ALLOWED_STATUS}"
            )

    def test_url_format(self, all_manifests):
        for manifest in all_manifests:
            name = manifest["_filename"]
            url = manifest.get("url", "")
            assert url.startswith("http"), (
                f"{name}: url should start with http, got: '{url}'"
            )

    def test_limitations_field_is_substantive(self, all_manifests):
        for manifest in all_manifests:
            name = manifest["_filename"]
            limitations = manifest.get("limitations", "")
            assert len(limitations.strip()) > 20, (
                f"{name}: limitations field too short — must document real limitations"
            )

    def test_no_duplicate_names(self, all_manifests):
        names = [m.get("name", "") for m in all_manifests]
        assert len(names) == len(set(names)), (
            f"Duplicate dataset names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_real_status_datasets_have_substantive_source(self, all_manifests):
        for manifest in all_manifests:
            if manifest.get("status") == "REAL":
                source = manifest.get("source", "")
                assert len(source.strip()) > 5, (
                    f"{manifest['_filename']}: REAL status dataset must have substantive source"
                )

    def test_synthetic_status_not_present_yet(self, all_manifests):
        """Phase 1 should not contain any synthetic datasets."""
        synthetic = [m["_filename"] for m in all_manifests if m.get("status") == "SYNTHETIC"]
        assert not synthetic, (
            f"Synthetic datasets should not be in Phase 1 manifests: {synthetic}"
        )
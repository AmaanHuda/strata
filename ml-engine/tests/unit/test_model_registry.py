"""
Model registry honesty tests (no torch required).

SIH 2026 PS 26011 - ML Engine

The registry must never report a model as available unless real weights exist
WITH provenance metadata. Untraceable checkpoints and smoke-test artifacts are
surfaced but never counted as trained models.
"""
import json

from src.inference import model_registry


def _write_checkpoint(root, name: str, *, smoke: bool = False, with_metadata: bool = True):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "model.pt").write_bytes(b"placeholder-weights")
    if with_metadata:
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "model_name": name,
                    "architecture": {"name": "UNet", "version": "1.0.0"},
                    "dataset": {"manifest": {"name": "unit-test-manifest"}},
                    "training": {"smoke_test": smoke},
                    "metrics": {"test": {"iou": 0.5}},
                }
            ),
            encoding="utf-8",
        )
    return directory


def test_empty_registry_reports_baseline_only(tmp_path):
    health = model_registry.registry_health(tmp_path)
    assert health["trained_models_loaded"] is False
    assert health["models_loaded"] == []
    assert health["inference_ready"] == "baseline_only"
    assert health["checkpoints_found"] == 0


def test_weights_without_metadata_are_untraceable_and_not_loaded(tmp_path):
    _write_checkpoint(tmp_path, "orphan_weights", with_metadata=False)

    health = model_registry.registry_health(tmp_path)
    assert health["trained_models_loaded"] is False
    assert health["models_loaded"] == []
    assert health["untraceable_checkpoints"] == ["orphan_weights"]


def test_smoke_test_artifact_is_discovered_but_never_usable(tmp_path):
    _write_checkpoint(tmp_path, "smoke_harness_check", smoke=True)

    entry = model_registry.discover_models(tmp_path)[0]
    assert entry["smoke_test"] is True
    assert entry["traceable"] is True
    assert entry["inference_usable"] is False

    health = model_registry.registry_health(tmp_path)
    assert health["trained_models_loaded"] is False
    assert health["smoke_test_artifacts"] == ["smoke_harness_check"]


def test_traceable_production_checkpoint_is_reported_as_loaded(tmp_path):
    _write_checkpoint(tmp_path, "building_extraction_unet", smoke=False)

    health = model_registry.registry_health(tmp_path)
    assert health["trained_models_loaded"] is True
    assert health["models_loaded"] == ["building_extraction_unet"]
    assert health["inference_ready"] == "trained_models_available"


def test_loading_an_untraceable_checkpoint_is_refused(tmp_path):
    import pytest

    _write_checkpoint(tmp_path, "orphan_weights", with_metadata=False)
    with pytest.raises(RuntimeError, match="no provenance metadata"):
        model_registry.load_trained_model("orphan_weights", tmp_path)


def test_loading_a_missing_checkpoint_raises_file_not_found(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        model_registry.load_trained_model("never_trained", tmp_path)

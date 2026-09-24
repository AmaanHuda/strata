"""
Tests for the genuinely trainable U-Net architecture.

SIH 2026 PS 26011 - ML Engine

These tests require torch and are skipped when it is absent, so the ML Engine
suite still runs in the torch-free serving environment. Run them inside the
training virtualenv (see requirements-train.txt).
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="PyTorch is required for trained-model tests")

from src.building_extraction import torch_unet  # noqa: E402


def _metadata() -> dict:
    return {
        "model_name": "unit_test_model",
        "architecture": {"name": "UNet", "version": "1.0.0"},
        "dataset": {"manifest": {"name": "unit-test"}},
        "training": {"epochs_run": 1, "smoke_test": False},
        "metrics": {"test": {"iou": 0.0}},
    }


def test_architecture_has_real_learnable_parameters():
    """The previous 'UNet' had zero parameters and could not be trained."""
    model = torch_unet.build_model(base_channels=8)
    assert model.parameter_count() > 1000
    assert any(p.requires_grad for p in model.parameters())


def test_forward_output_shape_matches_input_resolution():
    model = torch_unet.build_model(base_channels=8)
    out = model(torch.zeros(2, 3, 64, 64))
    assert tuple(out.shape) == (2, 1, 64, 64)


def test_probability_map_is_a_valid_probability():
    model = torch_unet.build_model(base_channels=8)
    probs = model.predict_probability_map(np.zeros((32, 32, 3), dtype="float32"))
    assert probs.shape == (32, 32)
    assert float(probs.min()) >= 0.0
    assert float(probs.max()) <= 1.0


def test_model_actually_learns_on_a_tiny_batch():
    """Proves trainability end to end: loss must fall after gradient steps."""
    torch.manual_seed(0)
    model = torch_unet.build_model(base_channels=4)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.02)

    images = torch.rand(2, 3, 32, 32)
    targets = (images.mean(dim=1, keepdim=True) > 0.5).float()

    losses = []
    for _ in range(4):
        optimizer.zero_grad()
        logits = model(images)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))

    assert losses[-1] < losses[0]


def test_checkpoint_round_trip_preserves_weights(tmp_path):
    model = torch_unet.build_model(base_channels=4)
    checkpoint_dir = tmp_path / "unit_model"
    torch_unet.save_checkpoint(checkpoint_dir, model, _metadata())

    assert (checkpoint_dir / "model.pt").exists()
    assert (checkpoint_dir / "metadata.json").exists()

    loaded, metadata = torch_unet.load_checkpoint(checkpoint_dir)
    assert metadata["model_name"] == "unit_test_model"

    original = model.state_dict()
    restored = loaded.state_dict()
    assert set(original) == set(restored)
    for key in original:
        assert torch.equal(original[key], restored[key])


def test_checkpoint_refuses_to_be_written_without_provenance(tmp_path):
    """A checkpoint with no dataset source must never be produced."""
    model = torch_unet.build_model(base_channels=4)
    with pytest.raises(ValueError, match="provenance"):
        torch_unet.save_checkpoint(tmp_path / "orphan", model, {"model_name": "no-provenance"})


def test_loading_a_missing_checkpoint_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        torch_unet.load_checkpoint(tmp_path / "does_not_exist")

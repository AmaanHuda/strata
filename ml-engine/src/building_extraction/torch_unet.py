"""
Trainable U-Net for building footprint segmentation (PyTorch).

SIH 2026 PS 26011 - ML Engine

This module holds the only genuinely trainable deep model in the repository.
It replaces the previous `UNetFootprintModel` wrapper in `dl_models.py`, which
contained no neural network at all: no parameters, no torch import, no
optimizer step was possible. It was a fixed logistic curve over greyscale
pixels and could not be trained.

torch is an OPTIONAL dependency by design. The ML Engine service image
deliberately excludes it (see Dockerfile: "torch is intentionally excluded"),
so importing this module must never fail when torch is absent. Constructing a
model without torch raises a clear, actionable error instead.

Every checkpoint written here must carry a metadata sidecar recording dataset
provenance, so no checkpoint can exist without a traceable source.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:  # torch is absent in the serving environment; presence is optional
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - the serving image takes this path
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False


CHECKPOINT_FILENAME = "model.pt"
METADATA_FILENAME = "metadata.json"

ARCHITECTURE_NAME = "UNet"
ARCHITECTURE_VERSION = "1.0.0"

# Keys that every checkpoint metadata sidecar must carry. A checkpoint without
# a dataset source is untraceable, which is exactly the failure mode this
# repository has been burned by before.
REQUIRED_METADATA_KEYS = (
    "model_name",
    "architecture",
    "dataset",
    "training",
    "metrics",
)


def torch_unavailable_reason() -> str:
    return (
        "PyTorch is not installed in this environment. Training and trained-model "
        "inference require it. Install with:\n"
        "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
        "(see ml-engine/requirements-train.txt). The ML Engine service image "
        "intentionally ships without torch; baseline inference does not need it."
    )


def require_torch() -> None:
    """Raise a clear error rather than silently degrading to a fake result."""
    if not TORCH_AVAILABLE:
        raise RuntimeError(torch_unavailable_reason())


if TORCH_AVAILABLE:

    class DoubleConv(nn.Module):
        """(conv -> BN -> ReLU) x 2 - the standard U-Net building block."""

        def __init__(self, in_channels: int, out_channels: int):
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.block(x)

    class UNet(nn.Module):
        """
        Standard U-Net with an encoder/decoder and skip connections.

        Returns raw logits. Use BCEWithLogitsLoss during training, and
        `predict_probability_map()` to obtain calibrated probabilities in [0, 1].
        """

        def __init__(
            self,
            in_channels: int = 3,
            out_channels: int = 1,
            base_channels: int = 32,
        ):
            super().__init__()
            self.in_channels = in_channels
            self.out_channels = out_channels
            self.base_channels = base_channels

            c1 = base_channels
            c2 = base_channels * 2
            c3 = base_channels * 4
            c4 = base_channels * 8
            c5 = base_channels * 16

            # Encoder
            self.enc1 = DoubleConv(in_channels, c1)
            self.enc2 = DoubleConv(c1, c2)
            self.enc3 = DoubleConv(c2, c3)
            self.enc4 = DoubleConv(c3, c4)
            self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

            # Bottleneck
            self.bottleneck = DoubleConv(c4, c5)

            # Decoder (transposed convolution upsampling + concatenated skip)
            self.up4 = nn.ConvTranspose2d(c5, c4, kernel_size=2, stride=2)
            self.dec4 = DoubleConv(c4 + c4, c4)
            self.up3 = nn.ConvTranspose2d(c4, c3, kernel_size=2, stride=2)
            self.dec3 = DoubleConv(c3 + c3, c3)
            self.up2 = nn.ConvTranspose2d(c3, c2, kernel_size=2, stride=2)
            self.dec2 = DoubleConv(c2 + c2, c2)
            self.up1 = nn.ConvTranspose2d(c2, c1, kernel_size=2, stride=2)
            self.dec1 = DoubleConv(c1 + c1, c1)

            self.head = nn.Conv2d(c1, out_channels, kernel_size=1)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(self.pool(e1))
            e3 = self.enc3(self.pool(e2))
            e4 = self.enc4(self.pool(e3))
            b = self.bottleneck(self.pool(e4))

            d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
            d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
            d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
            d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))

            return self.head(d1)

        def parameter_count(self) -> int:
            """Evidence that this is a real model with learnable weights."""
            return sum(p.numel() for p in self.parameters() if p.requires_grad)

        def predict_probability_map(self, image_chip) -> "Any":
            """
            Predict a building probability map in [0, 1] for a HxW or HxWxC chip.

            Mirrors the method name previously exposed by the (non-neural)
            heuristic wrapper so existing callers keep working, but this now
            runs actual learned weights.
            """
            import numpy as np

            self.eval()
            arr = np.asarray(image_chip, dtype="float32")
            if arr.ndim == 2:
                arr = arr[:, :, None]
            if arr.ndim != 3:
                raise ValueError(f"Expected HxW or HxWxC chip, got shape {arr.shape}")

            # Channels-last (H, W, C) -> (C, H, W)
            tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)
            if tensor.shape[1] != self.in_channels:
                if tensor.shape[1] == 1 and self.in_channels == 3:
                    tensor = tensor.repeat(1, 3, 1, 1)
                else:
                    raise ValueError(
                        f"Model expects {self.in_channels} input channels, got {tensor.shape[1]}"
                    )

            with torch.no_grad():
                logits = self.forward(tensor)
                probs = torch.sigmoid(logits)
            return probs.squeeze(0).squeeze(0).cpu().numpy()

else:

    class UNet:  # type: ignore[no-redef]
        """
        Placeholder used when torch is unavailable.

        Instantiating this raises RuntimeError with installation instructions;
        it never fabricates predictions.
        """

        def __init__(self, *args, **kwargs):
            require_torch()


def build_model(
    in_channels: int = 3,
    out_channels: int = 1,
    base_channels: int = 32,
) -> "UNet":
    """Instantiate the architecture. Raises if torch is unavailable."""
    require_torch()
    return UNet(
        in_channels=in_channels,
        out_channels=out_channels,
        base_channels=base_channels,
    )


def save_checkpoint(
    checkpoint_dir: Path,
    model: "UNet",
    metadata: Dict[str, Any],
) -> Path:
    """
    Persist a real checkpoint plus its provenance metadata.

    The metadata must satisfy REQUIRED_METADATA_KEYS; a checkpoint with no
    dataset source is refused outright so that no untraceable weights can be
    written into the model registry.
    """
    require_torch()

    missing = [k for k in REQUIRED_METADATA_KEYS if k not in metadata]
    if missing:
        raise ValueError(
            "Refusing to write a checkpoint without provenance. Missing metadata keys: "
            f"{missing}. Required: {list(REQUIRED_METADATA_KEYS)}"
        )

    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "state_dict": model.state_dict(),
        "architecture": {
            "name": ARCHITECTURE_NAME,
            "version": ARCHITECTURE_VERSION,
            "in_channels": model.in_channels,
            "out_channels": model.out_channels,
            "base_channels": model.base_channels,
            "parameters": model.parameter_count(),
        },
        "metadata": metadata,
    }

    weights_path = checkpoint_dir / CHECKPOINT_FILENAME
    torch.save(payload, weights_path)

    sidecar = dict(metadata)
    sidecar["checkpoint"] = {
        "weights_file": CHECKPOINT_FILENAME,
        "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "framework": {
            "name": "pytorch",
            "version": torch.__version__,
        },
        "architecture_parameters": model.parameter_count(),
    }
    (checkpoint_dir / METADATA_FILENAME).write_text(
        json.dumps(sidecar, indent=2, sort_keys=True), encoding="utf-8"
    )

    return weights_path


def load_checkpoint(
    checkpoint_dir: Path,
    map_location: str = "cpu",
) -> Tuple["UNet", Dict[str, Any]]:
    """Load a checkpoint written by save_checkpoint()."""
    require_torch()

    checkpoint_dir = Path(checkpoint_dir)
    weights_path = checkpoint_dir / CHECKPOINT_FILENAME
    if not weights_path.exists():
        raise FileNotFoundError(f"No checkpoint weights at {weights_path}")

    payload = torch.load(weights_path, map_location=map_location, weights_only=False)
    arch = payload.get("architecture", {})
    if arch.get("name") != ARCHITECTURE_NAME:
        raise ValueError(f"Unsupported architecture in checkpoint: {arch.get('name')!r}")

    model = UNet(
        in_channels=int(arch.get("in_channels", 3)),
        out_channels=int(arch.get("out_channels", 1)),
        base_channels=int(arch.get("base_channels", 32)),
    )
    model.load_state_dict(payload["state_dict"])

    metadata_path = checkpoint_dir / METADATA_FILENAME
    metadata: Dict[str, Any] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    return model, metadata

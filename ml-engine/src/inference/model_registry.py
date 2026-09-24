"""
Model registry: discovery and loading of trained checkpoints.

SIH 2026 PS 26011 - ML Engine

The registry is the single source of truth for "is a trained model actually
available". It reports only what exists on disk WITH provenance metadata; a
weights file with no metadata sidecar is surfaced as `untraceable` and is never
counted as a loaded model. Nothing here invents models, metrics or readiness.

torch is optional: discovery works without it, loading needs it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINTS_ROOT = PROJECT_ROOT / "models" / "checkpoints"

WEIGHTS_CANDIDATES = ("model.pt", "weights.pt", "model.pth", "checkpoint.pt")
METADATA_CANDIDATES = ("metadata.json", "model_metadata.json")


def _torch_available() -> bool:
    try:
        from src.building_extraction import torch_unet

        return bool(torch_unet.TORCH_AVAILABLE)
    except Exception:
        return False


def _read_metadata(directory: Path) -> Optional[Dict[str, Any]]:
    for name in METADATA_CANDIDATES:
        path = directory / name
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    return None


def _find_weights(directory: Path) -> Optional[Path]:
    for name in WEIGHTS_CANDIDATES:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def discover_models(checkpoints_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    List every checkpoint directory and describe it honestly.

    `traceable` is True only when provenance metadata exists. `smoke_test` marks
    harness verification artifacts, which are discoverable (so nothing is hidden)
    but must never be reported as trained production models.
    """
    root = Path(checkpoints_root or DEFAULT_CHECKPOINTS_ROOT)
    if not root.exists():
        return []

    models: List[Dict[str, Any]] = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        weights = _find_weights(directory)
        metadata = _read_metadata(directory)
        smoke = bool((metadata or {}).get("training", {}).get("smoke_test", False))
        models.append(
            {
                "name": directory.name,
                "path": str(directory),
                "weights_present": weights is not None,
                "weights_file": weights.name if weights else None,
                "metadata_present": metadata is not None,
                "traceable": bool(weights and metadata),
                "smoke_test": smoke,
                "architecture": (metadata or {}).get("architecture"),
                "dataset": (metadata or {}).get("dataset", {}).get("manifest"),
                "metrics": (metadata or {}).get("metrics"),
                "inference_usable": bool(weights and metadata and not smoke),
            }
        )
    return models


def load_trained_model(
    name: str,
    checkpoints_root: Optional[Path] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Load a trained model by registry name.

    Raises FileNotFoundError when there is no such checkpoint, and RuntimeError
    when torch is unavailable. It never falls back to a heuristic and never
    presents baseline behaviour as a trained model.
    """
    root = Path(checkpoints_root or DEFAULT_CHECKPOINTS_ROOT)
    directory = root / name
    entry = next((m for m in discover_models(root) if m["name"] == name), None)

    if entry is None or not entry["weights_present"]:
        raise FileNotFoundError(f"No checkpoint named {name!r} under {root}")
    if not entry["traceable"]:
        raise RuntimeError(
            f"Checkpoint {name!r} has weights but no provenance metadata; refusing to "
            "treat an untraceable checkpoint as a model."
        )
    if entry["smoke_test"]:
        raise RuntimeError(
            f"Checkpoint {name!r} is a harness smoke-test artifact, not a trained model."
        )

    from src.building_extraction import torch_unet

    torch_unet.require_torch()
    return torch_unet.load_checkpoint(directory)


def registry_health(checkpoints_root: Optional[Path] = None) -> Dict[str, Any]:
    """Honest health payload for the ML Engine service."""
    models = discover_models(checkpoints_root)
    usable = [m for m in models if m["inference_usable"]]
    untraceable = [m["name"] for m in models if m["weights_present"] and not m["traceable"]]
    smoke = [m["name"] for m in models if m["smoke_test"]]

    return {
        "torch_available": _torch_available(),
        "checkpoints_found": len(models),
        "models_loaded": [m["name"] for m in usable],
        "trained_models_loaded": bool(usable),
        "inference_ready": "trained_models_available" if usable else "baseline_only",
        "untraceable_checkpoints": untraceable,
        "smoke_test_artifacts": smoke,
        "detail": models,
    }

"""
Training harness for the building footprint segmentation U-Net.

SIH 2026 PS 26011 - ML Engine

Reproducible training entry point. Design constraints, deliberately enforced:

  * A real dataset manifest is REQUIRED for a real run. Its contents are copied
    verbatim into the checkpoint metadata, so no checkpoint can exist without a
    traceable dataset source.
  * Splits are scene-level (see dataset.split_pairs) to avoid leakage.
  * Evaluation uses the repository's existing metrics (IoU, Dice, Precision,
    Recall, F1) - no metric is invented or rounded up.
  * `--smoke` runs the whole pipeline on synthetic tiles purely to prove the
    harness works. Smoke runs are stamped `smoke_test: true` and are written to
    a throwaway directory; they must never land in models/checkpoints, because a
    smoke run is not a trained model.

Usage (real run):
  python scripts/train_building_extraction.py \
      --data-dir datasets/raw/svamitva_drone \
      --manifest datasets/manifests/svamitva_drone_kaggle.json \
      --config configs/building_extraction_svamitva.json \
      --out-dir models/checkpoints/building_extraction_unet

Usage (harness verification only):
  python scripts/train_building_extraction.py --smoke
"""
from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from src.building_extraction import dataset as dataset_module  # noqa: E402
from src.building_extraction import dataset as tile_dataset  # noqa: E402
from src.building_extraction.dataset import (  # noqa: E402
    FootprintTileDataset,
    TilePair,
    building_pixel_fractions,
    describe_layout,
    discover_tiles,
    filter_blank_tiles,
    scan_dataset,
    split_fingerprint,
    split_pairs,
    split_summary,
    write_split_manifest,
)
from src.building_extraction.metrics import (  # noqa: E402
    calculate_dice,
    calculate_iou,
    calculate_precision_recall_f1,
)
from src.building_extraction import torch_unet  # noqa: E402

DEFAULT_CONFIG: Dict[str, object] = {
    "model_name": "building_extraction_unet",
    "architecture": "UNet",
    "in_channels": 3,
    "out_channels": 1,
    "base_channels": 32,
    "tile_size": 512,
    "batch_size": 4,
    "epochs": 30,
    "learning_rate": 0.0005,
    "seed": 1337,
    "val_fraction": 0.15,
    "test_fraction": 0.15,
    "bce_weight": 0.5,
    "dice_weight": 0.5,
    "threshold": 0.5,
    "early_stopping_patience": 8,
    # Building label colour for RGB class masks. None = mask is already binary.
    "mask_color": None,
    "mask_tolerance": 0,
    "random_crop": False,
    "split_strategy": "auto",
    "secondary_stratified_eval": False,
    "images_subdir": None,
    "masks_subdir": None,
    "max_blank_fraction": 0.90,
    "scan_cache_path": "datasets/processed/tile_scan_cache.json",
}


def load_config(path: Optional[Path]) -> Dict[str, object]:
    config = dict(DEFAULT_CONFIG)
    if path:
        config.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return config


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch_unet.TORCH_AVAILABLE:
        import torch

        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)


def make_synthetic_tiles(root: Path, n_scenes: int = 4, tiles_per_scene: int = 3) -> Path:
    """
    Create tiny synthetic tiles strictly for harness verification.

    These are NOT training data and must never be presented as such: they exist
    so the training loop can be proven to run before real data is available.
    """
    from PIL import Image

    root.mkdir(parents=True, exist_ok=True)
    for scene in range(n_scenes):
        images_dir = root / f"scene{scene:02d}" / "images"
        masks_dir = root / f"scene{scene:02d}" / "masks"
        images_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)
        for tile in range(tiles_per_scene):
            rng = np.random.RandomState(scene * 100 + tile)
            image = (rng.rand(64, 64, 3) * 255).astype("uint8")
            mask = np.zeros((64, 64), dtype="uint8")
            mask[10:30, 10:30] = 255
            if tile % 2:
                mask[35:50, 35:55] = 255
            name = f"scene{scene:02d}_patch_{tile:04d}"
            Image.fromarray(image).save(images_dir / f"{name}.png")
            Image.fromarray(mask).save(masks_dir / f"{name}_mask.png")
    return root


def bce_dice_loss(logits, targets, bce_weight: float, dice_weight: float):
    import torch
    import torch.nn.functional as F

    bce = F.binary_cross_entropy_with_logits(logits, targets)
    probs = torch.sigmoid(logits)
    intersection = (probs * targets).sum(dim=(2, 3))
    union = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
    dice = (2.0 * intersection + 1.0) / (union + 1.0)
    dice_loss = 1.0 - dice.mean()
    return bce_weight * bce + dice_weight * dice_loss


def evaluate(
    model,
    loader,
    threshold: float,
) -> Dict[str, float]:
    """Compute real IoU / Dice / Precision / Recall / F1 over a loader."""
    import torch

    model.eval()
    ious: List[float] = []
    dices: List[float] = []
    prfs: List[Dict[str, float]] = []

    with torch.no_grad():
        for images, masks in loader:
            logits = model(images)
            preds = (torch.sigmoid(logits) >= threshold).float().cpu().numpy()
            truths = masks.cpu().numpy()
            for i in range(preds.shape[0]):
                pred_mask = preds[i, 0]
                true_mask = truths[i, 0]
                ious.append(calculate_iou(pred_mask, true_mask))
                dices.append(calculate_dice(pred_mask, true_mask))
                prfs.append(calculate_precision_recall_f1(pred_mask, true_mask))

    def mean(values: Sequence[float]) -> float:
        return float(np.mean(values)) if values else 0.0

    return {
        "iou": round(mean(ious), 6),
        "dice": round(mean(dices), 6),
        "precision": round(mean([p["precision"] for p in prfs]), 6),
        "recall": round(mean([p["recall"] for p in prfs]), 6),
        "f1": round(mean([p["f1"] for p in prfs]), 6),
        "tiles_evaluated": len(ious),
    }


def _build_loader(
    pairs,
    tile_size: int,
    batch_size: int,
    shuffle: bool,
    augment: bool,
    seed: int,
    mask_color=None,
    mask_tolerance: int = 0,
    random_crop: bool = False,
):
    import torch
    from torch.utils.data import DataLoader

    ds = FootprintTileDataset(
        pairs,
        tile_size=tile_size,
        augment=augment,
        seed=seed,
        mask_color=mask_color,
        mask_tolerance=mask_tolerance,
        random_crop=random_crop,
    )
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, num_workers=0, drop_last=False)


def train(
    pairs: Sequence[TilePair],
    config: Dict[str, object],
    out_dir: Path,
    dataset_manifest: Optional[Dict[str, object]],
    smoke: bool,
    device_name: str = "cpu",
) -> Dict[str, object]:
    import torch

    torch_unet.require_torch()

    seed = int(config["seed"])
    set_seeds(seed)

    device = torch.device("cuda" if device_name == "cuda" and torch.cuda.is_available() else "cpu")

    mask_color = config.get("mask_color")
    mask_color = tuple(mask_color) if mask_color else None
    mask_tolerance = int(config.get("mask_tolerance", 0) or 0)
    random_crop = bool(config.get("random_crop", False))
    strategy = str(config.get("split_strategy", "auto"))

    # One pass over imagery + masks gives building coverage and nodata
    # blankness. Positivity drives stratification; blankness removes tiles that
    # are orthomosaic padding rather than real observation.
    cache_path = config.get("scan_cache_path")
    cache_path = Path(PROJECT_ROOT / str(cache_path)) if cache_path else None
    scan = scan_dataset(pairs, mask_color, mask_tolerance, cache_path=cache_path)

    kept, dropped = filter_blank_tiles(pairs, scan, float(config.get("max_blank_fraction", 0.90)))
    dropped_positive = [p.tile_id for p in dropped if scan[p.tile_id]["building_fraction"] > 0.0]
    if dropped:
        print(
            f"[data] excluded {len(dropped)}/{len(pairs)} nodata-blank tiles "
            f"(> {config.get('max_blank_fraction', 0.90):.0%} near-black pixels); "
            f"{len(dropped_positive)} of them contained building pixels"
        )
    if dropped_positive:
        print(f"[data] WARNING: excluded blank tiles containing buildings: {dropped_positive[:10]}")
    pairs = kept

    positive_flags = {tile: entry["building_fraction"] > 0.0 for tile, entry in scan.items()}
    resolved_strategy = strategy
    if strategy == "auto":
        resolved_strategy = "scene" if len({p.scene_key for p in pairs}) >= 3 else "contiguous"

    splits = split_pairs(
        pairs,
        val_fraction=float(config["val_fraction"]),
        test_fraction=float(config["test_fraction"]),
        seed=seed,
        strategy=strategy,
        positive_flags=positive_flags,
    )
    tile_size = int(config["tile_size"])
    batch_size = int(config["batch_size"])

    def loader_for(subset, shuffle: bool, augment: bool):
        return _build_loader(
            subset,
            tile_size,
            batch_size,
            shuffle,
            augment,
            seed,
            mask_color,
            mask_tolerance,
            random_crop,
        )

    train_loader = loader_for(splits["train"], True, True)
    val_loader = loader_for(splits["val"], False, False)
    test_loader = loader_for(splits["test"], False, False)

    # Optional distribution-matched (but spatially leaky) evaluation of the same
    # weights, reported separately and labelled as such. Never the headline number.
    secondary_loader = None
    if bool(config.get("secondary_stratified_eval", False)) and resolved_strategy != "stratified":
        secondary_splits = split_pairs(
            pairs,
            val_fraction=float(config["val_fraction"]),
            test_fraction=float(config["test_fraction"]),
            seed=seed,
            strategy="stratified",
            positive_flags=positive_flags,
        )
        secondary_loader = loader_for(secondary_splits["test"], False, False)

    model = torch_unet.build_model(
        in_channels=int(config["in_channels"]),
        out_channels=int(config["out_channels"]),
        base_channels=int(config["base_channels"]),
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["learning_rate"]))
    epochs = int(config["epochs"])
    patience = int(config["early_stopping_patience"])
    threshold = float(config["threshold"])

    history: List[Dict[str, object]] = []
    best_iou = -1.0
    best_state = None
    best_epoch = 0
    epochs_without_improvement = 0
    torch.manual_seed(seed)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loader.dataset.set_epoch(epoch)
        epoch_losses: List[float] = []
        for images, masks in train_loader:
            images = images.to(device)
            masks = masks.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = bce_dice_loss(
                logits,
                masks,
                float(config["bce_weight"]),
                float(config["dice_weight"]),
            )
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu()))

        val_metrics = evaluate(model, val_loader, threshold)
        entry = {
            "epoch": epoch,
            "train_loss": round(float(np.mean(epoch_losses)), 6) if epoch_losses else None,
            "val": val_metrics,
        }
        history.append(entry)
        print(
            f"[epoch {epoch:03d}] train_loss={entry['train_loss']} "
            f"val_iou={val_metrics['iou']} val_dice={val_metrics['dice']} val_f1={val_metrics['f1']}"
        )

        if val_metrics["iou"] > best_iou:
            best_iou = val_metrics["iou"]
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"[early stopping] no val IoU improvement for {patience} epochs")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate(model, test_loader, threshold)
    print(f"[test] {json.dumps(test_metrics, sort_keys=True)}")

    secondary_metrics = None
    if secondary_loader is not None:
        secondary_metrics = evaluate(model, secondary_loader, threshold)
        print(f"[test-stratified-leakage-optimistic] {json.dumps(secondary_metrics, sort_keys=True)}")

    metadata: Dict[str, object] = {
        "model_name": str(config["model_name"]),
        "architecture": {
            "name": torch_unet.ARCHITECTURE_NAME,
            "version": torch_unet.ARCHITECTURE_VERSION,
            "base_channels": int(config["base_channels"]),
            "parameters": model.parameter_count(),
        },
        "dataset": {
            "manifest_present": dataset_manifest is not None,
            "manifest": dataset_manifest,
            "total_tiles": len(pairs),
            "tiles_excluded_nodata_blank": len(dropped),
            "excluded_tiles_with_buildings": dropped_positive,
            "blank_pixel_threshold": dataset_module.BLANK_PIXEL_THRESHOLD,
            "max_blank_fraction": float(config.get("max_blank_fraction", 0.90)),
            "scan_cache": str(cache_path) if cache_path else None,
            "split_strategy": resolved_strategy,
            "split_strategy_requested": strategy,
            "split_fingerprint": split_fingerprint(splits),
            "split_caveats": {
                "contiguous": "Contiguous blocks of tile order. Spatially disjoint for raster-ordered tiles, but tile order is NOT density-neutral here, so val/test building density differs from train; that shift is reported per split and is NOT corrected for.",
                "scene": "Grouped by inferred scene key; no tiles of one scene straddle splits.",
                "stratified": "RANDOM tiles, stratified on building presence. Distribution-matched but NOT spatially disjoint; scores are leakage-optimistic.",
            }.get(resolved_strategy, "unknown"),
            "split_summary": split_summary(splits, strategy=resolved_strategy, positive_flags=positive_flags),
            "mask_decoding": {
                "mask_color": list(mask_color) if mask_color else None,
                "mask_tolerance": mask_tolerance,
                "note": "Exact colour match on the class mask; NOT a '>0' binarisation."
                if mask_color
                else "Mask treated as already binary (single-channel).",
            },
            "mask_labels_provenance": (dataset_manifest or {}).get("labels"),
        },
        "training": {
            "config": config,
            "device": str(device),
            "epochs_run": len(history),
            "best_epoch": best_epoch,
            "best_val_iou": round(float(best_iou), 6),
            "history": history,
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "smoke_test": bool(smoke),
            "torch_version": torch.__version__,
            "python_version": sys.version.split()[0],
            "repo_commit": _git_commit(),
        },
        "metrics": {
            "validation_best": history[best_epoch - 1]["val"] if history and best_epoch else {},
            "test": test_metrics,
            "test_stratified_leakage_optimistic": secondary_metrics,
            "metric_definition": "computed on the held-out split at threshold "
            f"{threshold}; per-tile means via src/building_extraction/metrics.py",
            "primary_metric": "test",
            "leakage_optimistic_metric": "test_stratified_leakage_optimistic"
            if secondary_metrics
            else None,
        },
    }

    if smoke:
        metadata["training"]["smoke_test_notice"] = (
            "Synthetic tiles. This is a harness verification run, NOT a trained "
            "building extraction model and NOT usable for inference."
        )

    torch_unet.save_checkpoint(out_dir, model, metadata)
    write_split_manifest(splits, out_dir / "split_manifest.json")
    (out_dir / "test_metrics.json").write_text(
        json.dumps(test_metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metadata


def _git_commit() -> Optional[str]:
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Train the building footprint U-Net.")
    parser.add_argument("--data-dir", type=Path, help="Directory containing image/mask tiles")
    parser.add_argument("--manifest", type=Path, help="Dataset manifest JSON (required for real runs)")
    parser.add_argument("--config", type=Path, help="Training config JSON")
    parser.add_argument("--out-dir", type=Path, help="Checkpoint output directory")
    parser.add_argument("--images-dir", type=Path, help="Explicit imagery directory (paired by stem with --masks-dir)")
    parser.add_argument("--masks-dir", type=Path, help="Explicit mask directory")
    parser.add_argument("--smoke", action="store_true", help="Harness verification on synthetic tiles")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--describe-only", action="store_true", help="Print dataset layout and exit")
    args = parser.parse_args(argv)

    if not torch_unet.TORCH_AVAILABLE:
        print(torch_unet.torch_unavailable_reason(), file=sys.stderr)
        return 2

    config = load_config(args.config)

    if args.smoke:
        config.update({"epochs": 2, "tile_size": 64, "batch_size": 2, "base_channels": 8, "model_name": "smoke_harness_check"})
        with tempfile.TemporaryDirectory(prefix="unet_smoke_") as tmp:
            data_root = make_synthetic_tiles(Path(tmp) / "synthetic")
            pairs = discover_tiles(data_root)
            out_dir = Path(tmp) / "out"
            print(f"[smoke] {len(pairs)} synthetic tile pairs; verifying the harness end to end")
            metadata = train(pairs, config, out_dir, dataset_manifest=None, smoke=True, device_name="cpu")
            print(f"[smoke] {json.dumps(metadata['metrics']['test'], sort_keys=True)}")
            print("[smoke] harness verified. No model artifact was written to models/checkpoints.")
        return 0

    if not args.data_dir:
        parser.error("--data-dir is required unless --smoke is used")

    if args.describe_only:
        print(json.dumps(describe_layout(args.data_dir), indent=2))
        return 0

    if not args.manifest:
        print(
            "Refusing to train without --manifest: a checkpoint with no traceable "
            "dataset source must never be produced (AGENTS.md section 3).",
            file=sys.stderr,
        )
        return 3

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    base = Path(args.data_dir)
    images_dir = args.images_dir or (base / str(config["images_subdir"]) if config.get("images_subdir") else None)
    masks_dir = args.masks_dir or (base / str(config["masks_subdir"]) if config.get("masks_subdir") else None)

    pairs = discover_tiles(base, images_dir=images_dir, masks_dir=masks_dir)
    mask_color = config.get("mask_color")
    mask_color = tuple(mask_color) if mask_color else None
    print(f"[data] {len(pairs)} image/mask tile pairs discovered (images={images_dir or base}, masks={masks_dir or base})")
    print(f"[data] mask_color={mask_color}")
    print(
        "[data] stats: "
        + json.dumps(
            tile_dataset.dataset_stats(
                pairs,
                mask_color=mask_color,
                mask_tolerance=int(config.get("mask_tolerance", 0) or 0),
            ),
            sort_keys=True,
        )
    )

    out_dir = args.out_dir or (PROJECT_ROOT / "models" / "checkpoints" / str(config["model_name"]))
    metadata = train(pairs, config, Path(out_dir), dataset_manifest=manifest, smoke=False, device_name=args.device)
    print(f"[done] checkpoint + metadata written to {out_dir}")
    print(f"[done] test metrics: {json.dumps(metadata['metrics']['test'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

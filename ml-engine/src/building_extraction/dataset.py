"""
Tile dataset for building footprint segmentation training.

SIH 2026 PS 26011 - ML Engine

Responsibilities:
  * discover image/mask tile pairs on disk (explicit directories preferred),
  * decode RGB class-coloured masks into a binary building label,
  * build leakage-aware train/val/test splits,
  * serve (image, mask) tensors to PyTorch.

Two correctness rules are enforced here, both learned from the real dataset:

1. MASK DECODING. Segmentation masks in the wild are usually RGB class
   colourings, not binary images. SVAMITVA's masks (per the dataset's own
   `poly2mask.py`) paint Building as (0, 110, 255) and Field, Road, Water and
   Other in other colours. Binarising such a mask with `pixel > 0` marks almost
   the whole image as foreground. When `mask_color` is supplied the label is an
   exact colour match; when it is not, only single-channel masks are accepted as
   already-binary.

2. SPLIT HONESTY. Tiles cut from one survey are spatially adjacent, so a random
   tile split leaks approximately-identical neighbours across splits. Splits are
   made by SCENE when several scenes exist, and otherwise by CONTIGUOUS BLOCKS of
   tile index, which is spatially disjoint for raster-ordered tiles. Which
   strategy was used, and the resulting building-density per split, are reported
   in the checkpoint metadata rather than assumed.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

IMAGE_SUFFIXES = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".ecw")
MASK_SUFFIXES = (".png", ".tif", ".tiff", ".jpg", ".jpeg")

_MASK_HINTS = ("mask", "label", "annot", "gt", "target", "building")
_IMAGE_HINTS = ("image", "img", "imgage", "sat", "rgb", "ortho", "photo", "patch")

SPLIT_STRATEGIES = ("auto", "scene", "contiguous", "stratified")

_INDEX_RE = re.compile(r"(\d+)")


@dataclass(frozen=True)
class TilePair:
    image_path: Path
    mask_path: Path
    scene_key: str
    tile_id: str
    tile_index: Optional[int] = None


def parse_tile_index(name: str) -> Optional[int]:
    """Trailing integer in a tile name, e.g. 'patch_1234' -> 1234."""
    matches = _INDEX_RE.findall(Path(name).stem)
    return int(matches[-1]) if matches else None


def _pair_sort_key(pair: TilePair) -> Tuple[str, int, str]:
    return (pair.scene_key, pair.tile_index if pair.tile_index is not None else -1, pair.tile_id)


def _infer_scene_key(path: Path, root: Path) -> str:
    """
    Infer a scene/group key so tiles from one drone scene stay in one split.

    Strategy (documented approximation):
      1. Use the immediate parent directory name when it looks scene-specific.
      2. Otherwise strip trailing tile/patch indices from the stem, e.g.
         "scene04_patch_0123" -> "scene04".
    """
    stem = path.stem
    stripped = re.sub(r"[_\- \t]*(patch|tile|img|image|chip)?[_\- \t]*\d+$", "", stem, flags=re.IGNORECASE)
    if stripped and stripped != stem:
        return stripped

    try:
        rel = path.relative_to(root)
    except ValueError:
        return stem
    if len(rel.parts) >= 3:
        return rel.parts[-3]
    return path.parent.name or stem


def _looks_like_mask(path: Path) -> bool:
    hay = f"{path.parent.name} {path.stem}".lower()
    return any(h in hay for h in _MASK_HINTS)


def _looks_like_image(path: Path) -> bool:
    hay = f"{path.parent.name} {path.stem}".lower()
    return any(h in hay for h in _IMAGE_HINTS)


def _index_files(root: Path) -> Tuple[Dict[str, Path], Dict[str, Path]]:
    """Index candidate images and masks by (lowercased) stem."""
    images: Dict[str, Path] = {}
    masks: Dict[str, Path] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in IMAGE_SUFFIXES and suffix not in MASK_SUFFIXES:
            continue

        # Mask hints take precedence. Mask files are routinely named with the same
        # tokens as their imagery (e.g. "scene01_patch_0001_mask.png"), so testing
        # "looks like an image" first would sweep every mask into the imagery pool
        # and leave zero masks - which looked exactly like a failed download.
        if _looks_like_mask(path):
            masks.setdefault(path.stem.lower(), path)
        elif _looks_like_image(path):
            images.setdefault(path.stem.lower(), path)

    return images, masks


def _mask_stem_candidates(image_stem: str) -> Iterable[str]:
    base = image_stem.lower()
    bases = {base}
    for marker in ("_sat", "-sat", "_image", "-image", "_img", "-img", "_rgb", "-rgb", "_patch", "-patch"):
        if marker in base:
            bases.add(base.split(marker)[0])
    for hint in ("_mask", "-mask", "_label", "-label"):
        for b in list(bases):
            if hint in b:
                bases.add(b.split(hint)[0])
    for b in list(bases):
        for hint in ("_mask", "-mask", "_label", "-label", "_building", "-building"):
            bases.add(f"{b}{hint}")
    return bases


def _pairs_from_explicit_dirs(images_dir: Path, masks_dir: Path) -> List[TilePair]:
    """
    Pair tiles from two explicitly named directories by identical file stem.

    This is the preferred path for real datasets: it cannot accidentally pick up
    a differently-encoded mask copy elsewhere in the tree (for example a
    matplotlib-colormapped 'BinaryMasks' folder sitting next to the real masks).
    """
    if not images_dir.exists():
        raise FileNotFoundError(f"images_dir does not exist: {images_dir}")
    if not masks_dir.exists():
        raise FileNotFoundError(f"masks_dir does not exist: {masks_dir}")

    mask_by_stem: Dict[str, Path] = {}
    for path in sorted(masks_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in MASK_SUFFIXES:
            mask_by_stem.setdefault(path.stem.lower(), path)

    pairs: List[TilePair] = []
    unmatched: List[str] = []
    for path in sorted(images_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        mask_path = mask_by_stem.get(path.stem.lower())
        if mask_path is None:
            unmatched.append(path.name)
            continue
        # The imagery folder's own name is not a scene label, so use the dataset
        # folder above it (e.g. "Images" under "Full Data" -> "Full Data").
        pairs.append(
            TilePair(
                image_path=path,
                mask_path=mask_path,
                scene_key=images_dir.parent.name or images_dir.name or "scene",
                tile_id=path.stem,
                tile_index=parse_tile_index(path.stem),
            )
        )

    if not pairs:
        raise FileNotFoundError(
            f"No image/mask pairs matched by stem between {images_dir} and {masks_dir}. "
            f"First unmatched images: {unmatched[:5]}"
        )

    if unmatched:
        print(
            f"[data] WARNING: {len(unmatched)} images had no same-stem mask and were skipped; "
            f"first: {unmatched[:5]}"
        )
    return pairs


def discover_tiles(
    root: Path,
    max_tiles: Optional[int] = None,
    images_dir: Optional[Path] = None,
    masks_dir: Optional[Path] = None,
) -> List[TilePair]:
    """
    Discover image/mask tile pairs.

    Pass `images_dir`/`masks_dir` for an exact pairing; otherwise the tree under
    `root` is scanned heuristically. Raises FileNotFoundError with a layout report
    when nothing pairs up, so a failed download is never mistaken for an
    empty-but-valid dataset.
    """
    if images_dir is not None or masks_dir is not None:
        if images_dir is None or masks_dir is None:
            raise ValueError("images_dir and masks_dir must be supplied together")
        pairs = _pairs_from_explicit_dirs(Path(images_dir), Path(masks_dir))
        pairs.sort(key=_pair_sort_key)
        return pairs[:max_tiles] if max_tiles is not None else pairs

    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Dataset root does not exist: {root}")

    images, masks = _index_files(root)

    pairs: List[TilePair] = []
    unmatched: List[str] = []

    for image_stem, image_path in sorted(images.items()):
        mask_path = None
        for candidate in _mask_stem_candidates(image_stem):
            if candidate in masks:
                mask_path = masks[candidate]
                break

        if mask_path is None:
            # Directory-sibling fallback: same stem inside a masks/ directory.
            sibling = image_path.parent.parent / "masks" / image_path.with_suffix(".png").name
            if sibling.exists():
                mask_path = sibling
            else:
                unmatched.append(str(image_path))
                continue

        pairs.append(
            TilePair(
                image_path=image_path,
                mask_path=mask_path,
                scene_key=_infer_scene_key(image_path, root),
                tile_id=image_path.stem,
                tile_index=parse_tile_index(image_path.stem),
            )
        )

    if not pairs:
        raise FileNotFoundError(
            "No image/mask tile pairs could be paired under "
            f"{root}. Found {len(images)} image candidates and {len(masks)} mask "
            f"candidates. First unmatched images: {unmatched[:5]}. "
            "Run describe_layout() to inspect the actual structure."
        )

    pairs.sort(key=_pair_sort_key)
    if max_tiles is not None:
        pairs = pairs[:max_tiles]
    return pairs


def describe_layout(root: Path, limit: int = 40) -> Dict[str, object]:
    """Summarise a downloaded dataset tree - used to confirm layout by hand."""
    root = Path(root)
    if not root.exists():
        return {"root": str(root), "exists": False}

    dirs: List[str] = []
    files: List[str] = []
    suffix_counts: Dict[str, int] = {}

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            dirs.append(str(path.relative_to(root)))
        elif path.is_file():
            if len(files) < limit:
                files.append(str(path.relative_to(root)))
            suffix_counts[path.suffix.lower()] = suffix_counts.get(path.suffix.lower(), 0) + 1

    return {
        "root": str(root),
        "exists": True,
        "directory_count": len(dirs),
        "directories": dirs[:limit],
        "file_extension_counts": dict(sorted(suffix_counts.items())),
        "sample_files": files,
    }


def decode_mask(arr: np.ndarray, mask_color: Optional[Sequence[int]] = None, tolerance: int = 0) -> np.ndarray:
    """
    Decode a mask image into a binary building label.

    * `mask_color` given  -> exact (within `tolerance`) colour match on RGB.
    * `mask_color` None   -> the mask must already be effectively single-channel;
      any non-zero pixel is foreground. Passing an RGB class mask here is a
      misuse, so it is rejected loudly rather than silently mislabelled.
    """
    arr = np.asarray(arr)
    if arr.ndim == 2:
        return (arr > 0).astype("float32")

    if arr.ndim != 3:
        raise ValueError(f"Unsupported mask shape {arr.shape}")

    if mask_color is None:
        if arr.shape[2] >= 3 and not np.array_equal(arr[:, :, 0], arr[:, :, 1]):
            raise ValueError(
                "Mask is a multi-colour RGB image but no mask_color was supplied. "
                "Binarising RGB class masks with '>0' mislabels every class as "
                "foreground; supply the building colour instead."
            )
        return (arr[:, :, 0] > 0).astype("float32")

    rgb = arr[:, :, :3].astype("int16")
    target = np.asarray(list(mask_color)[:3], dtype="int16")
    diff = np.abs(rgb - target).max(axis=2)
    return (diff <= int(tolerance)).astype("float32")


CACHE_VERSION = 1

# A tile whose pixels are essentially all near-black is nodata padding in the
# source orthomosaic, not verified empty ground. Labelling it "no building" would
# be inventing ground truth, so such tiles are excluded and counted.
BLANK_PIXEL_THRESHOLD = 10
DEFAULT_MAX_BLANK_FRACTION = 0.90


def scan_dataset(
    pairs: Sequence[TilePair],
    mask_color: Optional[Sequence[int]] = None,
    tolerance: int = 0,
    cache_path: Optional[Path] = None,
    progress_every: int = 250,
) -> Dict[str, Dict[str, float]]:
    """
    One pass over imagery and masks measuring, per tile:

      * `building_fraction` - decoded building pixels as a fraction of the tile,
      * `blank_fraction`    - near-black pixels, i.e. likely nodata padding.

    Results are cached to JSON keyed by tile id plus image/mask size and mtime, so
    repeat runs do not re-decode the whole dataset. A stale cache entry is
    recomputed rather than trusted.
    """
    from PIL import Image

    cache: Dict[str, Dict[str, object]] = {}
    cache_path = Path(cache_path) if cache_path else None
    if cache_path and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("cache_version") == CACHE_VERSION:
                cache = payload.get("tiles", {})
        except (json.JSONDecodeError, OSError):
            cache = {}

    out: Dict[str, Dict[str, float]] = {}
    computed = 0
    for index, pair in enumerate(pairs, start=1):
        img_stat = pair.image_path.stat()
        msk_stat = pair.mask_path.stat()
        key = pair.tile_id
        entry = cache.get(key)
        signature = [img_stat.st_size, int(img_stat.st_mtime), msk_stat.st_size, int(msk_stat.st_mtime)]
        if entry and entry.get("signature") == signature:
            out[key] = {
                "building_fraction": float(entry["building_fraction"]),
                "blank_fraction": float(entry["blank_fraction"]),
            }
            continue

        with Image.open(pair.image_path) as img:
            grey = np.asarray(img.convert("L"))
        with Image.open(pair.mask_path) as msk:
            mask_arr = np.asarray(msk)

        out[key] = {
            "building_fraction": float(decode_mask(mask_arr, mask_color, tolerance).mean()),
            "blank_fraction": float((grey < BLANK_PIXEL_THRESHOLD).mean()),
        }
        cache[key] = {"signature": signature, **out[key]}
        computed += 1
        if progress_every and computed % progress_every == 0:
            print(f"[scan] {index}/{len(pairs)} tiles measured")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"cache_version": CACHE_VERSION, "tiles": cache}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return out


def building_pixel_fractions(
    pairs: Sequence[TilePair],
    mask_color: Optional[Sequence[int]] = None,
    tolerance: int = 0,
    limit: Optional[int] = None,
) -> Dict[str, float]:
    """Building-pixel fraction per tile. Used for split stratification and reporting."""
    subset = list(pairs)[:limit] if limit else list(pairs)
    scan = scan_dataset(subset, mask_color, tolerance, progress_every=0)
    return {tile: entry["building_fraction"] for tile, entry in scan.items()}


def filter_blank_tiles(
    pairs: Sequence[TilePair],
    scan: Dict[str, Dict[str, float]],
    max_blank_fraction: float = DEFAULT_MAX_BLANK_FRACTION,
) -> Tuple[List[TilePair], List[TilePair]]:
    """
    Split out tiles that are nodata padding rather than real observation.

    Returns (kept, dropped). Dropped tiles are reported, never silently ignored.
    """
    kept: List[TilePair] = []
    dropped: List[TilePair] = []
    for pair in pairs:
        entry = scan.get(pair.tile_id)
        blank = entry["blank_fraction"] if entry else 0.0
        (dropped if blank > max_blank_fraction else kept).append(pair)
    return kept, dropped


def _contiguous_splits(
    pairs: Sequence[TilePair],
    val_fraction: float,
    test_fraction: float,
) -> Dict[str, List[TilePair]]:
    """Split by contiguous blocks of tile order - spatially disjoint for raster tiles."""
    ordered = sorted(pairs, key=_pair_sort_key)
    n = len(ordered)
    n_test = int(round(n * test_fraction))
    n_val = int(round(n * val_fraction))
    n_train = n - n_val - n_test
    return {
        "train": ordered[:n_train],
        "val": ordered[n_train : n_train + n_val],
        "test": ordered[n_train + n_val :],
    }


def _stratified_splits(
    pairs: Sequence[TilePair],
    val_fraction: float,
    test_fraction: float,
    seed: int,
    positive_flags: Dict[str, bool],
) -> Dict[str, List[TilePair]]:
    """
    Random split stratified on building presence.

    Distribution-matched, but NOT spatially disjoint: neighbouring tiles can land
    in different splits and inflate scores. Reported as such.
    """
    groups: Dict[bool, List[TilePair]] = {True: [], False: []}
    for pair in pairs:
        groups[bool(positive_flags.get(pair.tile_id, False))].append(pair)

    splits: Dict[str, List[TilePair]] = {"train": [], "val": [], "test": []}
    for group in groups.values():
        ordered = sorted(group, key=lambda p: p.tile_id)
        random.Random(seed).shuffle(ordered)
        n = len(ordered)
        n_test = int(round(n * test_fraction))
        n_val = int(round(n * val_fraction))
        splits["test"].extend(ordered[:n_test])
        splits["val"].extend(ordered[n_test : n_test + n_val])
        splits["train"].extend(ordered[n_test + n_val :])

    for key in splits:
        splits[key].sort(key=_pair_sort_key)
    return splits


def _scene_splits(
    pairs: Sequence[TilePair],
    val_fraction: float,
    test_fraction: float,
    seed: int,
) -> Dict[str, List[TilePair]]:
    scene_to_tiles: Dict[str, List[TilePair]] = {}
    for pair in pairs:
        scene_to_tiles.setdefault(pair.scene_key, []).append(pair)

    scenes = sorted(scene_to_tiles)
    random.Random(seed).shuffle(scenes)

    n_scenes = len(scenes)
    n_test = max(1, int(round(n_scenes * test_fraction)))
    n_val = max(1, int(round(n_scenes * val_fraction)))
    if n_val + n_test >= n_scenes:
        n_test = max(0, n_scenes - n_val - 1)
        if n_val >= n_scenes:
            n_val = max(1, n_scenes - 1)

    test_scenes = set(scenes[:n_test])
    val_scenes = set(scenes[n_test : n_test + n_val])

    splits: Dict[str, List[TilePair]] = {"train": [], "val": [], "test": []}
    for scene, tiles in scene_to_tiles.items():
        if scene in test_scenes:
            splits["test"].extend(tiles)
        elif scene in val_scenes:
            splits["val"].extend(tiles)
        else:
            splits["train"].extend(tiles)

    for key in splits:
        splits[key].sort(key=_pair_sort_key)
    return splits


def split_pairs(
    pairs: Sequence[TilePair],
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    seed: int = 1337,
    strategy: str = "auto",
    positive_flags: Optional[Dict[str, bool]] = None,
) -> Dict[str, List[TilePair]]:
    """
    Build train/val/test splits without silently degenerating.

    strategy:
      "auto"        - scene split when there are >= 3 distinct scenes, else
                      contiguous blocks. Never falls back to a random tile split.
      "scene"       - group by scene key.
      "contiguous"  - contiguous blocks of tile order (spatially disjoint for
                      raster-ordered tiles).
      "stratified"  - stratified random split; requires `positive_flags` and is
                      NOT spatially disjoint.

    Raises ValueError when the requested configuration cannot produce three
    non-empty, genuinely distinct splits, instead of quietly evaluating the model
    on its own training data.
    """
    if not pairs:
        raise ValueError("Cannot split an empty tile set")
    if strategy not in SPLIT_STRATEGIES:
        raise ValueError(f"Unknown split strategy {strategy!r}; expected one of {SPLIT_STRATEGIES}")

    distinct_scenes = len({p.scene_key for p in pairs})

    if strategy == "auto":
        strategy = "scene" if distinct_scenes >= 3 else "contiguous"

    if strategy == "scene":
        splits = _scene_splits(pairs, val_fraction, test_fraction, seed)
    elif strategy == "contiguous":
        splits = _contiguous_splits(pairs, val_fraction, test_fraction)
    else:
        if not positive_flags:
            raise ValueError("stratified splitting requires positive_flags")
        splits = _stratified_splits(pairs, val_fraction, test_fraction, seed, positive_flags)

    problems: List[str] = []
    for name in ("train", "val", "test"):
        if not splits[name]:
            problems.append(f"{name} split is empty ({len(splits[name])} tiles)")
    if problems:
        raise ValueError(
            f"Split strategy {strategy!r} could not produce three usable splits: "
            + "; ".join(problems)
            + f" (tiles={len(pairs)}, distinct_scenes={distinct_scenes}). "
            "Refusing to fall back to evaluating on the training data."
        )

    return splits


def split_summary(
    splits: Dict[str, List[TilePair]],
    strategy: Optional[str] = None,
    positive_flags: Optional[Dict[str, bool]] = None,
) -> Dict[str, object]:
    """Honest, reportable description of the split actually used."""
    summary: Dict[str, object] = {"strategy": strategy}
    for name, tiles in splits.items():
        scenes = sorted({t.scene_key for t in tiles})
        entry: Dict[str, object] = {
            "tiles": len(tiles),
            "scenes": len(scenes),
            "scene_keys": scenes[:25],
        }
        if tiles:
            entry["first_tile"] = tiles[0].tile_id
            entry["last_tile"] = tiles[-1].tile_id
        if positive_flags is not None:
            pos = sum(1 for t in tiles if positive_flags.get(t.tile_id, False))
            entry["building_positive_tiles"] = pos
            entry["building_positive_fraction"] = round(pos / len(tiles), 6) if tiles else 0.0
        summary[name] = entry
    summary["distinct_scenes"] = len({t.scene_key for tiles in splits.values() for t in tiles})
    return summary


class FootprintTileDataset:
    """
    Serves (image, mask) float32 tensors for a list of tile pairs.

    Images are scaled to [0, 1]; masks are decoded to {0, 1} via decode_mask().
    torch is imported lazily so this module stays importable without it.
    """

    def __init__(
        self,
        pairs: Sequence[TilePair],
        tile_size: Optional[int] = 512,
        augment: bool = False,
        seed: int = 1337,
        mask_color: Optional[Sequence[int]] = None,
        mask_tolerance: int = 0,
        random_crop: bool = False,
    ):
        self.pairs = list(pairs)
        self.tile_size = tile_size
        self.augment = augment
        self.seed = seed
        self.mask_color = tuple(mask_color) if mask_color is not None else None
        self.mask_tolerance = int(mask_tolerance)
        self.random_crop = bool(random_crop)
        self._epoch = 0
        if not self.pairs:
            raise ValueError("FootprintTileDataset requires at least one tile pair")

    def set_epoch(self, epoch: int) -> None:
        """Reseed crop/flip randomness so each epoch sees different crops."""
        self._epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.pairs)

    def _load(self, pair: TilePair):
        from PIL import Image

        image = Image.open(pair.image_path)
        image = image.convert("RGB") if image.mode != "RGB" else image
        mask = Image.open(pair.mask_path)

        if self.tile_size and self.random_crop and self.augment:
            width, height = image.size
            if width >= self.tile_size and height >= self.tile_size:
                rng = random.Random(f"{self.seed}:{pair.tile_id}:{self._epoch}")
                left = rng.randrange(0, width - self.tile_size + 1)
                top = rng.randrange(0, height - self.tile_size + 1)
                box = (left, top, left + self.tile_size, top + self.tile_size)
                image = image.crop(box)
                mask = mask.crop(box)

        if self.tile_size and image.size != (self.tile_size, self.tile_size):
            image = image.resize((self.tile_size, self.tile_size), Image.BILINEAR)
            mask = mask.resize((self.tile_size, self.tile_size), Image.NEAREST)

        image_arr = np.asarray(image, dtype="float32") / 255.0
        mask_arr = decode_mask(np.asarray(mask), self.mask_color, self.mask_tolerance)
        return image_arr, mask_arr

    def __getitem__(self, index: int):
        import torch

        pair = self.pairs[index]
        image, mask = self._load(pair)

        if self.augment:
            rng = random.Random(f"{self.seed}:{pair.tile_id}:{self._epoch}")
            if rng.random() < 0.5:
                image = np.ascontiguousarray(image[:, ::-1, :])
                mask = np.ascontiguousarray(mask[:, ::-1])
            if rng.random() < 0.5:
                image = np.ascontiguousarray(image[::-1, :, :])
                mask = np.ascontiguousarray(mask[::-1, :])

        image_tensor = torch.from_numpy(image.transpose(2, 0, 1))
        mask_tensor = torch.from_numpy(mask).unsqueeze(0)
        return image_tensor.float(), mask_tensor.float()


def dataset_stats(
    pairs: Sequence[TilePair],
    max_samples: int = 8,
    mask_color: Optional[Sequence[int]] = None,
    mask_tolerance: int = 0,
) -> Dict[str, object]:
    """Cheap integrity check before training: sizes, dtypes and mask coverage."""
    from PIL import Image

    stats: Dict[str, object] = {"checked": 0, "sizes": {}, "mask_positive_fraction": []}
    for pair in list(pairs)[:max_samples]:
        with Image.open(pair.image_path) as img:
            size = img.size
            mode = img.mode
        with Image.open(pair.mask_path) as m:
            arr = np.asarray(m)
        decoded = decode_mask(arr, mask_color, mask_tolerance)
        stats["sizes"][pair.image_path.name] = {"size": size, "mode": mode}
        stats["mask_positive_fraction"].append(float(decoded.mean()))
        stats["checked"] += 1
    if stats["mask_positive_fraction"]:
        stats["mask_positive_fraction_mean"] = round(
            float(np.mean(stats["mask_positive_fraction"])), 6
        )
    stats["mask_color"] = list(mask_color) if mask_color is not None else None
    return stats


def write_split_manifest(
    splits: Dict[str, List[TilePair]],
    out_path: Path,
    strategy: Optional[str] = None,
    positive_flags: Optional[Dict[str, bool]] = None,
) -> Path:
    """Persist exactly which tiles went to which split - reproducible evidence."""
    payload = split_summary(splits, strategy=strategy, positive_flags=positive_flags)
    payload["tiles"] = {name: [t.tile_id for t in tiles] for name, tiles in splits.items()}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def split_fingerprint(splits: Dict[str, List[TilePair]]) -> str:
    """Stable hash of the split membership, so a run can be tied to its split."""
    digest = hashlib.sha256()
    for name in sorted(splits):
        digest.update(name.encode())
        for tile in splits[name]:
            digest.update(tile.tile_id.encode())
            digest.update(b"|")
    return digest.hexdigest()[:16]

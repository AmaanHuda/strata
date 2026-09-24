"""
Leakage and dataset-discovery tests (no torch required).

SIH 2026 PS 26011 - ML Engine

AGENTS.md section 5 and GROUND_TRUTH_MATRIX.md section 3 require spatial /
scene-level splits. These tests enforce that tiles from one scene can never
straddle train/val/test, which is the leakage mode that inflates segmentation
scores.
"""
from pathlib import Path

import numpy as np
import pytest

from src.building_extraction.dataset import (
    TilePair,
    _infer_scene_key,
    describe_layout,
    discover_tiles,
    split_pairs,
    split_summary,
    write_split_manifest,
)


def _make_pairs(n_scenes: int, tiles_per_scene: int):
    pairs = []
    for scene in range(n_scenes):
        scene_key = f"scene{scene:02d}"
        for tile in range(tiles_per_scene):
            pairs.append(
                TilePair(
                    image_path=Path(f"{scene_key}/images/patch{tile:04d}.png"),
                    mask_path=Path(f"{scene_key}/masks/patch{tile:04d}_mask.png"),
                    scene_key=scene_key,
                    tile_id=f"{scene_key}_patch{tile:04d}",
                )
            )
    return pairs


def test_no_scene_straddles_two_splits():
    splits = split_pairs(_make_pairs(n_scenes=10, tiles_per_scene=5), val_fraction=0.2, test_fraction=0.2, seed=7)
    # Invariant: a scene belongs to exactly ONE split. Repeats within the same
    # split are expected, because one scene yields many tiles.
    seen = {}
    for name, tiles in splits.items():
        for tile in tiles:
            previous = seen.get(tile.scene_key)
            assert previous is None or previous == name, (
                f"scene {tile.scene_key} straddles {previous} and {name}"
            )
            seen[tile.scene_key] = name
    assert len(seen) == 10


def test_every_tile_is_accounted_for_exactly_once():
    pairs = _make_pairs(n_scenes=8, tiles_per_scene=4)
    splits = split_pairs(pairs, seed=3)
    total = sum(len(tiles) for tiles in splits.values())
    assert total == len(pairs)
    ids = [t.tile_id for tiles in splits.values() for t in tiles]
    assert len(ids) == len(set(ids))


def test_split_is_deterministic_for_the_same_seed():
    pairs = _make_pairs(n_scenes=12, tiles_per_scene=3)
    first = {k: [t.tile_id for t in v] for k, v in split_pairs(pairs, seed=11).items()}
    second = {k: [t.tile_id for t in v] for k, v in split_pairs(pairs, seed=11).items()}
    assert first == second


def test_train_split_is_never_empty_for_tiny_datasets():
    splits = split_pairs(_make_pairs(n_scenes=3, tiles_per_scene=2), val_fraction=0.34, test_fraction=0.34, seed=1)
    assert len(splits["train"]) > 0


def test_split_summary_reports_scene_counts():
    summary = split_summary(split_pairs(_make_pairs(n_scenes=6, tiles_per_scene=2), seed=5))
    assert set(summary) == {"train", "val", "test", "strategy", "distinct_scenes"}
    for name in ("train", "val", "test"):
        assert "tiles" in summary[name] and "scenes" in summary[name]


def test_split_summary_reports_building_density_when_flags_are_supplied():
    """Split density must be reportable - a density shift must not go unreported."""
    splits = split_pairs(_make_pairs(n_scenes=6, tiles_per_scene=2), seed=5)
    flags = {t.tile_id: (t.tile_id.endswith("0001")) for tiles in splits.values() for t in tiles}
    summary = split_summary(splits, strategy="scene", positive_flags=flags)
    for name in ("train", "val", "test"):
        assert "building_positive_fraction" in summary[name]
        assert 0.0 <= summary[name]["building_positive_fraction"] <= 1.0


def test_scene_key_is_stripped_from_tile_index():
    assert _infer_scene_key(Path("scene04_patch_0123.png"), Path(".")) == "scene04"
    assert _infer_scene_key(Path("siteA_tile12.tif"), Path(".")) == "siteA"


def test_discover_tiles_pairs_images_with_masks(tmp_path):
    from PIL import Image

    images_dir = tmp_path / "scene01" / "images"
    masks_dir = tmp_path / "scene01" / "masks"
    images_dir.mkdir(parents=True)
    masks_dir.mkdir(parents=True)

    image = (np.random.rand(16, 16, 3) * 255).astype("uint8")
    mask = np.zeros((16, 16), dtype="uint8")
    mask[4:10, 4:10] = 255
    Image.fromarray(image).save(images_dir / "scene01_patch_0001.png")
    Image.fromarray(mask).save(masks_dir / "scene01_patch_0001_mask.png")

    pairs = discover_tiles(tmp_path)
    assert len(pairs) == 1
    assert pairs[0].mask_path.name == "scene01_patch_0001_mask.png"
    assert pairs[0].scene_key.startswith("scene01")


def test_discover_tiles_fails_loudly_on_an_empty_or_unpaired_tree(tmp_path):
    """A failed download must not look like a valid empty dataset."""
    (tmp_path / "scene01" / "images").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="No image/mask tile pairs"):
        discover_tiles(tmp_path)


def test_describe_layout_reports_extensions(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.tif").write_bytes(b"1")
    info = describe_layout(tmp_path)
    assert info["exists"] is True
    assert info["file_extension_counts"].get(".tif") == 1


def test_write_split_manifest_records_tiles(tmp_path):
    splits = split_pairs(_make_pairs(n_scenes=4, tiles_per_scene=2), seed=2)
    out = write_split_manifest(splits, tmp_path / "split_manifest.json")
    assert out.exists()
    assert "train" in out.read_text(encoding="utf-8")


def _indexed_pairs(n: int, positives: set):
    """One-scene raster-ordered tile set, mirroring the real SVAMITVA layout."""
    pairs = []
    for i in range(1, n + 1):
        pairs.append(
            TilePair(
                image_path=Path(f"ds/Images/patch_{i}.png"),
                mask_path=Path(f"ds/Masks/patch_{i}.png"),
                scene_key="ds",
                tile_id=f"patch_{i}",
                tile_index=i,
            )
        )
    return pairs, {f"patch_{i}": (i in positives) for i in range(1, n + 1)}


def test_single_scene_dataset_never_collapses_val_and_test_into_train():
    """
    A raster of one survey yields one inferred scene. The old behaviour put every
    tile in train and then evaluated on train, silently reporting training scores
    as test scores.
    """
    pairs, flags = _indexed_pairs(100, positives=set(range(40, 100)))
    splits = split_pairs(pairs, val_fraction=0.15, test_fraction=0.15, strategy="auto", positive_flags=flags)
    # 1 distinct scene -> auto must pick contiguous, never a random tile split.
    train_ids = {t.tile_id for t in splits["train"]}
    val_ids = {t.tile_id for t in splits["val"]}
    test_ids = {t.tile_id for t in splits["test"]}
    assert train_ids and val_ids and test_ids
    assert not (train_ids & val_ids) and not (train_ids & test_ids) and not (val_ids & test_ids)
    assert len(train_ids | val_ids | test_ids) == 100


def test_contiguous_split_is_monotonic_in_tile_order():
    """Contiguous blocks are spatially disjoint for raster-ordered tiles."""
    pairs, flags = _indexed_pairs(60, positives=set(range(1, 61)))
    splits = split_pairs(pairs, val_fraction=0.2, test_fraction=0.2, strategy="contiguous", positive_flags=flags)
    idx = {name: [t.tile_index for t in tiles] for name, tiles in splits.items()}
    for name, values in idx.items():
        assert values == sorted(values), f"{name} is not in tile order"
    assert max(idx["train"]) < min(idx["val"]) < max(idx["val"]) < min(idx["test"])


def test_stratified_split_matches_building_density():
    pairs, flags = _indexed_pairs(100, positives=set(range(30, 70)))
    splits = split_pairs(pairs, val_fraction=0.2, test_fraction=0.2, strategy="stratified", positive_flags=flags, seed=5)
    fracs = {}
    for name, tiles in splits.items():
        fracs[name] = sum(1 for t in tiles if flags[t.tile_id]) / len(tiles)
    assert abs(fracs["test"] - fracs["train"]) < 0.15


def test_degenerate_split_raises_instead_of_evaluating_on_train():
    """Too few tiles for three disjoint splits must fail loudly, not silently."""
    pairs, flags = _indexed_pairs(2, positives=set())
    with pytest.raises(ValueError, match="could not produce three usable splits"):
        split_pairs(pairs, val_fraction=0.4, test_fraction=0.4, strategy="contiguous", positive_flags=flags)


def test_unknown_split_strategy_is_rejected():
    pairs, _ = _indexed_pairs(10, positives=set())
    with pytest.raises(ValueError, match="Unknown split strategy"):
        split_pairs(pairs, strategy="random-tiles")


def test_explicit_dirs_ignore_a_decoy_colormapped_mask_folder(tmp_path):
    """
    Real trap: the SVAMITVA tree ships FilteredData/BinaryMasks (a matplotlib
    colormapped image) next to the authoritative Masks. Heuristic discovery can
    pair imagery with the colormapped copy and train on garbage labels. Explicit
    directories must pair only what is asked for.
    """
    from PIL import Image

    images = tmp_path / "Full Data" / "Images"
    masks = tmp_path / "Full Data" / "Masks"
    decoy = tmp_path / "FilteredData" / "BinaryMasks"
    for d in (images, masks, decoy):
        d.mkdir(parents=True)

    Image.fromarray((np.random.rand(16, 16, 3) * 255).astype("uint8")).save(images / "patch_1.png")
    Image.fromarray(np.zeros((16, 16, 3), dtype="uint8")).save(masks / "patch_1.png")
    Image.fromarray(np.zeros((16, 16, 4), dtype="uint8")).save(decoy / "patch_1.png")

    pairs = discover_tiles(tmp_path, images_dir=images, masks_dir=masks)
    assert len(pairs) == 1
    assert pairs[0].mask_path == masks / "patch_1.png"
    # The scene label must describe the dataset, not the imagery folder name.
    assert pairs[0].scene_key == "Full Data"


def test_explicit_dirs_report_unmatched_images_loudly(tmp_path, capsys):
    from PIL import Image

    images = tmp_path / "Images"
    masks = tmp_path / "Masks"
    images.mkdir(parents=True)
    masks.mkdir(parents=True)
    Image.fromarray(np.zeros((8, 8, 3), dtype="uint8")).save(images / "patch_1.png")
    Image.fromarray(np.zeros((8, 8), dtype="uint8")).save(masks / "patch_1.png")
    Image.fromarray(np.zeros((8, 8, 3), dtype="uint8")).save(images / "patch_2.png")

    pairs = discover_tiles(tmp_path, images_dir=images, masks_dir=masks)
    assert len(pairs) == 1
    assert "patch_2.png" in capsys.readouterr().out


def test_building_colour_decoding_separates_classes_from_background():
    """
    SVAMITVA masks are RGB class colourings. 'pixel > 0' would mark Field, Road,
    Water and Other as building; only the Building colour may become foreground.
    """
    from src.building_extraction.dataset import decode_mask

    building, field, road, water, other, background = (
        (0, 110, 255),
        (85, 217, 48),
        (255, 0, 0),
        (0, 238, 255),
        (200, 255, 0),
        (0, 0, 0),
    )
    mask = np.zeros((6, 1, 3), dtype="uint8")
    for row, colour in enumerate((building, field, road, water, other, background)):
        mask[row, 0] = colour

    decoded = decode_mask(mask, building, tolerance=0)
    assert decoded.shape == (6, 1)
    assert decoded[0, 0] == 1.0, "Building must be foreground"
    assert decoded[1:, 0].sum() == 0.0, "no other class may be foreground"


def test_decoding_an_rgb_mask_without_a_colour_is_refused():
    from src.building_extraction.dataset import decode_mask

    mask = np.zeros((4, 4, 3), dtype="uint8")
    mask[:, :] = (85, 217, 48)
    with pytest.raises(ValueError, match="multi-colour RGB"):
        decode_mask(mask, mask_color=None)


def test_grayscale_binary_masks_still_decode_without_a_colour():
    from src.building_extraction.dataset import decode_mask

    mask = np.zeros((4, 4), dtype="uint8")
    mask[1:3, 1:3] = 255
    assert decode_mask(mask, mask_color=None).sum() == 4.0


def test_colour_decoding_tolerates_lossy_reencoding_only_within_tolerance():
    from src.building_extraction.dataset import decode_mask

    mask = np.zeros((1, 2, 3), dtype="uint8")
    mask[0, 0] = (0, 110, 255)
    mask[0, 1] = (6, 116, 255)
    assert decode_mask(mask, (0, 110, 255), tolerance=0).sum() == 1.0
    assert decode_mask(mask, (0, 110, 255), tolerance=8).sum() == 2.0


def test_nodata_blank_tiles_are_excluded_and_reported():
    """Near-black orthomosaic padding is not verified empty ground."""
    from src.building_extraction.dataset import filter_blank_tiles

    pairs, _ = _indexed_pairs(4, positives={1})
    scan = {
        "patch_1": {"building_fraction": 0.2, "blank_fraction": 0.0},
        "patch_2": {"building_fraction": 0.0, "blank_fraction": 0.95},
        "patch_3": {"building_fraction": 0.0, "blank_fraction": 0.10},
        "patch_4": {"building_fraction": 0.0, "blank_fraction": 1.00},
    }
    kept, dropped = filter_blank_tiles(pairs, scan, max_blank_fraction=0.90)
    assert {p.tile_id for p in kept} == {"patch_1", "patch_3"}
    assert {p.tile_id for p in dropped} == {"patch_2", "patch_4"}


def test_scan_dataset_measures_both_building_and_blankness(tmp_path):
    from PIL import Image
    from src.building_extraction.dataset import scan_dataset

    images = tmp_path / "Images"
    masks = tmp_path / "Masks"
    images.mkdir()
    masks.mkdir()

    image = np.full((16, 16, 3), 120, dtype="uint8")
    Image.fromarray(image).save(images / "patch_1.png")
    mask = np.zeros((16, 16, 3), dtype="uint8")
    mask[0:8, :] = (0, 110, 255)
    Image.fromarray(mask).save(masks / "patch_1.png")

    Image.fromarray(np.zeros((16, 16, 3), dtype="uint8")).save(images / "patch_2.png")
    Image.fromarray(np.zeros((16, 16, 3), dtype="uint8")).save(masks / "patch_2.png")

    pairs = discover_tiles(tmp_path, images_dir=images, masks_dir=masks)
    cache = tmp_path / "cache" / "scan.json"
    scan = scan_dataset(pairs, (0, 110, 255), 0, cache_path=cache)

    assert abs(scan["patch_1"]["building_fraction"] - 0.5) < 1e-6
    assert scan["patch_1"]["blank_fraction"] == 0.0
    assert scan["patch_2"]["blank_fraction"] == 1.0
    assert cache.exists(), "the scan must be cached so re-runs do not re-decode"

    reused = scan_dataset(pairs, (0, 110, 255), 0, cache_path=cache)
    assert reused["patch_1"]["building_fraction"] == scan["patch_1"]["building_fraction"]

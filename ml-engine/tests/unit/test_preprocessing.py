"""
Unit tests for image tiling, vector simplification, and data normalization.
SIH 2026 PS 26011 - ML Engine
"""
import pytest
import numpy as np
from src.preprocessing.tiling import (
    generate_tile_windows,
    extract_tiles,
)
from src.preprocessing.vector_ops import (
    simplify_polygon_rdp,
    remove_duplicate_consecutive_vertices,
)
from src.preprocessing.normalization import (
    normalize_min_max,
    normalize_percentile,
    normalize_zscore,
)


class TestTiling:
    def test_tile_window_generation(self):
        # 1024x1024 image with 512x512 tile and 64 overlap
        windows = generate_tile_windows(height=1024, width=1024, tile_size=512, overlap=64)
        assert len(windows) > 1
        for w in windows:
            assert w.row_max - w.row_min == 512
            assert w.col_max - w.col_min == 512

    def test_extract_tiles(self):
        img = np.ones((1000, 1000, 3), dtype=np.uint8) * 128
        tiles, windows = extract_tiles(img, tile_size=512, overlap=64)
        assert len(tiles) == len(windows)
        assert tiles[0].shape == (512, 512, 3)


class TestVectorOps:
    def test_rdp_simplification(self):
        # A straight line with slight perturbation in middle
        coords = [(0, 0), (5, 0.1), (10, 0), (10, 10), (0, 10), (0, 0)]
        simplified = simplify_polygon_rdp(coords, tolerance=0.5)
        # The point (5, 0.1) should be removed
        assert len(simplified) < len(coords)
        assert (5, 0.1) not in simplified

    def test_duplicate_vertex_removal(self):
        coords = [(0, 0), (0, 0), (10, 0), (10, 0), (10, 10), (0, 0)]
        dedup = remove_duplicate_consecutive_vertices(coords)
        assert len(dedup) == 4


class TestNormalization:
    def test_min_max_normalization(self):
        arr = np.array([[0, 50], [100, 200]], dtype=np.float32)
        norm = normalize_min_max(arr)
        assert np.isclose(norm.min(), 0.0)
        assert np.isclose(norm.max(), 1.0)
        assert np.isclose(norm[0, 1], 0.25)

    def test_percentile_normalization(self):
        arr = np.linspace(0, 100, 100)
        norm = normalize_percentile(arr, p_min=10.0, p_max=90.0)
        assert norm.min() == 0.0
        assert norm.max() == 1.0

    def test_zscore_normalization(self):
        arr = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        norm = normalize_zscore(arr)
        assert np.isclose(np.mean(norm), 0.0, atol=1e-6)
        assert np.isclose(np.std(norm), 1.0, atol=1e-6)

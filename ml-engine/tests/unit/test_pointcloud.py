"""
Unit tests for point cloud and elevation metrics.
SIH 2026 PS 26011 - ML Engine
"""
import pytest
import numpy as np
from src.pointcloud.elevation import (
    compute_ndsm,
    extract_height_metrics,
    estimate_floor_count,
)
from src.pointcloud.filtering import (
    statistical_outlier_removal,
    filter_invalid_z,
    fill_nodata_nearest,
)
from src.pointcloud.metadata import (
    create_pointcloud_metadata_summary,
)


class TestElevationProcessing:
    def test_compute_ndsm(self):
        # Ground at 100m, building at 115m -> nDSM = 15m
        dsm = np.array([[115.0, 100.0], [100.0, 120.0]], dtype=np.float32)
        dtm = np.array([[100.0, 100.0], [100.0, 100.0]], dtype=np.float32)
        ndsm = compute_ndsm(dsm, dtm)
        assert np.isclose(ndsm[0, 0], 15.0)
        assert np.isclose(ndsm[0, 1], 0.0)
        assert np.isclose(ndsm[1, 1], 20.0)

    def test_extract_height_metrics(self):
        patch = np.array([
            [12.0, 12.5, 12.0],
            [12.2, 13.0, 12.4],
            [12.1, 12.3, 12.5]
        ], dtype=np.float32)
        metrics = extract_height_metrics(patch)
        assert metrics["valid_pixels"] == 9
        assert metrics["min_height"] == 12.0
        assert metrics["max_height"] == 13.0
        assert 12.0 <= metrics["mean_height"] <= 13.0
        assert metrics["median_height"] is not None

    def test_estimate_floor_count(self):
        assert estimate_floor_count(12.0, floor_height_m=3.0) == 4
        assert estimate_floor_count(15.5, floor_height_m=3.0) == 5
        assert estimate_floor_count(0.0) is None
        assert estimate_floor_count(None) is None


class TestPointCloudFiltering:
    def test_filter_invalid_z(self):
        elevations = np.array([50.0, 120.0, -999.0, 15000.0])
        filtered = filter_invalid_z(elevations, min_z=-500.0, max_z=9000.0)
        assert not np.isnan(filtered[0])
        assert not np.isnan(filtered[1])
        assert np.isnan(filtered[2])
        assert np.isnan(filtered[3])

    def test_statistical_outlier_removal(self):
        data = np.array([10.0, 10.1, 9.9, 10.2, 10.0, 100.0])
        cleaned = statistical_outlier_removal(data, k_std=2.0)
        assert np.isnan(cleaned[-1])  # 100.0 is an outlier
        assert not np.isnan(cleaned[0])

    def test_fill_nodata_nearest(self):
        grid = np.array([[10.0, -9999.0], [10.0, 10.0]], dtype=np.float32)
        filled = fill_nodata_nearest(grid, nodata_val=-9999.0)
        assert np.isclose(filled[0, 1], 10.0)


class TestPointCloudMetadata:
    def test_metadata_summary(self):
        meta = create_pointcloud_metadata_summary(
            point_count=50000,
            bbox=(500000, 2000000, 10, 500100, 2000100, 30),
            crs="EPSG:32643"
        )
        assert meta["point_count"] == 50000
        assert meta["coverage_area_sqm"] == 10000.0
        assert meta["density_points_per_sqm"] == 5.0
        assert meta["crs"] == "EPSG:32643"

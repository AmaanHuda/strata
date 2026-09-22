"""
Unit tests for Advanced AI tasks: Change detection, 3D Mesh Exporters, Strata Partitioner, DL Wrappers.
SIH 2026 PS 26011 - ML Engine
"""
import pytest
import numpy as np
from src.change_detection.detector import MultiTemporalChangeDetector
from src.reconstruction.exporters import export_to_cityjson, export_to_wavefront_obj, export_to_geojson_polygonz
from src.units.partitioner import StrataUnitPartitioner
from src.building_extraction.dl_models import UNetFootprintModel
from src.height.dl_height import DeepHeightEstimator


class TestChangeDetection:
    def test_spectral_difference(self):
        cd = MultiTemporalChangeDetector()
        img1 = np.zeros((100, 100), dtype=np.uint8)
        img2 = np.zeros((100, 100), dtype=np.uint8)
        img2[20:80, 20:80] = 200  # New bright feature

        res = cd.compute_spectral_difference(img1, img2)
        assert res["has_significant_change"] is True
        assert res["change_fraction"] > 0.10

    def test_vertical_extension_detection(self):
        cd = MultiTemporalChangeDetector(height_change_threshold_m=2.5)
        poly = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        res = cd.detect_building_change(poly, poly, height_t1=9.0, height_t2=18.0)
        assert res["change_type"] == "VERTICAL_EXTENSION"
        assert res["delta_height_m"] == 9.0
        assert res["estimated_floors_added"] == 3
        assert res["review_required"] is True


class Test3DExporters:
    def test_cityjson_export(self):
        poly = [(72.825, 18.975), (72.826, 18.975), (72.826, 18.976), (72.825, 18.976), (72.825, 18.975)]
        cj = export_to_cityjson("BLD-01", "MH-MUM-001", poly, height_m=15.0)
        assert cj["type"] == "CityJSON"
        assert "BLD-01" in cj["CityObjects"]
        assert len(cj["vertices"]) == 8  # 4 bottom + 4 top

    def test_wavefront_obj_export(self):
        poly = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        obj_text = export_to_wavefront_obj(poly, height_m=12.0)
        assert "o CadastralBuilding" in obj_text
        assert "v 0.000000 0.000000 0.00" in obj_text
        assert "f " in obj_text

    def test_geojson_polygonz_export(self):
        poly = [(72.8, 19.0), (72.81, 19.0), (72.81, 19.01), (72.8, 19.01), (72.8, 19.0)]
        feat = export_to_geojson_polygonz("BLD-01", "MH-MUM-001", poly, height_m=20.0)
        assert feat["type"] == "Feature"
        assert feat["properties"]["height_m"] == 20.0
        assert len(feat["geometry"]["coordinates"]) == 2  # base and top rings


class TestStrataUnitPartitioner:
    def test_partition_multi_unit(self):
        partitioner = StrataUnitPartitioner(floor_height_m=3.0)
        poly = [(0, 0), (20, 0), (20, 10), (0, 10), (0, 0)]
        units = partitioner.partition_floor_into_units(
            ulpin="MH-MUM-001",
            building_id="BLD-01",
            floor_level=2,
            footprint_coords=poly,
            unit_count_per_floor=2,
            base_elevation_m=5.0
        )
        assert len(units) == 2
        assert units[0]["floor_id"] == "FL-02"
        assert units[0]["z_min_m"] == 8.0  # 5.0 + 3.0
        assert units[0]["z_max_m"] == 11.0 # 8.0 + 3.0
        assert units[0]["unit_id"] == "UNIT-0201"
        assert units[1]["unit_id"] == "UNIT-0202"


class TestDeepLearningWrappers:
    def test_unet_segmentation(self):
        model = UNetFootprintModel()
        chip = np.ones((128, 128, 3), dtype=np.uint8) * 180
        res = model.segment(chip)
        assert res["binary_mask"].shape == (128, 128)
        assert "probability_map" in res
        assert res["model_version"] == "1.0.0-unet-cartosat"

    def test_deep_height_estimator(self):
        model = DeepHeightEstimator()
        chip = np.ones((64, 64, 3), dtype=np.uint8) * 150
        res = model.estimate_building_height(chip)
        assert res["estimated_height_m"] > 0.0
        assert res["confidence"] > 0.0

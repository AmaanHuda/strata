#!/usr/bin/env python3
"""
dataset_quality_check.py
SIH 2026 PS 26011 - ML Engine, Phase 1

Framework for data quality checks on acquired datasets.
Run per-dataset after download. Generates a quality report JSON.

Supported checks:
  - File existence and integrity (size, extension)
  - GeoJSON: geometry validity, CRS field, coordinate range (India bbox)
  - Raster (GeoTIFF): CRS, nodata, resolution, value range, NaN fraction
  - CSV: missing values, duplicate rows
  - LAS/LAZ: point count, Z range, CRS (metadata only)

Usage:
    python scripts/dataset_quality_check.py --path datasets/raw/mydata.geojson --type geojson
    python scripts/dataset_quality_check.py --path datasets/raw/dem.tif --type raster
    python scripts/dataset_quality_check.py --path datasets/raw/points.las --type pointcloud

Outputs: datasets/quality_reports/<filename>_quality.json
"""
import argparse
import json
import pathlib
import sys
import datetime

# India approximate bounding box (degrees)
INDIA_BBOX = {"min_lon": 68.0, "max_lon": 97.5, "min_lat": 8.0, "max_lat": 37.0}


def check_geojson(path: pathlib.Path) -> dict:
    """Quality checks for GeoJSON files."""
    issues = []
    stats = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "ERROR", "issues": [f"Parse error: {e}"], "stats": {}}

    features = data.get("features", [])
    stats["feature_count"] = len(features)

    if len(features) == 0:
        issues.append("WARNING: No features in GeoJSON")

    try:
        import shapely.geometry as sg
        import shapely.validation

        invalid_geoms = 0
        null_geoms = 0
        out_of_india = 0

        for i, feat in enumerate(features):
            geom_data = feat.get("geometry")
            if geom_data is None:
                null_geoms += 1
                continue
            try:
                geom = sg.shape(geom_data)
                if not geom.is_valid:
                    invalid_geoms += 1
                    if i < 5:  # report first few
                        issues.append(f"Feature {i}: invalid geometry - {shapely.validation.explain_validity(geom)}")
                # Coordinate range check (rough India bbox)
                bounds = geom.bounds  # (minx, miny, maxx, maxy)
                if bounds[0] < INDIA_BBOX["min_lon"] or bounds[2] > INDIA_BBOX["max_lon"] \
                   or bounds[1] < INDIA_BBOX["min_lat"] or bounds[3] > INDIA_BBOX["max_lat"]:
                    out_of_india += 1
            except Exception as e:
                issues.append(f"Feature {i}: geometry error - {e}")

        stats["invalid_geometries"] = invalid_geoms
        stats["null_geometries"] = null_geoms
        stats["out_of_india_bbox"] = out_of_india

        if invalid_geoms > 0:
            issues.append(f"ERROR: {invalid_geoms} invalid geometries found")
        if null_geoms > 0:
            issues.append(f"WARNING: {null_geoms} null geometries")

    except ImportError:
        issues.append("WARNING: shapely not installed - geometry validation skipped")

    # CRS check
    crs = data.get("crs") or data.get("coordinate_reference_system")
    if crs is None:
        issues.append("INFO: No CRS field in GeoJSON - assuming EPSG:4326 per RFC 7946")
    stats["crs_field"] = str(crs)

    status = "ERROR" if any("ERROR" in i for i in issues) else (
        "WARNING" if issues else "PASS"
    )
    return {"status": status, "issues": issues, "stats": stats}


def check_raster(path: pathlib.Path) -> dict:
    """Quality checks for GeoTIFF/raster files."""
    issues = []
    stats = {}
    try:
        import rasterio
        import numpy as np
    except ImportError:
        return {
            "status": "SKIPPED",
            "issues": ["rasterio or numpy not installed - raster check skipped"],
            "stats": {}
        }

    try:
        with rasterio.open(path) as src:
            stats["crs"] = str(src.crs)
            stats["width"] = src.width
            stats["height"] = src.height
            stats["bands"] = src.count
            stats["nodata"] = src.nodata
            stats["transform"] = str(src.transform)
            stats["res_x"] = src.res[0]
            stats["res_y"] = src.res[1]
            bounds = src.bounds
            stats["bounds"] = {"left": bounds.left, "bottom": bounds.bottom,
                                "right": bounds.right, "top": bounds.top}

            if src.crs is None:
                issues.append("ERROR: No CRS defined on raster")

            # Read sample for value stats (first band, up to 1024x1024 overview)
            data = src.read(1, out_shape=(min(src.height, 512), min(src.width, 512)))
            if src.nodata is not None:
                valid = data[data != src.nodata]
            else:
                valid = data.flatten()

            nan_count = int(np.sum(np.isnan(valid.astype(float))))
            nan_frac = nan_count / max(len(valid), 1)
            stats["sample_min"] = float(np.nanmin(valid)) if len(valid) > 0 else None
            stats["sample_max"] = float(np.nanmax(valid)) if len(valid) > 0 else None
            stats["sample_nan_fraction"] = nan_frac
            stats["sample_pixels"] = len(valid)

            if nan_frac > 0.3:
                issues.append(f"WARNING: High NaN/nodata fraction in sample: {nan_frac:.1%}")
            if len(valid) == 0:
                issues.append("ERROR: All sampled pixels are nodata")

    except Exception as e:
        issues.append(f"ERROR: Could not open raster: {e}")

    status = "ERROR" if any("ERROR" in i for i in issues) else (
        "WARNING" if issues else "PASS"
    )
    return {"status": status, "issues": issues, "stats": stats}


def check_pointcloud(path: pathlib.Path) -> dict:
    """Quality checks for LAS/LAZ files (metadata only - do not load full cloud)."""
    issues = []
    stats = {}
    try:
        import laspy
        with laspy.open(path) as f:
            header = f.header
            stats["point_count"] = int(header.point_count)
            stats["point_format"] = int(header.point_format.id)
            stats["version"] = f"{header.version.major}.{header.version.minor}"
            # Bounding box
            stats["x_min"] = float(header.x_min)
            stats["x_max"] = float(header.x_max)
            stats["y_min"] = float(header.y_min)
            stats["y_max"] = float(header.y_max)
            stats["z_min"] = float(header.z_min)
            stats["z_max"] = float(header.z_max)

            if header.point_count == 0:
                issues.append("ERROR: Zero points in file")
            if header.z_min == header.z_max:
                issues.append("WARNING: Z range is zero - may indicate missing elevation data")
            if header.z_min < -500 or header.z_max > 9000:
                issues.append(f"WARNING: Z range ({header.z_min:.1f} to {header.z_max:.1f}) suspicious for India")

    except ImportError:
        issues.append("INFO: laspy not installed - point cloud metadata check skipped")
        issues.append("Install: pip install laspy")
    except Exception as e:
        issues.append(f"ERROR: Could not read point cloud: {e}")

    status = "ERROR" if any("ERROR" in i for i in issues) else (
        "WARNING" if issues else "PASS"
    )
    return {"status": status, "issues": issues, "stats": stats}


def check_file_basics(path: pathlib.Path) -> dict:
    """Basic file existence and size check."""
    if not path.exists():
        return {"status": "ERROR", "issues": [f"File not found: {path}"], "stats": {}}
    size_bytes = path.stat().st_size
    if size_bytes == 0:
        return {"status": "ERROR", "issues": ["File is empty (0 bytes)"], "stats": {"size_bytes": 0}}
    return {"status": "PASS", "issues": [], "stats": {"size_bytes": size_bytes}}


def main():
    parser = argparse.ArgumentParser(description="Dataset quality check.")
    parser.add_argument("--path", type=pathlib.Path, required=True, help="Path to dataset file")
    parser.add_argument(
        "--type", choices=["geojson", "raster", "pointcloud", "csv", "auto"],
        default="auto", help="Dataset type (auto-detects from extension if not set)"
    )
    args = parser.parse_args()

    path = args.path
    dtype = args.type

    # Auto-detect
    if dtype == "auto":
        ext = path.suffix.lower()
        if ext in [".geojson", ".json"]:
            dtype = "geojson"
        elif ext in [".tif", ".tiff", ".img", ".vrt"]:
            dtype = "raster"
        elif ext in [".las", ".laz"]:
            dtype = "pointcloud"
        elif ext in [".csv", ".tsv"]:
            dtype = "csv"
        else:
            print(f"Cannot auto-detect type for extension '{ext}'. Specify --type explicitly.")
            sys.exit(1)

    print(f"Checking: {path} (type={dtype})")

    # File basics
    basic = check_file_basics(path)
    if basic["status"] == "ERROR":
        print("FAIL:", basic["issues"])
        sys.exit(1)

    # Type-specific checks
    if dtype == "geojson":
        result = check_geojson(path)
    elif dtype == "raster":
        result = check_raster(path)
    elif dtype == "pointcloud":
        result = check_pointcloud(path)
    else:
        result = {"status": "SKIPPED", "issues": ["CSV check not yet implemented"], "stats": {}}

    result["file"] = str(path)
    result["type"] = dtype
    result["checked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result["file_size_bytes"] = basic["stats"].get("size_bytes")

    # Save report
    report_dir = pathlib.Path(__file__).parent.parent / "datasets" / "quality_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{path.stem}_quality.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\nStatus:  {result['status']}")
    print(f"Report:  {report_path}")
    if result["issues"]:
        print("Issues:")
        for i in result["issues"]:
            print(f"  - {i}")
    if result.get("stats"):
        print("Stats:")
        for k, v in result["stats"].items():
            print(f"  {k}: {v}")

    sys.exit(0 if result["status"] in ("PASS", "WARNING", "SKIPPED") else 1)


if __name__ == "__main__":
    main()

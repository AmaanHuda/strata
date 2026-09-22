"""
Geospatial processing package for SIH 2026 PS 26011 ML Engine.
"""
from src.geospatial.crs import (
    EPSG_WGS84,
    EPSG_WEB_MERCATOR,
    INDIAN_UTM_ZONES,
    INDIA_BBOX,
    get_utm_zone_from_lon,
    get_utm_epsg_for_coordinates,
    is_within_india_bbox,
    lonlat_to_web_mercator,
    web_mercator_to_lonlat,
    approximate_utm_forward,
    transform_coordinates,
)
from src.geospatial.operations import (
    compute_bounding_box,
    calculate_polygon_area,
    calculate_perimeter,
    calculate_compactness,
    calculate_centroid,
    point_in_polygon,
)
from src.geospatial.validation import (
    validate_polygon_geometry,
    check_self_intersection,
)
from src.geospatial.conversion import (
    coords_to_geojson_polygon,
    coords_to_geojson_feature,
    create_geojson_feature_collection,
    geojson_feature_to_coords,
)

__all__ = [
    "EPSG_WGS84",
    "EPSG_WEB_MERCATOR",
    "INDIAN_UTM_ZONES",
    "INDIA_BBOX",
    "get_utm_zone_from_lon",
    "get_utm_epsg_for_coordinates",
    "is_within_india_bbox",
    "lonlat_to_web_mercator",
    "web_mercator_to_lonlat",
    "approximate_utm_forward",
    "transform_coordinates",
    "compute_bounding_box",
    "calculate_polygon_area",
    "calculate_perimeter",
    "calculate_compactness",
    "calculate_centroid",
    "point_in_polygon",
    "validate_polygon_geometry",
    "check_self_intersection",
    "coords_to_geojson_polygon",
    "coords_to_geojson_feature",
    "create_geojson_feature_collection",
    "geojson_feature_to_coords",
]

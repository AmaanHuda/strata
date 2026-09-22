"""
GeoJSON conversion utilities.
SIH 2026 PS 26011 - ML Engine
"""
import uuid
from typing import List, Tuple, Dict, Any, Optional


def coords_to_geojson_polygon(rings: List[List[Tuple[float, float]]]) -> Dict[str, Any]:
    cleaned_rings = []
    for ring in rings:
        r = list(ring)
        if len(r) > 0 and r[0] != r[-1]:
            r.append(r[0])
        cleaned_rings.append([[float(x), float(y)] for x, y in r])

    return {
        "type": "Polygon",
        "coordinates": cleaned_rings
    }


def coords_to_geojson_feature(
    coords: List[Tuple[float, float]],
    properties: Optional[Dict[str, Any]] = None,
    crs: str = "EPSG:4326",
    feature_id: Optional[str] = None
) -> Dict[str, Any]:
    props = properties.copy() if properties else {}
    props["geometry_crs"] = crs

    return {
        "type": "Feature",
        "id": feature_id or str(uuid.uuid4()),
        "geometry": coords_to_geojson_polygon([coords]),
        "properties": props
    }


def create_geojson_feature_collection(
    features: List[Dict[str, Any]],
    crs: str = "EPSG:4326"
) -> Dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": crs}
        },
        "features": features
    }


def geojson_feature_to_coords(feature: Dict[str, Any]) -> List[Tuple[float, float]]:
    geom = feature.get("geometry", {})
    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon" and coords:
        exterior = coords[0]
        return [(float(pt[0]), float(pt[1])) for pt in exterior]
    elif geom_type == "MultiPolygon" and coords and coords[0]:
        exterior = coords[0][0]
        return [(float(pt[0]), float(pt[1])) for pt in exterior]
    else:
        raise ValueError(f"Unsupported geometry type or empty coordinates: {geom_type}")

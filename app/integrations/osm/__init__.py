"""
OpenStreetMap integration (real, traceable cadastral source data).

This package is the ONLY place STRATA talks to OpenStreetMap. Everything it
returns carries the originating OSM type/id so a reviewer can re-fetch the exact
same geometry from the public Overpass API. No geometry is generated here.
"""
from app.integrations.osm.overpass import (
    FLOOR_TO_FLOOR_M,
    OSMBuilding,
    OverpassClient,
    OverpassError,
    derive_floor_count,
    derive_height,
    parse_building_element,
    pick_target_buildings,
)

__all__ = [
    "FLOOR_TO_FLOOR_M",
    "OSMBuilding",
    "OverpassClient",
    "OverpassError",
    "derive_floor_count",
    "derive_height",
    "parse_building_element",
    "pick_target_buildings",
]

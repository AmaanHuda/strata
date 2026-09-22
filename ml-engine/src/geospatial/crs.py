"""
Geospatial CRS Management & Projections for Indian Cadastral Mapping.
SIH 2026 PS 26011 - ML Engine
"""
import math
from typing import List, Tuple, Optional

EPSG_WGS84 = "EPSG:4326"
EPSG_WEB_MERCATOR = "EPSG:3857"

INDIAN_UTM_ZONES = {
    42: "EPSG:32642",
    43: "EPSG:32643",
    44: "EPSG:32644",
    45: "EPSG:32645",
    46: "EPSG:32646",
    47: "EPSG:32647",
}

INDIA_BBOX = [68.1, 6.7, 97.4, 37.1]


def get_utm_zone_from_lon(lon: float) -> int:
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    return max(1, min(60, zone))


def get_utm_epsg_for_coordinates(lon: float, lat: float) -> str:
    zone = get_utm_zone_from_lon(lon)
    if lat >= 0:
        return f"EPSG:{32600 + zone}"
    return f"EPSG:{32700 + zone}"


def is_within_india_bbox(lon: float, lat: float) -> bool:
    return (
        INDIA_BBOX[0] <= lon <= INDIA_BBOX[2] and
        INDIA_BBOX[1] <= lat <= INDIA_BBOX[3]
    )


def lonlat_to_web_mercator(lon: float, lat: float) -> Tuple[float, float]:
    r_major = 6378137.0
    x = r_major * math.radians(lon)
    lat_clamped = max(min(lat, 89.5), -89.5)
    lat_rad = math.radians(lat_clamped)
    y = r_major * math.log(math.tan(math.pi / 4.0 + lat_rad / 2.0))
    return (x, y)


def web_mercator_to_lonlat(x: float, y: float) -> Tuple[float, float]:
    r_major = 6378137.0
    lon = math.degrees(x / r_major)
    lat = math.degrees(2.0 * math.atan(math.exp(y / r_major)) - math.pi / 2.0)
    return (lon, lat)


def approximate_utm_forward(lon: float, lat: float, zone: Optional[int] = None) -> Tuple[float, float]:
    if zone is None:
        zone = get_utm_zone_from_lon(lon)

    lon0 = (zone - 1) * 6.0 - 180.0 + 3.0
    lon0_rad = math.radians(lon0)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)
    k0 = 0.9996

    dlon = lon_rad - lon0_rad
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    tan_lat = math.tan(lat_rad)

    N = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    T = tan_lat * tan_lat
    C = e_prime2 * cos_lat * cos_lat
    A = cos_lat * dlon

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 * e2 * e2 / 256.0) * lat_rad
        - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 32.0 + 45.0 * e2 * e2 * e2 / 1024.0) * math.sin(2.0 * lat_rad)
        + (15.0 * e2 * e2 / 256.0 + 45.0 * e2 * e2 * e2 / 1024.0) * math.sin(4.0 * lat_rad)
        - (35.0 * e2 * e2 * e2 / 3072.0) * math.sin(6.0 * lat_rad)
    )

    x = k0 * N * (
        A + (1.0 - T + C) * (A ** 3) / 6.0 + (5.0 - 18.0 * T + T * T + 72.0 * C - 58.0 * e_prime2) * (A ** 5) / 120.0
    ) + 500000.0

    y = k0 * (
        M + N * tan_lat * (
            (A ** 2) / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C * C) * (A ** 4) / 24.0
            + (61.0 - 58.0 * T + T * T + 600.0 * C - 330.0 * e_prime2) * (A ** 6) / 720.0
        )
    )
    if lat < 0:
        y += 10000000.0

    return (x, y)


def transform_coordinates(coords: List[Tuple[float, float]], src_crs: str, dst_crs: str) -> List[Tuple[float, float]]:
    src = src_crs.upper()
    dst = dst_crs.upper()
    if src == dst:
        return list(coords)

    if src == "EPSG:4326" and dst == "EPSG:3857":
        return [lonlat_to_web_mercator(lon, lat) for lon, lat in coords]
    elif src == "EPSG:3857" and dst == "EPSG:4326":
        return [web_mercator_to_lonlat(x, y) for x, y in coords]
    elif src == "EPSG:4326" and dst.startswith("EPSG:326"):
        try:
            zone = int(dst.split(":")[1]) - 32600
        except ValueError:
            zone = None
        return [approximate_utm_forward(lon, lat, zone=zone) for lon, lat in coords]
    else:
        raise ValueError(f"Direct transformation between {src_crs} and {dst_crs} not supported.")

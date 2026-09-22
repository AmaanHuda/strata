"""
Image and raster tiling / chipping pipeline with coordinate window tracking.
SIH 2026 PS 26011 - ML Engine
"""
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np


@dataclass
class TileWindow:
    row_min: int
    row_max: int
    col_min: int
    col_max: int
    tile_index: int


def generate_tile_windows(
    height: int,
    width: int,
    tile_size: int = 512,
    overlap: int = 64
) -> List[TileWindow]:
    if tile_size <= overlap:
        raise ValueError("tile_size must be strictly greater than overlap.")

    stride = tile_size - overlap
    windows = []
    idx = 0

    r = 0
    while r < height:
        r_end = min(r + tile_size, height)
        r_start = max(0, r_end - tile_size)

        c = 0
        while c < width:
            c_end = min(c + tile_size, width)
            c_start = max(0, c_end - tile_size)

            windows.append(TileWindow(
                row_min=r_start,
                row_max=r_end,
                col_min=c_start,
                col_max=c_end,
                tile_index=idx
            ))
            idx += 1

            if c_end == width:
                break
            c += stride

        if r_end == height:
            break
        r += stride

    return windows


def extract_tiles(
    image: np.ndarray,
    tile_size: int = 512,
    overlap: int = 64
) -> Tuple[List[np.ndarray], List[TileWindow]]:
    h, w = image.shape[:2]
    windows = generate_tile_windows(h, w, tile_size=tile_size, overlap=overlap)
    tiles = []
    for win in windows:
        patch = image[win.row_min:win.row_max, win.col_min:win.col_max]
        tiles.append(patch)
    return tiles, windows

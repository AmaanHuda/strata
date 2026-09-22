"""
Baseline building footprint segmentation module.
SIH 2026 PS 26011 - ML Engine
"""
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from src.geospatial.operations import calculate_polygon_area
from src.preprocessing.vector_ops import simplify_polygon_rdp, remove_duplicate_consecutive_vertices


class BaselineFootprintSegmenter:
    """
    Morphological and intensity-thresholding footprint extractor baseline.
    Serves as the benchmark baseline before heavy deep-learning model integration.
    """
    def __init__(self, threshold: float = 0.5, min_area_sqm: float = 15.0):
        self.threshold = threshold
        self.min_area_sqm = min_area_sqm

    def predict_mask(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image.copy()

        # Normalize to 0-1
        g_min, g_max = np.min(gray), np.max(gray)
        if g_max - g_min > 1e-6:
            norm = (gray - g_min) / (g_max - g_min)
        else:
            norm = np.zeros_like(gray)

        # Baseline segmentation: high contrast roofs/structures
        mask = (norm > self.threshold).astype(np.uint8)
        return mask

    def extract_polygons_from_mask(
        self,
        mask: np.ndarray,
        geo_transform: Tuple[float, float, float, float, float, float] = (0, 1, 0, 0, 0, -1),
        tolerance: float = 1.0
    ) -> List[List[Tuple[float, float]]]:
        """
        Simple raster scanline border tracing to extract candidate polygons.
        geo_transform: (origin_x, pixel_width, 0, origin_y, 0, pixel_height)
        """
        h, w = mask.shape
        ox, pw, _, oy, _, ph = geo_transform

        # Simple connected component bounding box fallback for robust polygon generation
        polygons = []
        visited = np.zeros_like(mask, dtype=bool)

        for r in range(h):
            for c in range(w):
                if mask[r, c] == 1 and not visited[r, c]:
                    # Find extent of connected blob
                    r_min, r_max, c_min, c_max = r, r, c, c
                    stack = [(r, c)]
                    visited[r, c] = True
                    count = 0
                    while stack:
                        cr, cc = stack.pop()
                        count += 1
                        r_min = min(r_min, cr)
                        r_max = max(r_max, cr)
                        c_min = min(c_min, cc)
                        c_max = max(c_max, cc)
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = cr + dr, cc + dc
                            if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] == 1 and not visited[nr, nc]:
                                visited[nr, nc] = True
                                stack.append((nr, nc))

                    if count >= 4:
                        # Convert pixel bounding box to geographic/projected coordinates
                        x1 = ox + c_min * pw
                        y1 = oy + r_min * ph
                        x2 = ox + (c_max + 1) * pw
                        y2 = oy + (r_max + 1) * ph

                        poly = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
                        simplified = simplify_polygon_rdp(poly, tolerance=tolerance)
                        polygons.append(simplified)

        return polygons

# SIH 2026 PS 26011 — 3D-Mapping ML Engine Service
# Runs src/server.py (FastAPI) on port 8001.
# Heavyweight ML deps (torch, rasterio, geopandas) require a full Python image.
# GDAL, PDAL, Open3D require environment-specific installation — see pyproject.toml note.

FROM python:3.11-slim

WORKDIR /ml-engine

# System-level dependencies for rasterio, geopandas, shapely, opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    libproj-dev \
    proj-bin \
    libgdal-dev \
    gdal-bin \
    gcc \
    g++ \
    libgl1 \
    && rm -rf /var/lib/lists/*

# Copy only dependency definition first (layer caching)
COPY pyproject.toml .

# Install Python dependencies listed in pyproject.toml
# Using pip without Poetry to keep the container image simple.
# Pin versions matching pyproject.toml constraints.
RUN pip install --no-cache-dir \
    "numpy>=1.24,<2.0" \
    "pandas>=2.0,<3.0" \
    "geopandas>=0.14,<1.0" \
    "shapely>=2.0,<3.0" \
    "rasterio>=1.3,<2.0" \
    "opencv-python-headless>=4.8,<5.0" \
    "scikit-learn>=1.3,<2.0" \
    "trimesh>=4.0,<5.0" \
    "jsonschema>=4.0,<5.0" \
    "fastapi>=0.100,<1.0" \
    "uvicorn[standard]>=0.23,<1.0" \
    "pydantic>=2.0,<3.0"

# NOTE: torch is intentionally excluded — adds ~2GB and current pipeline uses
# heuristic/geometric algorithms (no trained model weights loaded).
# Re-add torch if/when trained model inference is activated:
#   RUN pip install --no-cache-dir "torch>=2.0,<3.0" --index-url https://download.pytorch.org/whl/cpu

# Copy application source
COPY src/ ./src/
COPY schemas/ ./schemas/
COPY datasets/ ./datasets/
COPY models/ ./models/
COPY configs/ ./configs/

EXPOSE 8001

# Run the FastAPI server
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8001"]

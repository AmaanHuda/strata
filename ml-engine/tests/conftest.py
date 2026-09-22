"""
pytest conftest - SIH 2026 PS 26011 ML Engine
Shared fixtures and configuration.
"""
import sys
import pathlib
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture
def project_root() -> pathlib.Path:
    return PROJECT_ROOT

@pytest.fixture
def schemas_dir(project_root) -> pathlib.Path:
    return project_root / "schemas"

@pytest.fixture
def fixtures_dir(project_root) -> pathlib.Path:
    return project_root / "tests" / "fixtures"

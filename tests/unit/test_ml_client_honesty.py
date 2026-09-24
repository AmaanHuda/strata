"""Regression guard: the ML client must never fabricate predictions.

Context
-------
app/integrations/ml_engine/client.py previously caught *any* exception from the
ML Engine HTTP call and returned invented values - for example an assumed 9.0 m
building height for an assumed 3-storey building, with an invented 0.75
confidence and an invented +/-0.5 m uncertainty. Callers (MLAdapter) then
persisted those values as though the ML Engine had measured the building.

The client now raises MLEngineNotAvailableError instead. These tests fail if the
silent fallback is ever reintroduced.
"""
import pytest

from app.core.config import settings
from app.core.errors import MLEngineNotAvailableError
from app.integrations.ml_engine.client import ml_client
from app.integrations.ml_engine.contracts import (
    FloorCountRequest,
    HeightEstimationRequest,
    VerticalUnitGenRequest,
)

# A port with nothing listening: this is the real "ML Engine is down" scenario.
UNREACHABLE_URL = "http://127.0.0.1:9"


@pytest.fixture
def engine_enabled_but_unreachable(monkeypatch):
    """ML Engine is switched ON (so the enabled check passes) but unreachable."""
    monkeypatch.setattr(settings, "ML_ENGINE_ENABLED", True)
    monkeypatch.setattr(ml_client, "enabled", True)
    monkeypatch.setattr(ml_client, "base_url", UNREACHABLE_URL)
    monkeypatch.setattr(ml_client, "timeout", 1.0)
    yield


async def test_height_estimation_raises_instead_of_returning_assumed_height(
    engine_enabled_but_unreachable,
):
    """No assumed 9.0 m height, no invented 0.75 confidence."""
    with pytest.raises(MLEngineNotAvailableError):
        await ml_client.estimate_height(
            HeightEstimationRequest(
                parcel_id="P-1",
                building_id="B-1",
                lat=18.9750,
                lon=72.8250,
            )
        )


async def test_floor_detection_raises_instead_of_returning_assumed_floors(
    engine_enabled_but_unreachable,
):
    """No invented confidence of 0.80 with method 'height_division'."""
    with pytest.raises(MLEngineNotAvailableError):
        await ml_client.estimate_floors(
            FloorCountRequest(building_id="B-1", height_m=18.5)
        )


async def test_vertical_units_raise_instead_of_local_generation(
    engine_enabled_but_unreachable,
):
    """No locally generated unit boundaries returned as ML Engine output."""
    with pytest.raises(MLEngineNotAvailableError):
        await ml_client.generate_vertical_units(
            VerticalUnitGenRequest(floor_number=0, floor_area_sqm=120.0)
        )


async def test_disabled_engine_raises_rather_than_fabricating(monkeypatch):
    """The repo default (ML_ENGINE_ENABLED=False) must produce errors, not data."""
    monkeypatch.setattr(settings, "ML_ENGINE_ENABLED", False)
    monkeypatch.setattr(ml_client, "enabled", False)

    with pytest.raises(MLEngineNotAvailableError):
        await ml_client.estimate_floors(
            FloorCountRequest(building_id="B-1", height_m=9.0)
        )

"""Integration tests: auth register/login flow."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "SIH 2026" in data["project"]

"""Tests for the FastAPI HTTP endpoints."""

import pytest
import httpx
from httpx import ASGITransport

from main import app


@pytest.fixture
def async_client():
    """Create an httpx async client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, async_client) -> None:
        async with async_client as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRouteEndpoint:
    @pytest.mark.asyncio
    async def test_route_returns_zone_list(self, async_client) -> None:
        async with async_client as client:
            response = await client.get("/route")
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        assert isinstance(data["zones"], list)
        assert len(data["zones"]) == 5


class TestIngestEndpoint:
    @pytest.mark.asyncio
    async def test_valid_ingest_accepted(self, async_client) -> None:
        payload = {
            "location_zone": "Silk Board Junction",
            "text": "Flooding reported near the flyover",
        }
        async with async_client as client:
            response = await client.post("/ingest", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_missing_field_returns_422(self, async_client) -> None:
        payload = {"location_zone": "Silk Board Junction"}  # missing 'text'
        async with async_client as client:
            response = await client.post("/ingest", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_body_returns_422(self, async_client) -> None:
        async with async_client as client:
            response = await client.post("/ingest", json={})
        assert response.status_code == 422

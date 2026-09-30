"""
E2E Tests for Health Endpoint
Verifies /health is accessible without authentication.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health -> 200 with service statuses."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert "services" in data
    assert isinstance(data["services"], dict)

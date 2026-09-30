"""
E2E Tests for Health Check Endpoint
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.main import app


@pytest.mark.asyncio
async def test_health_check_returns_200():
    """Test that /health endpoint returns 200 OK."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check_returns_correct_format():
    """Test that /health endpoint returns correct JSON format."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert "status" in data
    assert "services" in data
    assert isinstance(data["services"], dict)


@pytest.mark.asyncio
async def test_health_check_status_is_string():
    """Test that status field is a string."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert isinstance(data["status"], str)
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.asyncio
async def test_health_check_services_is_dict():
    """Test that services field is a dictionary."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert isinstance(data["services"], dict)


@pytest.mark.asyncio
async def test_root_endpoint_returns_200():
    """Test that root endpoint returns 200 OK."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_root_endpoint_returns_message():
    """Test that root endpoint returns message."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    data = response.json()

    assert "message" in data
    assert isinstance(data["message"], str)

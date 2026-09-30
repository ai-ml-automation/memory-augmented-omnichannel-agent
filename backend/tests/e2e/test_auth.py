"""
E2E Tests for Authentication Flow
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_201(client: AsyncClient):
    """Test that /auth/register returns 201 Created."""
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_register_returns_user_data(client: AsyncClient):
    """Test that /auth/register returns user data."""
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234568",
            "password": "testpassword123",
        },
    )

    data = response.json()

    assert "id" in data
    assert "phone_hash" in data
    assert "created_at" in data
    assert "is_active" in data
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient):
    """Test that /auth/login returns access token."""
    # First register
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234569",
            "password": "testpassword123",
        },
    )

    # Then login
    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234569",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_sets_cookie(client: AsyncClient):
    """Test that /auth/login sets httpOnly cookie."""
    # First register
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234570",
            "password": "testpassword123",
        },
    )

    # Then login
    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234570",
            "password": "testpassword123",
        },
    )

    # Check cookie is set
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_me_requires_authentication(client: AsyncClient):
    """Test that /auth/me requires authentication."""
    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_with_valid_token(client: AsyncClient):
    """Test that /auth/me returns user with valid token."""
    # Register and login
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234571",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234571",
            "password": "testpassword123",
        },
    )

    # Get user with cookie
    response = await client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "phone_hash" in data


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient):
    """Test that /auth/logout clears cookie."""
    # Register and login first so middleware accepts the request
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234572",
            "password": "testpassword123",
        },
    )
    await client.post(
        "/auth/login",
        json={
            "phone": "+79991234572",
            "password": "testpassword123",
        },
    )

    response = await client.post("/auth/logout")

    assert response.status_code == 200
    # Cookie should be cleared
    assert response.cookies.get("access_token") is None or \
           response.cookies.get("access_token") == ""


@pytest.mark.asyncio
async def test_consents_status_requires_auth(client: AsyncClient):
    """Test that /consents/status requires authentication."""
    response = await client.get("/consents/status")

    assert response.status_code == 401

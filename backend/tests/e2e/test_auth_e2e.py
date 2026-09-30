"""
E2E Tests for Authentication Flow
Tests registration, login, token validation, and logout.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """POST /auth/register with valid data → 201 + response has id, phone_hash."""
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "phone_hash" in data
    assert "created_at" in data
    assert "is_active" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_user_duplicate(client: AsyncClient):
    """Register same phone twice → 400 error."""
    payload = {
        "phone": "+79991234567",
        "password": "TestPassword123!",
    }
    response1 = await client.post("/auth/register", json=payload)
    assert response1.status_code == 201

    response2 = await client.post("/auth/register", json=payload)
    assert response2.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Register then login → 200 + access_token cookie is set."""
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Register, then login with wrong password → 401."""
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "WrongPassword999!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """Register, login, GET /auth/me with cookie → 200 + user data."""
    register_response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert register_response.status_code == 201
    registered_user = register_response.json()

    login_response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200
    # Cookie is automatically stored by httpx AsyncClient

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    data = me_response.json()
    assert data["id"] == registered_user["id"]
    assert "phone_hash" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """GET /auth/me without cookie → 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Register, login, POST /auth/logout, then GET /auth/me → 401."""
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    # Verify auth works before logout
    me_before = await client.get("/auth/me")
    assert me_before.status_code == 200

    # Logout
    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200
    data = logout_response.json()
    assert "message" in data

    # Verify auth no longer works
    me_after = await client.get("/auth/me")
    assert me_after.status_code == 401

"""
E2E Tests for Consent Endpoints
Tests consent grant, status, and revocation (GDPR RTBF).
All endpoints require authentication via JWT cookie.
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str) -> None:
    """Helper: register user and login to set the JWT cookie."""
    await client.post(
        "/auth/register",
        json={
            "phone": phone,
            "password": "ConsentTest123!",
        },
    )
    await client.post(
        "/auth/login",
        json={"phone": phone, "password": "ConsentTest123!"},
    )


@pytest.mark.asyncio
async def test_consent_grant(client: AsyncClient):
    """POST /consents/grant -> 201 with created consent record."""
    await _register_and_login(client, "+79991000001")

    resp = await client.post(
        "/consents/grant",
        json={
            "scope": "messaging",
            "channel": "telegram",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_active_consent"] is True


@pytest.mark.asyncio
async def test_consent_status(client: AsyncClient):
    """GET /consents/status -> 200 with consent status."""
    await _register_and_login(client, "+79991000002")

    resp = await client.get("/consents/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_active_consent" in data


@pytest.mark.asyncio
async def test_consent_revoke(client: AsyncClient):
    """POST /consents/revoke -> 200 with revoked consent."""
    await _register_and_login(client, "+79991000003")

    # Grant first, then revoke
    await client.post(
        "/consents/grant",
        json={"scope": "messaging", "channel": "max"},
    )

    resp = await client.post("/consents/revoke")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_active_consent"] is False

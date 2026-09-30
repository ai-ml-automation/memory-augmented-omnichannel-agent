"""
E2E Tests for Chat Endpoints
Tests chat send, chat health, and response evaluation.
Mock settings.ENABLE_LLM to control LLM behavior.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_send_message(client: AsyncClient):
    """POST /chat/users/{id}/message -> 200 with response."""
    # Register and login to get auth cookie
    register_resp = await client.post(
        "/auth/register",
        json={"phone": "+79999000001", "password": "TestPassword123!"},
    )
    user_id = register_resp.json()["id"]
    await client.post(
        "/auth/login",
        json={"phone": "+79999000001", "password": "TestPassword123!"},
    )

    # Grant consent (required for chat per 152-FZ)
    await client.post("/consents/grant", json={"scope": "messaging", "channel": "telegram"})

    resp = await client.post(
        f"/chat/users/{user_id}/message",
        json={"message": "Hello there", "channel_type": "telegram"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "evaluation" in data
    assert "facts_stored" in data


@pytest.mark.asyncio
async def test_chat_health(client: AsyncClient):
    """GET /chat/health -> 200 with provider info (LLM disabled by default)."""
    # Register and login to get auth cookie
    await client.post(
        "/auth/register",
        json={"phone": "+79999000002", "password": "TestPassword123!"},
    )
    await client.post(
        "/auth/login",
        json={"phone": "+79999000002", "password": "TestPassword123!"},
    )

    resp = await client.get("/chat/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "enabled" in data
    assert "initialized" in data


@pytest.mark.asyncio
async def test_chat_evaluate(client: AsyncClient):
    """POST /chat/evaluate -> 200 with evaluation score."""
    # Register and login to get auth cookie
    await client.post(
        "/auth/register",
        json={"phone": "+79999000003", "password": "TestPassword123!"},
    )
    await client.post(
        "/auth/login",
        json={"phone": "+79999000003", "password": "TestPassword123!"},
    )

    resp = await client.post(
        "/chat/evaluate",
        params={
            "response": "This is a test response",
            "context": "User asked a question",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert isinstance(data["score"], (int, float))

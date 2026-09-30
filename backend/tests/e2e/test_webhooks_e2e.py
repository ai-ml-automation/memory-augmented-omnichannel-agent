"""
V.2: E2E Webhook Tests
Tests for Telegram, VK, and MAX webhook secret verification.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

_TG = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "placeholder-tg")
_VK = os.environ.get("VK_CALLBACK_SECRET", "placeholder-vk")


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Mock Celery task dispatch so webhook tests don't need Redis broker."""
    with patch("backend.src.api.webhooks.process_message") as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


class TestTelegramWebhook:

    @pytest.mark.asyncio
    async def test_valid_secret_returns_ok(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = _TG
            m.VK_GROUP_ID = "123"
            response = await client.post(
                "/webhook/telegram",
                json={"message": {"text": "Hello", "from": {"id": 123}}},
                headers={"X-Telegram-Bot-Api-Secret-Token": _TG},
            )
            assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_invalid_secret_returns_403(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = _TG
            response = await client.post(
                "/webhook/telegram",
                json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-value"},
            )
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_header_returns_403(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = _TG
            response = await client.post("/webhook/telegram", json={})
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = ""
            response = await client.post(
                "/webhook/telegram",
                json={"message": {"text": "Hi", "from": {"id": 999}}},
            )
            assert response.status_code != 403


class TestVKWebhook:

    @pytest.mark.asyncio
    async def test_valid_secret_returns_ok(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_CALLBACK_SECRET = _VK
            m.VK_GROUP_ID = "123"
            response = await client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": _VK, "object": {"message": {"text": "Hi"}}},
            )
            assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_invalid_secret_returns_403(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_CALLBACK_SECRET = _VK
            response = await client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "wrong-value"},
            )
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_confirmation_bypasses_secret(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_GROUP_ID = "789"
            response = await client.post("/webhook/vk", json={"type": "confirmation"})
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self, client: AsyncClient):
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_CALLBACK_SECRET = ""
            m.VK_GROUP_ID = "123"
            response = await client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "anything", "object": {"message": {"text": "Hi"}}},
            )
            assert response.status_code != 403


class TestMAXWebhook:

    @pytest.mark.asyncio
    async def test_max_no_secret_check(self, client: AsyncClient):
        response = await client.post(
            "/webhook/max",
            json={"message": {"text": "Hello", "sender": {"id": 456}}},
        )
        assert response.status_code != 403
"""
Tests for Webhook Security (Phase B.2.1, B.2.2)

B.2.1: Telegram X-Telegram-Bot-Api-Secret-Token verification
B.2.2: VK Callback API secret parameter verification
"""

import hmac
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.src.api.webhooks import (
    _verify_telegram_secret,
    _verify_vk_secret,
    router,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with webhook router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


# ------------------------------------------------------------------
# B.2.1: Telegram webhook secret verification
# ------------------------------------------------------------------


class TestTelegramSecretVerification:
    """Tests for Telegram webhook secret token verification."""

    def test_valid_secret_accepted(self, client):
        """Request with correct secret token should be accepted (200 or 400 for bad data)."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.TELEGRAM_WEBHOOK_SECRET = "my-secure-token"
            mock_settings.TELEGRAM_BOT_TOKEN = "test-token"

            # Even with invalid data, we should get 400 (not 403)
            response = client.post(
                "/webhook/telegram",
                json={},
                headers={"x-telegram-bot-api-secret-token": "my-secure-token"},
            )
            assert response.status_code != 403

    def test_invalid_secret_rejected(self, client):
        """Request with wrong secret token should return 403."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.TELEGRAM_WEBHOOK_SECRET = "my-secure-token"

            response = client.post(
                "/webhook/telegram",
                json={},
                headers={"x-telegram-bot-api-secret-token": "wrong-token"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Forbidden"

    def test_missing_secret_rejected(self, client):
        """Request without secret token header should return 403 when configured."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.TELEGRAM_WEBHOOK_SECRET = "my-secure-token"

            response = client.post(
                "/webhook/telegram",
                json={},
                # No header
            )
            assert response.status_code == 403

    def test_empty_secret_config_skips_verification(self, client):
        """When TELEGRAM_WEBHOOK_SECRET is empty, verification is skipped (dev mode)."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.TELEGRAM_WEBHOOK_SECRET = ""
            mock_settings.TELEGRAM_BOT_TOKEN = "test-token"

            # No header but secret not configured -> 400 (bad data), not 403
            response = client.post(
                "/webhook/telegram",
                json={},
            )
            assert response.status_code == 400

    def test_secret_comparison_is_timing_safe(self):
        """Verify hmac.compare_digest is used (constant-time comparison)."""
        # This is a code review test - verify the function uses compare_digest
        import inspect
        source = inspect.getsource(_verify_telegram_secret)
        assert "compare_digest" in source


# ------------------------------------------------------------------
# B.2.2: VK callback secret verification
# ------------------------------------------------------------------


class TestVKSsecretVerification:
    """Tests for VK Callback API secret parameter verification."""

    def test_valid_vk_secret_accepted(self, client):
        """Request with correct VK secret should be accepted."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"
            mock_settings.VK_GROUP_ID = "12345"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "vk-secret-123"},
            )
            assert response.status_code != 403

    def test_invalid_vk_secret_rejected(self, client):
        """Request with wrong VK secret should return 403."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "wrong-secret"},
            )
            assert response.status_code == 403

    def test_missing_vk_secret_rejected(self, client):
        """Request without VK secret should return 403 when configured."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new"},
            )
            assert response.status_code == 403

    def test_confirmation_without_secret_check(self, client):
        """VK confirmation request should work even without secret (initial setup)."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"
            mock_settings.VK_GROUP_ID = "12345"

            response = client.post(
                "/webhook/vk",
                json={"type": "confirmation"},
            )
            # Confirmation should return group ID, not check secret
            assert response.status_code == 200
            assert response.json() == {"response": "12345"}

    def test_empty_vk_secret_config_skips_verification(self, client):
        """When VK_CALLBACK_SECRET is empty, verification is skipped."""
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = ""
            mock_settings.VK_GROUP_ID = "12345"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new"},
            )
            # No secret check, should get 400 (bad data) not 403
            assert response.status_code == 400

    def test_vk_secret_comparison_is_timing_safe(self):
        """Verify hmac.compare_digest is used for VK secret."""
        import inspect
        source = inspect.getsource(_verify_vk_secret)
        assert "compare_digest" in source

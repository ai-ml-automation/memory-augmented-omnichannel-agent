"""
Юнит-тесты безопасности вебхуков Telegram (B.2.1) и VK (B.2.2).

Проверяют проверку секретов: валидный секрет принимается, неверный и
отсутствующий дают 403, пустая конфигурация отключает проверку (dev-режим),
confirmation VK работает без проверки секрета, а сравнение секретов идёт
через hmac.compare_digest (constant-time, защита от timing-атак).
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
    """Создаёт тестовое FastAPI-приложение с роутером вебхуков.

    Ловит баги настройки роутера: отсутствие include_router сразу валит все
    HTTP-тесты (404 вместо проверки секрета).
    """
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Создаёт тестовый клиент поверх приложения.

    Изолирует HTTP-слой: без реального сервера тесты детерминированы.
    """
    return TestClient(app)


# ------------------------------------------------------------------
# B.2.1: Telegram webhook secret verification
# ------------------------------------------------------------------


class TestTelegramSecretVerification:
    """
    Проверка X-Telegram-Bot-Api-Secret-Token на /webhook/telegram.

    Ловит баги: пропуск проверки секрета, неверный статус при отклонении
    (403 вместо 400), отключение проверки при пустом секрете и использование
    обычного == вместо constant-time сравнения (timing-атака).
    """

    def test_valid_secret_accepted(self, client):
        """
        Валидный секрет-токен не даёт 403 (проходит проверку).
        Ловит ложное отклонение легитимного запроса вебхука Telegram.
        """
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
        """
        Неверный секрет-токен отклоняется с 403 Forbidden.
        Ловит баг отсутствия проверки: чужой секрет не должен проходить.
        """
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
        """
        Запрос без заголовка секрета отклоняется 403, если секрет задан.
        Ловит баг принятия запросов без токена (открытый вебхук).
        """
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.TELEGRAM_WEBHOOK_SECRET = "my-secure-token"

            response = client.post(
                "/webhook/telegram",
                json={},
                # No header
            )
            assert response.status_code == 403

    def test_empty_secret_config_skips_verification(self, client):
        """
        Пустой секрет в конфиге отключает проверку (dev-режим): 400, не 403.
        Ловит баг жёсткой проверки при незаполненной конфигурации — вебхук
        Telegram требует секрет всегда, в dev без него должен быть 400.
        """
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
        """
        Функция проверки секрета использует hmac.compare_digest.
        Код-ревью тест: обычное == уязвимо к timing-атаке по секрету.
        """
        # This is a code review test - verify the function uses compare_digest
        import inspect
        source = inspect.getsource(_verify_telegram_secret)
        assert "compare_digest" in source


# ------------------------------------------------------------------
# B.2.2: VK callback secret verification
# ------------------------------------------------------------------


class TestVKSsecretVerification:
    """
    Проверка секрета VK Callback API на /webhook/vk.

    Ловит баги: пропуск проверки секрета, неверный статус отклонения,
    блокировку confirmation без секрета (ломает первичную настройку VK)
    и пустую конфигурацию, дающую 403 вместо 400.
    """

    def test_valid_vk_secret_accepted(self, client):
        """
        Валидный VK-секрет в теле запроса проходит проверку (не 403).
        Ловит ложное отклонение легитимного callback-запроса VK.
        """
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"
            mock_settings.VK_GROUP_ID = "12345"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "vk-secret-123"},
            )
            assert response.status_code != 403

    def test_invalid_vk_secret_rejected(self, client):
        """
        Неверный VK-секрет отклоняется с 403.
        Ловит баг отсутствия проверки: чужой секрет не должен проходить.
        """
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "wrong-secret"},
            )
            assert response.status_code == 403

    def test_missing_vk_secret_rejected(self, client):
        """
        Callback без VK-секрета отклоняется 403, если секрет настроен.
        Ловит баг приёма callback-запросов без секрета (подделка событий).
        """
        with patch("backend.src.api.webhooks.settings") as mock_settings:
            mock_settings.VK_CALLBACK_SECRET = "vk-secret-123"

            response = client.post(
                "/webhook/vk",
                json={"type": "message_new"},
            )
            assert response.status_code == 403

    def test_confirmation_without_secret_check(self, client):
        """
        Confirmation VK обрабатывается без проверки секрета (первичная настройка).
        Ловит баг блокировки confirmation — VK требует его при подключении,
        секрет ещё не прислан, без этого теста вебхук нельзя настроить.
        """
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
        """
        Пустой VK_CALLBACK_SECRET отключает проверку: 400 (bad data), не 403.
        Ловит баг вечного 403 при незаполненной конфигурации секрета.
        """
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
        """
        Функция проверки VK-секрета использует hmac.compare_digest.
        Код-ревью тест: сравнение через == даёт утечку по таймингу.
        """
        import inspect
        source = inspect.getsource(_verify_vk_secret)
        assert "compare_digest" in source

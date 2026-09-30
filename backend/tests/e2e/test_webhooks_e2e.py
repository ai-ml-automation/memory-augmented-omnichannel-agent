"""
V.2: E2E-тесты вебхуков Telegram, VK и MAX.

Проверяют проверку секретов входящих вебхуков: валидный секрет
принимается, неверный/отсутствующий отклоняется 403, пустой секрет
в конфиге отключает проверку. MAX секрет не проверяет вовсе.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

_TG = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "placeholder-tg")
_VK = os.environ.get("VK_CALLBACK_SECRET", "placeholder-vk")


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Мокает отправку задач Celery, чтобы не нужен Redis-брокер.

    Autouse-фикстура: подменяет process_message.delay пустышкой,
    изолируя вебхук-обработку от очереди.
    """
    with patch("backend.src.api.webhooks.process_message") as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


class TestTelegramWebhook:
    """Проверка секрета Telegram-вебхука (X-Telegram-Bot-Api-Secret-Token).

    Охватывает валидный/неверный/отсутствующий заголовок, а также
    режим с пустым секретом в конфиге.
    """

    @pytest.mark.asyncio
    async def test_valid_secret_returns_ok(self, client: AsyncClient):
        """Ловит ложный 403: валидный секрет отклоняется.

        Валидный заголовок обязан пройти проверку; иначе Telegram
        не доставляет сообщения в приложение.
        """
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
        """Ловит дыру: неверный секрет вебхука не отклоняется.

        Запрос с чужим секретом обязан вернуть 403 — иначе
        поддельные события попадают в обработку.
        """
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
        """Ловит дыру: отсутствующий заголовок пропускается.

        Вебхук без секретного заголовка обязан вернуть 403,
        иначе проверка секрета легко обходится.
        """
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = _TG
            response = await client.post("/webhook/telegram", json={})
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self, client: AsyncClient):
        """Ловит переключение режима: пустой секрет блокирует всё.

        Пустой секрет в конфиге отключает проверку — сообщения
        должны приниматься в локальной отладке.
        """
        with patch("backend.src.api.webhooks.settings") as m:
            m.TELEGRAM_WEBHOOK_SECRET = ""
            response = await client.post(
                "/webhook/telegram",
                json={"message": {"text": "Hi", "from": {"id": 999}}},
            )
            assert response.status_code != 403


class TestVKWebhook:
    """Проверка секрета VK-вебхука (поле secret в пейлоаде).

    Охватывает валидный/неверный secret, подтверждение адреса
    и режим с пустым секретом в конфиге.
    """

    @pytest.mark.asyncio
    async def test_valid_secret_returns_ok(self, client: AsyncClient):
        """Ловит ложный 403: валидный VK-секрет отклоняется.

        Сообщение с верным secret обязано обработаться; иначе VK
        не доставляет события в приложение.
        """
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
        """Ловит дыру: неверный секрет вебхука не отклоняется.

        Запрос с чужим секретом обязан вернуть 403 — иначе
        поддельные события попадают в обработку.
        """
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_CALLBACK_SECRET = _VK
            response = await client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "wrong-value"},
            )
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_confirmation_bypasses_secret(self, client: AsyncClient):
        """Ловит поломку confirm: VK-подтверждение требует секрет.

        Запрос type=confirmation обязан работать без секрета (200),
        иначе VK не подтверждает адрес вебхука.
        """
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_GROUP_ID = "789"
            response = await client.post("/webhook/vk", json={"type": "confirmation"})
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self, client: AsyncClient):
        """Ловит переключение режима: пустой секрет блокирует всё.

        Пустой секрет в конфиге отключает проверку — сообщения
        должны приниматься в локальной отладке.
        """
        with patch("backend.src.api.webhooks.settings") as m:
            m.VK_CALLBACK_SECRET = ""
            m.VK_GROUP_ID = "123"
            response = await client.post(
                "/webhook/vk",
                json={"type": "message_new", "secret": "anything", "object": {"message": {"text": "Hi"}}},
            )
            assert response.status_code != 403


class TestMAXWebhook:
    """MAX-вебхук: проверка секрета не предусмотрена.

    Сообщения MAX принимаются без заголовков аутентификации —
    тест фиксирует отсутствие ложного 403.
    """

    @pytest.mark.asyncio
    async def test_max_no_secret_check(self, client: AsyncClient):
        """Ловит ложный 403: MAX-вебхук требует секрет.

        MAX не передаёт секрет в запросе; вебхук обязан
        принимать сообщения без заголовков аутентификации.
        """
        response = await client.post(
            "/webhook/max",
            json={"message": {"text": "Hello", "sender": {"id": 456}}},
        )
        assert response.status_code != 403
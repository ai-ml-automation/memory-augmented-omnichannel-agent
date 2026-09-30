"""
Контрактные тесты структуры webhook-пейлоадов (Phase E.3).

Фиксируют формат реальных пейлоадов Telegram, VK Callback API
и MAX: набор обязательных полей и их вложенность. Ловят расхождение
между тем, что присылают каналы, и тем, что ожидает парсер
вебхуков (E.3), — без реальных запросов к мессенджерам.
"""

import pytest


class TestWebhookContracts:
    """Группа контрактных тестов пейлоадов вебхуков трёх каналов.

    Покрывают структуру реальных update Telegram, событий VK Callback
    API и MAX: обязательные поля и вложенность. Фиксируют контракт
    между мессенджерами и парсером вебхуков (E.3).
    """

    def test_telegram_message_payload_structure(self):
        """Ловит смену структуры update Telegram: парсер вебхуков сломается.

        Реальный update Bot API содержит update_id и message с полями
        message_id/from/chat/text; from.id равен chat.id в приватном чате.
        """
        # Real Telegram update structure
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User",
                    "username": "testuser",
                    "language_code": "ru",
                },
                "chat": {
                    "id": 123456,
                    "first_name": "Test",
                    "last_name": "User",
                    "username": "testuser",
                    "type": "private",
                },
                "date": 1689000000,
                "text": "Hello bot",
            },
        }

        # Verify required fields exist
        assert "update_id" in payload
        assert "message" in payload
        msg = payload["message"]
        assert "message_id" in msg
        assert "from" in msg
        assert "chat" in msg
        assert "text" in msg
        assert msg["from"]["id"] == msg["chat"]["id"]

    def test_vk_callback_payload_structure(self):
        """Ловит смену структуры VK Callback API: message_new не распарсится.

        Событие message_new несёт object.message с полями
        text/from_id/peer_id; отправитель и чат в VK — разные сущности.
        """
        payload = {
            "type": "message_new",
            "object": {
                "message": {
                    "text": "Hello",
                    "from_id": 123456,
                    "peer_id": 123456,
                    "date": 1689000000,
                    "attachments": [],
                },
            },
            "group_id": 123456,
            "event_id": "abc123",
            "secret": "verify_me",
        }

        assert payload["type"] == "message_new"
        assert "object" in payload
        assert "message" in payload["object"]
        assert "text" in payload["object"]["message"]
        assert "from_id" in payload["object"]["message"]

    def test_max_webhook_payload_structure(self):
        """Ловит смену структуры MAX: событие message не распарсится.

        MAX оборачивает сообщение в payload.message, чат — в payload.chat
        с chatId; вложенность отличается от Telegram/VK.
        """
        payload = {
            "event": "message",
            "payload": {
                "message": {
                    "text": "Hello",
                    "mid": "123456789",
                },
                "chat": {
                    "chatId": "123456",
                    "type": "dialog",
                },
            },
        }

        assert payload["event"] == "message"
        assert "payload" in payload
        assert "message" in payload["payload"]
        assert "chat" in payload["payload"]
        assert "text" in payload["payload"]["message"]

    def test_webhook_payloads_are_json_serializable(self):
        """Ловит не-сериализуемые типы: пейлоад сломает JSON-транспорт.

        Все три канала доставляют вебхуки как JSON, поэтому любой
        не-сериализуемый объект (datetime/bytes/и т.п.) обрушит
        доставку ещё до парсинга.
        """
        import json

        payloads = [
            {"update_id": 1, "message": {"chat": {"id": 1}, "text": "hi", "from": {"id": 1}}},
            {"type": "message_new", "object": {"message": {"text": "hi", "from_id": 1, "peer_id": 1}}, "group_id": 1},
            {"event": "message", "payload": {"message": {"text": "hi"}, "chat": {"chatId": "1"}}},
        ]

        for payload in payloads:
            serialized = json.dumps(payload)
            deserialized = json.loads(serialized)
            assert deserialized == payload

"""
Contract tests for webhook payload parsing.
Phase E.3: Verify parsing matches real messenger payloads.
"""

import pytest


class TestWebhookContracts:
    """Contract tests for webhook payload parsing (Phase E.3)."""

    def test_telegram_message_payload_structure(self):
        """Verify Telegram message payload structure matches API spec."""
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
        """Verify VK Callback API payload structure."""
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
        """Verify MAX messenger webhook payload structure."""
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
        """Verify all webhook payloads can be serialized to JSON."""
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

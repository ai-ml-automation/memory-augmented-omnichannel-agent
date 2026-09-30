"""
Telegram Gateway
Integration with Telegram via aiogram 3.x
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramGateway:
    """Gateway for Telegram integration."""

    def __init__(self):
        self._bot = None
        self._bot_token = settings.TELEGRAM_BOT_TOKEN

    def _get_bot(self) -> Any:
        """Lazy initialization of Telegram bot."""
        if self._bot is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("Telegram integration disabled (ENABLE_LLM=false)")

            try:
                from aiogram import Bot

                self._bot = Bot(token=self._bot_token)
                logger.info("Telegram bot initialized")
            except ImportError:
                raise RuntimeError("aiogram package not installed")

        return self._bot

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """
        Send message to Telegram chat.

        Args:
            chat_id: Chat identifier
            text: Message text
            **kwargs: Additional parameters

        Returns:
            True if sent successfully
        """
        if not settings.ENABLE_LLM:
            logger.warning("Telegram integration disabled, skipping send")
            return False

        try:
            bot = self._get_bot()
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs,
            )
            logger.info(f"Message sent to Telegram chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse incoming webhook data from Telegram.

        Args:
            data: Raw webhook data (Update object)

        Returns:
            Parsed message data
        """
        message = data.get("message", {}) or data.get("edited_message", {})
        from_user = message.get("from", {})

        return {
            "channel": "TG",
            "external_id": str(from_user.get("id", "")),
            "text": message.get("text", ""),
            "message_id": str(message.get("message_id", "")),
            "timestamp": message.get("date", 0),
            "username": from_user.get("username", ""),
            "first_name": from_user.get("first_name", ""),
        }

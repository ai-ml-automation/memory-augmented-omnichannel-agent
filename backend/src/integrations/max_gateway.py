"""
MAX Gateway
Integration with MAX messenger via aiomax SDK
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MAXGateway:
    """Gateway for MAX messenger integration."""

    def __init__(self):
        self._client = None
        self._bot_token = settings.MAX_BOT_TOKEN

    def _get_client(self) -> Any:
        """Lazy initialization of MAX client."""
        if self._client is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("MAX integration disabled (ENABLE_LLM=false)")

            try:
                import aiomax

                self._client = aiomax.Bot(token=self._bot_token)
                logger.info("MAX client initialized")
            except ImportError:
                raise RuntimeError("aiomax package not installed")

        return self._client

    async def send_message(
        self,
        user_external_id: str,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """
        Send message to MAX user.

        Args:
            user_external_id: User's external ID in MAX
            text: Message text
            **kwargs: Additional parameters

        Returns:
            True if sent successfully
        """
        if not settings.ENABLE_LLM:
            logger.warning("MAX integration disabled, skipping send")
            return False

        try:
            client = self._get_client()
            await client.send_message(
                chat_id=user_external_id,
                text=text,
                **kwargs,
            )
            logger.info(f"Message sent to MAX user {user_external_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send MAX message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse incoming webhook data from MAX.

        Args:
            data: Raw webhook data

        Returns:
            Parsed message data
        """
        return {
            "channel": "MAX",
            "external_id": str(data.get("message", {}).get("sender", {}).get("id", "")),
            "text": data.get("message", {}).get("text", ""),
            "message_id": str(data.get("message", {}).get("id", "")),
            "timestamp": data.get("message", {}).get("date", 0),
        }

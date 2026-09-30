"""
VK Gateway
Integration with VK via vk_api (Callback API)
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VKGateway:
    """Gateway for VK integration."""

    def __init__(self):
        self._session = None
        self._access_token = settings.VK_ACCESS_TOKEN
        self._group_id = settings.VK_GROUP_ID

    def _get_session(self) -> Any:
        """Lazy initialization of VK session."""
        if self._session is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("VK integration disabled (ENABLE_LLM=false)")

            try:
                import vk_api

                self._session = vk_api.VkApi(token=self._access_token)
                logger.info("VK session initialized")
            except ImportError:
                raise RuntimeError("vk_api package not installed")

        return self._session

    async def send_message(
        self,
        user_id: str | int,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """
        Send message to VK user.

        Args:
            user_id: User identifier
            message: Message text
            **kwargs: Additional parameters

        Returns:
            True if sent successfully
        """
        if not settings.ENABLE_LLM:
            logger.warning("VK integration disabled, skipping send")
            return False

        try:
            session = self._get_session()
            vk = session.get_api()
            vk.messages.send(
                user_id=user_id,
                message=message,
                random_id=kwargs.get("random_id", 0),
                **{k: v for k, v in kwargs.items() if k != "random_id"},
            )
            logger.info(f"Message sent to VK user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send VK message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse incoming webhook data from VK (Callback API).

        Args:
            data: Raw webhook data

        Returns:
            Parsed message data
        """
        object_data = data.get("object", {})
        message = object_data.get("message", {}) if isinstance(object_data, dict) else object_data

        return {
            "channel": "VK",
            "external_id": str(message.get("user_id", "")),
            "text": message.get("text", ""),
            "message_id": str(message.get("id", "")),
            "timestamp": message.get("date", 0),
        }

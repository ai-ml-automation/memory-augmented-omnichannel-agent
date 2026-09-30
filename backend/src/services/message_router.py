"""
Message Router
Routes incoming messages to the appropriate handler based on channel type
"""

import logging
from typing import Any, Callable, Coroutine

from backend.src.config import get_settings
from backend.src.services.channel_binding_service import ChannelBindingService

logger = logging.getLogger(__name__)
settings = get_settings()


class MessageRouter:
    """
    Routes messages by channel type.

    Orchestrates message flow:
    1. Identify user by channel + external_id
    2. Route to appropriate handler
    3. Return response
    """

    def __init__(self):
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, str]]] = {}

    def register_handler(
        self,
        channel_type: str,
        handler: Callable[..., Coroutine[Any, Any, str]],
    ) -> None:
        """
        Register a handler for channel type.

        Args:
            channel_type: Channel type (MAX, TG, VK, VOICE)
            handler: Async handler function
        """
        self._handlers[channel_type.upper()] = handler
        logger.info(f"Registered handler for channel: {channel_type}")

    async def route_message(
        self,
        channel_type: str,
        external_id: str,
        text: str,
        binding_service: ChannelBindingService,
        **kwargs: Any,
    ) -> str:
        """
        Route message to appropriate handler.

        Args:
            channel_type: Channel type
            external_id: External ID
            text: Message text
            binding_service: Channel binding service
            **kwargs: Additional context

        Returns:
            Response text

        Raises:
            ValueError: If no handler for channel type
        """
        handler = self._handlers.get(channel_type.upper())

        if not handler:
            raise ValueError(f"No handler registered for channel: {channel_type}")

        # Identify user
        user = await binding_service.find_user_by_channel(
            channel_type=channel_type,
            external_id=external_id,
        )

        if not user:
            logger.warning(
                f"No user found for {channel_type}:{external_id}"
            )
            return "Для использования бота необходимо зарегистрироваться через веб-интерфейс."

        # Route to handler
        try:
            response = await handler(
                user_id=user.id,
                text=text,
                **kwargs,
            )
            return response
        except Exception as e:
            logger.error(f"Handler error for {channel_type}: {e}")
            return "Произошла ошибка при обработке сообщения."

    def get_registered_channels(self) -> list[str]:
        """Get list of registered channel types."""
        return list(self._handlers.keys())


# Default message router instance
message_router = MessageRouter()

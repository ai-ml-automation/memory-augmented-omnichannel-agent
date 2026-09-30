"""
Message Handler
Unified message processing pipeline
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.models import User
from backend.src.services.audit_service import AuditService
from backend.src.services.channel_binding_service import ChannelBindingService
from backend.src.services.consent_service import ConsentService

logger = logging.getLogger(__name__)
settings = get_settings()


class MessageHandler:
    """
    Unified message handler.

    Processes incoming messages through:
    1. User identification (via ChannelBinding)
    2. Consent verification (152-FZ)
    3. Memory check (fact lookup)
    4. Response generation (placeholder)
    5. Audit logging (152-FZ)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.binding_service = ChannelBindingService(db)
        self.consent_service = ConsentService(db)
        self.audit_service = AuditService(db)

    async def handle_message(
        self,
        channel_type: str,
        external_id: str,
        text: str,
        **kwargs: Any,
    ) -> str:
        """
        Handle incoming message.

        Args:
            channel_type: Channel type (MAX, TG, VK, VOICE)
            external_id: External ID
            text: Message text
            **kwargs: Additional context

        Returns:
            Response text
        """
        # 1. Identify user
        user = await self.binding_service.find_user_by_channel(
            channel_type=channel_type,
            external_id=external_id,
        )

        if not user:
            return await self._handle_unknown_user(channel_type, external_id)

        # 2. Check consent (152-FZ)
        has_consent = await self.consent_service.has_active_consent(
            user_id=user.id,
        )

        if not has_consent:
            return await self._handle_no_consent(user)

        # 3. Process message (placeholder for AI pipeline)
        response = await self._process_with_memory(
            user=user,
            text=text,
            **kwargs,
        )

        # 4. Audit log
        await self.audit_service.log_action(
            user_id=user.id,
            action="READ",
            source=channel_type,
        )

        return response

    async def _handle_unknown_user(
        self,
        channel_type: str,
        external_id: str,
    ) -> str:
        """Handle message from unknown user."""
        logger.info(
            f"Unknown user: {channel_type}:{external_id}"
        )
        return (
            "Для использования бота необходимо зарегистрироваться "
            "через веб-интерфейс."
        )

    async def _handle_no_consent(self, user: User) -> str:
        """Handle message from user without consent."""
        logger.warning(
            f"User {user.id} has no active consent"
        )
        return (
            "Для обработки сообщений необходимо дать согласие "
            "на обработку персональных данных."
        )

    async def _process_with_memory(
        self,
        user: User,
        text: str,
        **kwargs: Any,
    ) -> str:
        """
        Process message with memory context.

        This is a placeholder for the AI pipeline that will:
        1. Search facts in memory
        2. Build context
        3. Generate response
        4. Store new facts
        """
        # TODO: Integrate with memory service (Phase 3)
        # TODO: Integrate with LLM service (Phase 4)
        logger.info(f"Processing message for user {user.id}")

        return f"Обработка сообщения: {text}"


def register_default_handler() -> None:
    """Register default message handler for all channels."""
    # This will be called during app initialization
    pass

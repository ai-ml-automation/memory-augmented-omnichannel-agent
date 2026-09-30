"""
Сервис управления согласием (152-ФЗ): выдача, отзыв, проверка статуса.

Основание обработки персональных данных по ст. 6 152-ФЗ — согласие субъекта.
B.3.2: revoke_consent запускает каскадное удаление данных через
RightToBeForgottenService (PostgreSQL, Qdrant, Neo4j).
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Consent, User

logger = logging.getLogger(__name__)


class ConsentService:
    """
    Сервис согласий: grant/revoke/has/get.

    Хранит историю согласий (не перезаписывает): отзыв помечает revoked_at,
    что сохраняет аудит-след для 152-ФЗ. Активное согласие — запись без revoked_at.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_consent(
        self,
        user_id: uuid.UUID,
        channel: str,
        ip_address: str | None = None,
    ) -> Consent:
        """
        Выдача согласия на обработку данных.

        Args:
            user_id: идентификатор пользователя
            channel: канал (MAX, TG, VK, VOICE)
            ip_address: IP клиента для аудита

        Returns:
            созданная запись Consent

        Raises:
            ValueError: если пользователь не найден
        """
        # Check if user exists
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Create consent record
        consent = Consent(
            id=uuid.uuid4(),
            user_id=user_id,
            granted_at=datetime.utcnow(),
            channel=channel,
            ip_address=ip_address,
        )
        self.db.add(consent)
        await self.db.flush()

        return consent

    async def revoke_consent(
        self,
        user_id: uuid.UUID,
        source: str = "OPERATOR",
    ) -> None:
        """
        Отзыв согласия с каскадным удалением данных (B.3.2).

        Запускает RightToBeForgottenService.delete_user_data: удаление из
        PostgreSQL, Qdrant и Neo4j — право на забвение (ст. 17 152-ФЗ).
        Args:
            user_id: идентификатор пользователя
            source: источник отзыва (OPERATOR, AI, USER_REQUEST)
        """
        # Find active consent
        result = await self.db.execute(
            select(Consent).where(
                Consent.user_id == user_id,
                Consent.revoked_at.is_(None),
            )
        )
        consent = result.scalar_one_or_none()

        if not consent:
            raise ValueError("No active consent found")

        # Mark as revoked
        consent.revoked_at = datetime.utcnow()
        await self.db.flush()

        logger.info(
            "Consent revoked for user=%s channel=%s",
            user_id,
            consent.channel,
        )

        # B.3.2: Trigger Right to be Forgotten cascade deletion
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        rtbf = RightToBeForgottenService(self.db)
        summary = await rtbf.delete_user_data(
            user_id=user_id,
            source=source,
        )

        logger.info(
            "RightToBeForgotten triggered by consent revoke: %s",
            summary,
        )

    async def has_active_consent(self, user_id: uuid.UUID) -> bool:
        """
        Проверка активного согласия (запись без revoked_at).
        Args:
            user_id: идентификатор пользователя
        Returns:
            True если активное согласие существует
        """
        result = await self.db.execute(
            select(Consent).where(
                Consent.user_id == user_id,
                Consent.revoked_at.is_(None),
            )
        )
        consent = result.scalar_one_or_none()

        return consent is not None

    async def get_consent_status(
        self, user_id: uuid.UUID
    ) -> dict:
        """
        Статус согласия: последняя запись в истории.

        Нет записей — признак «согласие не давалось» (не то же, что отзыв).
        Args:
            user_id: идентификатор пользователя
        Returns:
            dict: has_active_consent, granted_at, revoked_at
        """
        result = await self.db.execute(
            select(Consent)
            .where(Consent.user_id == user_id)
            .order_by(Consent.granted_at.desc())
            .limit(1)
        )
        consent = result.scalar_one_or_none()

        if not consent:
            return {
                "has_active_consent": False,
                "granted_at": None,
                "revoked_at": None,
            }

        return {
            "has_active_consent": consent.revoked_at is None,
            "granted_at": consent.granted_at,
            "revoked_at": consent.revoked_at,
        }

"""
Сервис сессий омниканального взаимодействия.

Сессия привязывает контекст диалога к пользователю и каналу (MAX, TG, VK, VOICE):
позволяет продолжать разговор после переключения канала и хранить контекст
между сообщениями. Открытая сессия — запись без ended_at.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Session


class SessionService:
    """
    Сервис управления сессиями пользователя.

    Операции: start (создать), end (закрыть), получить активную/историю.
    Сессия считается активной, пока ended_at не установлен.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_session(
        self,
        user_id: uuid.UUID,
        channel_type: str,
        context_json: dict | None = None,
    ) -> Session:
        """
        Создание новой сессии.

        started_at проставляется на уровне приложения: серверное время
        одинаково для всех каналов и не зависит от часового пояса клиента.
        Args:
            user_id: идентификатор пользователя
            channel_type: канал (MAX, TG, VK, VOICE)
            context_json: стартовый контекст диалога
        Returns:
            созданная сессия Session
        """
        session = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            channel_type=channel_type,
            started_at=datetime.utcnow(),
            context_json=context_json,
        )
        self.db.add(session)
        await self.db.flush()

        return session

    async def end_session(self, session_id: uuid.UUID) -> Session:
        """
        Закрытие сессии: простановка ended_at.

        Сессия не удаляется — сохраняется для аудита и восстановления контекста.
        Args:
            session_id: идентификатор сессии
        Returns:
            обновлённая сессия Session
        Raises:
            ValueError: если сессия не найдена
        """
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Session not found")

        session.ended_at = datetime.utcnow()
        await self.db.flush()

        return session

    async def get_active_session(
        self,
        user_id: uuid.UUID,
        channel_type: str,
    ) -> Session | None:
        """
        Активная сессия пользователя на канале.

        Условие ended_at IS NULL гарантирует уникальность активной сессии:
        канал не может вести два параллельных диалога с одним пользователем.
        Args:
            user_id: идентификатор пользователя
            channel_type: канал (MAX, TG, VK, VOICE)
        Returns:
            Session или None
        """
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.channel_type == channel_type,
                Session.ended_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[Session]:
        """
        История сессий пользователя (новые сверху).

        limit ограничивает выборку — для UI достаточно последних N сессий.
        Args:
            user_id: идентификатор пользователя
            limit: максимальное число сессий
        Returns:
            список Session
        """
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

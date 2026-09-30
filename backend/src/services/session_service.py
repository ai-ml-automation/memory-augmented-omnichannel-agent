"""
Session Service
Session management for omnichannel interactions
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Session


class SessionService:
    """Service for managing user sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_session(
        self,
        user_id: uuid.UUID,
        channel_type: str,
        context_json: dict | None = None,
    ) -> Session:
        """
        Start a new session.

        Args:
            user_id: User identifier
            channel_type: Channel type (MAX, TG, VK, VOICE)
            context_json: Optional context data

        Returns:
            Created Session instance
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
        End a session.

        Args:
            session_id: Session identifier

        Returns:
            Updated Session instance

        Raises:
            ValueError: If session not found
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
        Get active session for user and channel.

        Args:
            user_id: User identifier
            channel_type: Channel type

        Returns:
            Active Session or None
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
        Get recent sessions for user.

        Args:
            user_id: User identifier
            limit: Maximum number of sessions

        Returns:
            List of Session instances
        """
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

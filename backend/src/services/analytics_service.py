"""
Analytics Service
Analytics and reporting for omnichannel agent
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import AuditLog, Consent, Fact, Session, User

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and reporting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(self) -> dict[str, Any]:
        """
        Get dashboard statistics.

        Returns:
            Dashboard stats
        """
        # User count
        user_result = await self.db.execute(select(func.count(User.id)))
        user_count = user_result.scalar() or 0

        # Active sessions
        session_result = await self.db.execute(
            select(func.count(Session.id)).where(Session.ended_at.is_(None))
        )
        active_sessions = session_result.scalar() or 0

        # Total facts
        fact_result = await self.db.execute(
            select(func.count(Fact.id)).where(Fact.is_active)
        )
        total_facts = fact_result.scalar() or 0

        # Active consents
        consent_result = await self.db.execute(
            select(func.count(Consent.id)).where(Consent.is_active)
        )
        active_consents = consent_result.scalar() or 0

        # Audit logs today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        audit_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today)
        )
        audit_today = audit_result.scalar() or 0

        return {
            "users": user_count,
            "active_sessions": active_sessions,
            "total_facts": total_facts,
            "active_consents": active_consents,
            "audit_today": audit_today,
        }

    async def get_user_activity(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get user activity stats.

        Args:
            user_id: User identifier
            days: Number of days to analyze

        Returns:
            Activity stats
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Sessions count
        session_result = await self.db.execute(
            select(func.count(Session.id)).where(
                Session.user_id == user_id,
                Session.started_at >= since,
            )
        )
        sessions_count = session_result.scalar() or 0

        # Facts count
        fact_result = await self.db.execute(
            select(func.count(Fact.id)).where(
                Fact.user_id == user_id,
                Fact.created_at >= since,
            )
        )
        facts_count = fact_result.scalar() or 0

        # Audit actions
        audit_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == user_id,
                AuditLog.timestamp >= since,
            )
        )
        audit_count = audit_result.scalar() or 0

        return {
            "user_id": str(user_id),
            "period_days": days,
            "sessions": sessions_count,
            "facts_created": facts_count,
            "audit_actions": audit_count,
        }

    async def get_channel_distribution(self) -> dict[str, int]:
        """
        Get channel usage distribution.

        Returns:
            Channel distribution
        """
        result = await self.db.execute(
            select(
                Session.channel_type,
                func.count(Session.id),
            ).group_by(Session.channel_type)
        )

        distribution = {}
        for channel_type, count in result.all():
            distribution[channel_type] = count

        return distribution

    async def get_fact_categories(self) -> dict[str, int]:
        """
        Get fact category distribution.

        Returns:
            Category distribution
        """
        result = await self.db.execute(
            select(
                Fact.category,
                func.count(Fact.id),
            ).where(Fact.is_active).group_by(Fact.category)
        )

        distribution = {}
        for category, count in result.all():
            distribution[category] = count

        return distribution

    async def get_audit_timeline(
        self,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Get audit log timeline.

        Args:
            days: Number of days

        Returns:
            Timeline data
        """
        since = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(AuditLog.timestamp).label("date"),
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.timestamp >= since)
            .group_by(func.date(AuditLog.timestamp))
            .order_by(func.date(AuditLog.timestamp))
        )

        return [
            {"date": str(row.date), "count": row.count}
            for row in result.all()
        ]

    async def get_peak_hours(self) -> list[dict[str, Any]]:
        """
        Get peak activity hours.

        Returns:
            Hourly activity distribution
        """
        result = await self.db.execute(
            select(
                func.extract("hour", AuditLog.timestamp).label("hour"),
                func.count(AuditLog.id).label("count"),
            )
            .group_by(func.extract("hour", AuditLog.timestamp))
            .order_by(func.extract("hour", AuditLog.timestamp))
        )

        return [
            {"hour": int(row.hour), "count": row.count}
            for row in result.all()
        ]

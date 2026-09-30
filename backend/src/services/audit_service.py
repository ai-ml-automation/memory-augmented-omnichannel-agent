"""
Audit Service
152-FZ compliance: audit logging
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import AuditLog


class AuditService:
    """Service for audit logging (152-FZ)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        user_id: uuid.UUID,
        action: str,
        source: str,
        fact_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Log an audit action.

        Args:
            user_id: User identifier
            action: Action type (READ, WRITE, DELETE)
            source: Action source (AI, OPERATOR)
            fact_id: Related fact identifier (optional)
            ip_address: Client IP address (optional)

        Returns:
            Created AuditLog instance
        """
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            source=source,
            fact_id=fact_id,
            timestamp=datetime.utcnow(),
            ip_address=ip_address,
        )
        self.db.add(audit_log)
        await self.db.flush()

        return audit_log

    async def get_user_audit_logs(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Get audit logs for user.

        Args:
            user_id: User identifier
            limit: Maximum number of logs

        Returns:
            List of AuditLog instances
        """
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_fact_audit_logs(
        self,
        fact_id: uuid.UUID,
    ) -> list[AuditLog]:
        """
        Get audit logs for specific fact.

        Args:
            fact_id: Fact identifier

        Returns:
            List of AuditLog instances
        """
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.fact_id == fact_id)
            .order_by(AuditLog.timestamp.desc())
        )
        return list(result.scalars().all())

"""
Consent Service
152-FZ compliance: consent management

B.3.2: revoke_consent now triggers RightToBeForgotten cascade deletion
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Consent, User

logger = logging.getLogger(__name__)


class ConsentService:
    """Service for managing user consent (152-FZ)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_consent(
        self,
        user_id: uuid.UUID,
        channel: str,
        ip_address: str | None = None,
    ) -> Consent:
        """
        Grant consent for data processing.

        Args:
            user_id: User identifier
            channel: Channel type (MAX, TG, VK, VOICE)
            ip_address: Client IP address

        Returns:
            Created Consent instance
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
        Revoke user consent and trigger Right to be Forgotten.

        B.3.2: This now triggers cascade deletion of all user data
        from PostgreSQL, Qdrant, and Neo4j.

        Args:
            user_id: User identifier
            source: Audit source (OPERATOR, AI, USER_REQUEST)
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
        Check if user has active consent.

        Args:
            user_id: User identifier

        Returns:
            True if active consent exists
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
        Get consent status for user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with consent status
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

"""
Fact Service
Storage and retrieval of facts in long-term memory.

Aligned with Fact model: type, value, weight, channel, created_at,
expires_at, is_superseded.

Security (Phase B):
- value is AES-256-GCM encrypted before DB storage
- consent check (152-FZ) enforced before all memory writes

Audit (Phase B.3.3):
- All memory operations logged via AuditService (152-FZ)
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Fact
from backend.src.utils.crypto import decrypt, encrypt, is_encrypted
from backend.src.metrics import FACTS_EXTRACTED_TOTAL

logger = logging.getLogger(__name__)

# Valid fact types per SPEC 3.3
VALID_FACT_TYPES = frozenset({
    "intent",
    "preference",
    "complaint",
    "agreement",
    "rejection",
    "personal_info",
})

DEFAULT_FACT_WEIGHT = 1.0
DEFAULT_EXPIRY_DAYS = 90


class FactService:
    """Service for managing facts in long-term memory."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # B.1.4: consent helper
    # ------------------------------------------------------------------
    async def _require_consent(self, user_id: uuid.UUID) -> None:
        """
        Check that user has active consent (152-FZ).

        Raises:
            PermissionError: If no active consent
        """
        from backend.src.services.consent_service import ConsentService

        svc = ConsentService(self.db)
        if not await svc.has_active_consent(user_id):
            raise PermissionError(
                "Active consent required for memory operations (152-FZ)"
            )

    # ------------------------------------------------------------------
    # B.3.3: audit helper
    # ------------------------------------------------------------------
    async def _audit(
        self,
        user_id: uuid.UUID,
        action: str,
        fact_id: uuid.UUID | None = None,
        source: str = "AI",
        ip_address: str | None = None,
    ) -> None:
        """
        Log an audit event for 152-FZ compliance.

        B.3.3: All memory operations are logged.

        Args:
            user_id: User identifier
            action: Action type (READ, WRITE, DELETE)
            fact_id: Related fact (optional)
            source: Action source (AI, OPERATOR)
            ip_address: Client IP (optional)
        """
        from backend.src.services.audit_service import AuditService

        try:
            svc = AuditService(self.db)
            await svc.log_action(
                user_id=user_id,
                action=action,
                source=source,
                fact_id=fact_id,
                ip_address=ip_address,
            )
        except Exception as e:
            # Audit failure must not break the operation
            logger.error("Audit log failed: %s", e)

    # ------------------------------------------------------------------
    # B.1.2: encryption helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _encrypt_value(plaintext: str) -> str:
        """Encrypt fact value before storage."""
        return encrypt(plaintext)

    @staticmethod
    def _decrypt_value(ciphertext: str) -> str:
        """Decrypt fact value after retrieval."""
        if is_encrypted(ciphertext):
            return decrypt(ciphertext)
        # Fallback: value is not encrypted (legacy or non-PII data)
        return ciphertext

    def _decrypt_fact(self, fact: Fact) -> Fact:
        """Decrypt a single fact's value in-place (returns the same object)."""
        if fact.value:
            fact.value = self._decrypt_value(fact.value)
        return fact

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def store_fact(
        self,
        user_id: uuid.UUID,
        fact_type: str,
        value: str,
        channel: str,
        weight: float = DEFAULT_FACT_WEIGHT,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    ) -> Fact:
        """
        Store a new fact.

        1. Validates fact type
        2. Checks active consent (152-FZ)
        3. Encrypts value (AES-256-GCM)
        4. Persists to DB
        5. Logs audit (WRITE)

        Args:
            user_id: User identifier
            fact_type: One of VALID_FACT_TYPES
            value: Fact content text (will be encrypted)
            channel: Source channel (MAX, TG, VK, VOICE)
            weight: Importance weight (0.0 to 1.0)
            expires_in_days: Days until auto-expiry

        Returns:
            Created Fact instance (with decrypted value)

        Raises:
            ValueError: If fact_type is not valid
            PermissionError: If user has no active consent
        """
        if fact_type not in VALID_FACT_TYPES:
            raise ValueError(
                f"Invalid fact type '{fact_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_FACT_TYPES))}"
            )

        # B.1.4: consent check (152-FZ)
        await self._require_consent(user_id)

        # B.1.2: encrypt value
        encrypted_value = self._encrypt_value(value)

        now = datetime.utcnow()
        fact = Fact(
            id=uuid.uuid4(),
            user_id=user_id,
            type=fact_type,
            value=encrypted_value,
            weight=weight,
            channel=channel,
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days),
            is_superseded=False,
        )
        self.db.add(fact)
        await self.db.flush()

        # B.3.3: audit log (WRITE)
        await self._audit(
            user_id=user_id,
            action="WRITE",
            fact_id=fact.id,
            source=channel if channel in ("AI", "OPERATOR") else "AI",
        )

        logger.info(
            "Fact stored: id=%s type=%s channel=%s encrypted=True",
            fact.id,
            fact_type,
            channel,
        )

        # F.1.1: Track facts extracted per channel
        FACTS_EXTRACTED_TOTAL.labels(channel=channel).inc()

        # Return with decrypted value for caller
        return self._decrypt_fact(fact)

    async def get_facts(
        self,
        user_id: uuid.UUID,
        fact_type: str | None = None,
        active_only: bool = True,
        min_weight: float = 0.0,
        limit: int = 100,
    ) -> list[Fact]:
        """
        Get facts for user (values are decrypted on retrieval).

        152-FZ: Active consent is required before reading facts.
        B.3.3: Logs a READ audit event.

        Args:
            user_id: User identifier
            fact_type: Optional type filter
            active_only: Exclude superseded facts
            min_weight: Minimum weight threshold
            limit: Maximum number of facts

        Returns:
            List of Fact instances with decrypted values

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        # II.1: consent check on READ (152-FZ §7.1)
        await self._require_consent(user_id)

        query = select(Fact).where(Fact.user_id == user_id)

        if active_only:
            query = query.where(Fact.is_superseded == False)  # noqa: E712
        if fact_type:
            query = query.where(Fact.type == fact_type)
        if min_weight > 0:
            query = query.where(Fact.weight >= min_weight)

        query = query.order_by(Fact.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        facts = list(result.scalars().all())

        # B.3.3: audit log (READ)
        await self._audit(user_id=user_id, action="READ")

        # B.1.2: decrypt all values
        return [self._decrypt_fact(f) for f in facts]

    async def get_fact(
        self,
        fact_id: uuid.UUID,
    ) -> Fact | None:
        """
        Get fact by ID (value decrypted).

        152-FZ: Active consent is required before reading facts.
        B.3.3: Logs a READ audit event.

        Args:
            fact_id: Fact identifier

        Returns:
            Fact instance with decrypted value, or None

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        result = await self.db.execute(
            select(Fact).where(Fact.id == fact_id)
        )
        fact = result.scalar_one_or_none()
        if fact:
            # II.1: consent check on READ (152-FZ §7.1)
            await self._require_consent(fact.user_id)

            # B.3.3: audit log (READ)
            await self._audit(
                user_id=fact.user_id,
                action="READ",
                fact_id=fact.id,
            )
            return self._decrypt_fact(fact)
        return None

    async def supersede_fact(
        self,
        fact_id: uuid.UUID,
    ) -> bool:
        """
        Mark a fact as superseded (replaced by newer data).

        152-FZ: Active consent is required before modifying facts.
        B.3.3: Logs a WRITE audit event.

        Args:
            fact_id: Fact identifier

        Returns:
            True if superseded

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        fact = await self._get_fact_raw(fact_id)
        if not fact:
            return False

        # II.1: consent check (152-FZ §7.1)
        await self._require_consent(fact.user_id)

        fact.is_superseded = True
        fact.weight = 0.1
        await self.db.flush()

        # B.3.3: audit log (WRITE)
        await self._audit(
            user_id=fact.user_id,
            action="WRITE",
            fact_id=fact.id,
        )

        return True

    async def delete_fact(
        self,
        fact_id: uuid.UUID,
    ) -> bool:
        """
        Hard-delete a fact (used by RightToBeForgotten).

        152-FZ: Active consent is required before deleting facts.
        B.3.3: Logs a DELETE audit event.

        Args:
            fact_id: Fact identifier

        Returns:
            True if deleted

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        fact = await self._get_fact_raw(fact_id)
        if not fact:
            return False

        # II.1: consent check (152-FZ §7.1)
        await self._require_consent(fact.user_id)

        # B.3.3: audit log (DELETE) before deletion
        await self._audit(
            user_id=fact.user_id,
            action="DELETE",
            fact_id=fact.id,
        )

        await self.db.delete(fact)
        await self.db.flush()

        return True

    async def search_facts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[Fact]:
        """
        Search facts by value text.

        NOTE: LIKE search does not work on encrypted data.
        This method retrieves all active facts and performs
        in-memory search on decrypted values.
        For production, use VectorStoreService (Qdrant) instead.

        152-FZ: Active consent is required before reading/searching facts.
        B.3.3: Logs a READ audit event.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            Matching facts with decrypted values

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        # II.1: consent check on READ (152-FZ §7.1)
        await self._require_consent(user_id)

        # Fetch all active facts (encrypted)
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == user_id,
                Fact.is_superseded == False,  # noqa: E712
            ).limit(500)  # bounded scan
        )
        all_facts = list(result.scalars().all())

        # Decrypt and filter in memory
        query_lower = query.lower()
        matches: list[Fact] = []
        for fact in all_facts:
            decrypted = self._decrypt_value(fact.value)
            if query_lower in decrypted.lower():
                fact.value = decrypted  # attach decrypted value
                matches.append(fact)
                if len(matches) >= limit:
                    break

        # B.3.3: audit log (READ)
        await self._audit(user_id=user_id, action="READ")

        return matches

    async def get_user_stats(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, int]:
        """
        Get fact statistics for user.

        152-FZ: Active consent is required before reading fact data.

        Args:
            user_id: User identifier

        Returns:
            Statistics dict with counts per type

        Raises:
            PermissionError: If user has no active consent (152-FZ)
        """
        # II.1: consent check (152-FZ §7.1)
        await self._require_consent(user_id)

        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == user_id,
                Fact.is_superseded == False,  # noqa: E712
            )
        )
        facts = result.scalars().all()

        stats: dict[str, int] = {ft: 0 for ft in VALID_FACT_TYPES}
        stats["total"] = 0

        for fact in facts:
            stats["total"] += 1
            if fact.type in stats:
                stats[fact.type] += 1

        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _get_fact_raw(self, fact_id: uuid.UUID) -> Fact | None:
        """Get fact without decryption (for internal mutations)."""
        result = await self.db.execute(
            select(Fact).where(Fact.id == fact_id)
        )
        return result.scalar_one_or_none()

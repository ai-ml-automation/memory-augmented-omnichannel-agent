"""
Сервис фактов: хранение и получение фактов долговременной памяти.

Модель данных — Fact: type, value, weight, channel, created_at,
expires_at, is_superseded.

ПОЧЕМУ факты — отдельная сущность: сессии описывают «когда и откуда
пришёл запрос», а факты — «что мы знаем о пользователе». Факты живут
дольше сессий и переиспользуются всеми сценариями (чат, голос, поиск).

Безопасность (Phase B):
- value шифруется AES-256-GCM перед записью в БД (B.1.2);
- перед любой записью в память проверяется активное согласие 152-ФЗ (B.1.4).

Аудит (Phase B.3.3):
- все операции с памятью логируются через AuditService (152-ФЗ).
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
    """
    Сервис управления фактами долговременной памяти.

    Единая точка CRUD-операций с фактами: создание, чтение, обновление
    (supersede), удаление и поиск. Все публичные операции:
    - проверяют активное согласие пользователя (152-ФЗ, II.1);
    - логируют событие в аудит-журнал (B.3.3);
    - возвращают значение факта расшифрованным (B.1.2).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # B.1.4: consent helper
    # ------------------------------------------------------------------
    async def _require_consent(self, user_id: uuid.UUID) -> None:
        """
        Проверить наличие активного согласия пользователя (152-ФЗ).

        ПОЧЕМУ: 152-ФЗ требует подтверждения согласия на обработку
        ПДн перед любой операцией записи/чтения памяти (B.1.4, II.1).

        Raises:
            PermissionError: Если активное согласие отсутствует
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
        Записать событие аудита для соответствия 152-ФЗ (B.3.3).

        ПОЧЕМУ: все операции с памятью обязаны оставлять след — при
        RTBF и проверках регулятора нужен полный журнал обращений.

        Args:
            user_id: Идентификатор пользователя
            action: Тип действия (READ, WRITE, DELETE)
            fact_id: Связанный факт (необязательно)
            source: Источник действия (AI, OPERATOR)
            ip_address: IP-адрес клиента (необязательно)
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
        """
        Зашифровать значение факта перед записью в БД (B.1.2).

        Обёртка над utils.crypto.encrypt: единая точка вызова, чтобы
        логика шифрования не дублировалась по сервису.
        """
        return encrypt(plaintext)

    @staticmethod
    def _decrypt_value(ciphertext: str) -> str:
        """
        Расшифровать значение факта после чтения (B.1.2).

        ПОЧЕМУ fallback: старые или не-ПДн значения могут лежать
        открытым текстом — is_encrypted отличает их от шифротекста.
        """
        if is_encrypted(ciphertext):
            return decrypt(ciphertext)
        # Fallback: value is not encrypted (legacy or non-PII data)
        return ciphertext

    def _decrypt_fact(self, fact: Fact) -> Fact:
        """
        Расшифровать значение одного факта на месте (in-place).

        ПОЧЕМУ возвращает тот же объект: вызывающий код успевает
        работать с Fact до повторной сериализации, без копий.
        """
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
        Сохранить новый факт: валидация типа → согласие (152-ФЗ,
        B.1.4) → шифрование (AES-256-GCM, B.1.2) → запись в БД.

        Args:
            user_id: Идентификатор пользователя
            fact_type: Один из VALID_FACT_TYPES
            value: Текст факта (будет зашифрован)
            channel: Канал-источник (MAX, TG, VK, VOICE)
            weight: Вес важности (0.0–1.0)
            expires_in_days: Дней до авто-протухания

        Returns:
            Созданный Fact (значение расшифровано)

        Raises:
            ValueError: Некорректный fact_type
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Получить факты пользователя (значения расшифровываются).

        Чтение требует активного согласия (152-ФЗ §7.1, II.1) и
        логируется как READ (B.3.3) — даже если фактов не найдено.

        Args:
            user_id: Идентификатор пользователя
            fact_type: Фильтр по типу (необязательно)
            active_only: Исключить superseded-факты
            min_weight: Минимальный порог веса
            limit: Максимум фактов

        Returns:
            Список Fact с расшифрованными значениями

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Получить факт по ID (значение расшифровано).

        Согласие проверяется по владельцу факта, а не по переданному
        ID — защита от чтения чужих фактов (152-ФЗ §7.1, II.1).

        Args:
            fact_id: Идентификатор факта

        Returns:
            Fact с расшифрованным значением, или None

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Пометить факт как замещённый (superseded) новыми данными.

        История сохраняется, а не перезаписывается: вес падает до
        0.1, факт исключается из выборок active_only, но остаётся
        в БД для аудита и отката (152-ФЗ, B.3.3).

        Args:
            fact_id: Идентификатор факта

        Returns:
            True, если факт помечен

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Жёстко удалить факт (используется RightToBeForgotten).

        Аудит DELETE пишется ДО удаления: после удаления события в
        журнале ссылаются на удалённый id, но сохраняют след (B.3.3).

        Args:
            fact_id: Идентификатор факта

        Returns:
            True, если факт удалён

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Найти факты по тексту значения.

        ПОЧЕМУ in-memory: LIKE-поиск не работает на шифрованных
        данных — метод тянет активные факты (до 500) и фильтрует
        по расшифрованным значениям. Для продакшена используйте
        VectorStoreService (Qdrant).

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Подходящие факты с расшифрованными значениями

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        Статистика фактов пользователя.

        Считаются только активные факты (не superseded); чтение
        требует активного согласия (152-ФЗ, II.1).

        Args:
            user_id: Идентификатор пользователя

        Returns:
            Словарь с количеством фактов по каждому типу

        Raises:
            PermissionError: Нет активного согласия (152-ФЗ)
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
        """
        Получить факт без расшифровки (для внутренних мутаций).

        ПОЧЕМУ: мутации (supersede/delete) не читают значение —
        расшифровка была бы лишней работой и риском для ПДн.
        """
        result = await self.db.execute(
            select(Fact).where(Fact.id == fact_id)
        )
        return result.scalar_one_or_none()

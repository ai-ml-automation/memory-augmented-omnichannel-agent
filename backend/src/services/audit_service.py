"""
Сервис аудит-лога (152-ФЗ).

Фиксирует действия с ПДн: кто (user_id), что (action: READ/WRITE/DELETE),
откуда (source: AI/OPERATOR) и когда. Хранится в AuditLog без возможности
перезаписи — цепочка неизменяемых записей для проверок регулятора.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import AuditLog


class AuditService:
    """
    Сервис журналирования действий с ПДн (152-ФЗ).

    Единая точка записи: все операции чтения/изменения/удаления данных
    пользователя логируются здесь, чтобы аудит-след был полным.
    """

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
        Запись одного аудит-события.

        id и timestamp генерируются здесь (не в БД): сервис не зависит от
        диалекта БД и может писать в любую сессию.
        Args:
            user_id: идентификатор пользователя
            action: тип действия (READ, WRITE, DELETE)
            source: источник (AI, OPERATOR)
            fact_id, ip_address: опционально — факт и IP клиента
        Returns:
            созданная запись AuditLog
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
        Лог действий пользователя, новые записи первыми.

        limit защищает от выгрузки всей истории: выдача ограничена пагинацией.
        Args:
            user_id: идентификатор пользователя
            limit: максимальное число записей
        Returns:
            список AuditLog (новые сверху)
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
        Лог действий по конкретному факту (новые сверху).

        Используется для проверки: кто и когда читал/менял конкретный факт.
        Args:
            fact_id: идентификатор факта
        Returns:
            список AuditLog по факту
        """
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.fact_id == fact_id)
            .order_by(AuditLog.timestamp.desc())
        )
        return list(result.scalars().all())

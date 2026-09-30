"""
Аналитика и отчётность для омниканального агента.

Отдельный сервис агрегатов для дашборда и админки: считаем только COUNT и
распределения по channel_type/category/часам — никогда не выгружаем сырые
факты или аудит-логи. Это осознанное ограничение приватности (152-ФЗ):
статистика не должна содержать персональных данных пользователей.

Все агрегации выполняются на стороне БД (func.count/group_by), чтобы не
тянуть строки в Python — отчётные эндпоинты остаются лёгкими при росте
данных.
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
    """Сбор агрегированной статистики из БД для дашборда и админки.

    Методы возвращают только числа и распределения, готовые к сериализации
    в JSON. Ни один метод не раскрывает содержимое персональных данных —
    только обезличенные счётчики (приватность, 152-ФЗ).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(self) -> dict[str, Any]:
        """Счётчики верхнего уровня для главного экрана дашборда.

        Считаем пользователей, активные сессии, активные факты, активные
        согласия и аудит-события за сегодня. Вместо выборки строк используем
        COUNT в БД — отчёт остаётся лёгким при любом объёме данных.

        Returns:
            Словарь: users, active_sessions, total_facts, active_consents,
            audit_today (числа, 0 при отсутствии данных).
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
        """Активность конкретного пользователя за период.

        Считаем сессии, созданные факты и аудит-действия с момента
        since = now - days. Период ограничиваем на стороне БД (WHERE
        >= since), а не фильтруем в Python. user_id возвращаем строкой,
        чтобы ответ сериализовался в JSON без конвертации UUID.

        Args:
            user_id: Идентификатор пользователя.
            days: Глубина анализа в днях (по умолчанию 30).

        Returns:
            Словарь: user_id, period_days, sessions, facts_created,
            audit_actions.
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
        """Распределение сессий по типам каналов.

        GROUP BY в БД возвращает пары channel_type -> количество сессий.
        Нужно для понимания нагрузки по каналам (MAX/Telegram/VK) и
        планирования ёмкости. Ключ channel_type — строка из модели сессии.

        Returns:
            Словарь {channel_type: количество сессий}.
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
        """Распределение активных фактов по категориям.

        Считаем только is_active факты: неактивные (удалённые/просроченные)
        не должны влиять на статистику памяти. Агрегация в БД — без
        выгрузки самих фактов, содержимое которых может быть персональным
        (152-ФЗ).

        Returns:
            Словарь {категория: количество фактов}.
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
        """Количество аудит-событий по дням за период.

        func.date обрезает timestamp до даты, группировка идёт по дню —
        получаем временной ряд для графика активности. Полезно как для
        продуктовой аналитики, так и для мониторинга безопасности
        (аномальные всплески операций).

        Args:
            days: Глубина периода в днях (по умолчанию 7).

        Returns:
            Список словарей {date, count} в хронологическом порядке.
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
        """Часовая активность аудит-событий.

        func.extract("hour") группирует события по часу суток (0-23).
        Используется для планирования нагрузки и проверки, когда система
        реально используется — часы с пиками.

        Returns:
            Список словарей {hour, count}, упорядоченный по часу.
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

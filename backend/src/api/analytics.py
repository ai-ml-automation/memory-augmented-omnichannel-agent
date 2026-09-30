"""
Роутер аналитики: эндпоинты статистики дашборда и отчётов.

Бизнес-контекст: аналитика нужна оператору для контроля работы системы,
однако 152-ФЗ запрещает выгружать сырые персональные данные — поэтому все
запросы делегируются `AnalyticsService`, который считает ТОЛЬКО агрегаты
(COUNT по группам) прямо в БД, без чтения содержимого фактов и аудита.

Ключевое решение: ответы формируются pydantic-схемами (DashboardStats,
UserActivity, TimelineEntry, HourlyEntry) — контракт ответа зафиксирован
и не зависит от внутренней структуры сервиса.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class DashboardStats(BaseModel):
    """
    Сводная статистика дашборда оператора.

    Все поля — счётчики-агрегаты: users (всего пользователей),
    active_sessions (активные сессии), total_facts (всего фактов памяти),
    active_consents (действующие согласия), audit_today (аудит-записей за сутки).

    Почему так: дашборд показывает тренды, а не персональные данные —
    согласуется с 152-ФЗ (см. `AnalyticsService.get_dashboard_stats`).
    """
    users: int
    active_sessions: int
    total_facts: int
    active_consents: int
    audit_today: int


class UserActivity(BaseModel):
    """
    Активность конкретного пользователя за период.

    Содержит только агрегированные счётчики (sessions, facts_created,
    audit_actions) — без самих данных сессий и фактов: оператор видит
    статистику, не раскрывая содержимое памяти клиента.

    user_id приводится к строке, чтобы не зависеть от формата UUID на клиенте.
    """
    user_id: str
    period_days: int
    sessions: int
    facts_created: int
    audit_actions: int


class TimelineEntry(BaseModel):
    """
    Точка временного ряда аудита: дата и число событий.

    Используется для графика динамики аудита — ответа на вопрос
    «когда система работала активнее всего» без выгрузки самих записей.
    """
    date: str
    count: int


class HourlyEntry(BaseModel):
    """
    Точка распределения нагрузки по часам суток.

    Показывает, в какие часы система обрабатывает пик сообщений, — это
    основа для планирования масштабирования воркеров Celery.
    """
    hour: int
    count: int


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """
    Сводная статистика для главного экрана оператора.

    Данные считаются сервисом как COUNT-агрегаты в БД — без выгрузки
    сырых записей, что соответствует 152-ФЗ (см. `AnalyticsService`).

    Returns:
        DashboardStats: счётчики пользователей, сессий, фактов, согласий и аудита
    """
    service = AnalyticsService(db)
    stats = await service.get_dashboard_stats()

    return DashboardStats(**stats)


@router.get("/users/{user_id}/activity", response_model=UserActivity)
async def get_user_activity(
    user_id: uuid.UUID,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
) -> UserActivity:
    """
    Активность пользователя за период (агрегаты, не данные).

    Оператору нужен ответ «активен ли клиент» без раскрытия содержимого
    его переписок и фактов памяти — только счётчики (см. `AnalyticsService`).

    Args:
        user_id: идентификатор пользователя
        days: длина анализируемого периода, до 365 дней (Query-ограничение)

    Returns:
        UserActivity: счётчики сессий, созданных фактов и аудит-действий
    """
    service = AnalyticsService(db)
    stats = await service.get_user_activity(user_id, days)

    return UserActivity(**stats)


@router.get("/channels")
async def get_channel_distribution(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Распределение сообщений по каналам (TG/VK/MAX).

    Показывает, каким каналом чаще пользуются клиенты, — основа для
    решений о развитии омниканального шлюза.

    Returns:
        dict: channel_type → число сообщений (COUNT-агрегат в БД)
    """
    service = AnalyticsService(db)
    return await service.get_channel_distribution()


@router.get("/facts/categories")
async def get_fact_categories(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Распределение фактов памяти по категориям.

    Агрегат по категориям показывает тематику запоминаемой информации
    без раскрытия самих фактов (152-ФЗ: статистика ≠ персональные данные).

    Returns:
        dict: категория → число фактов
    """
    service = AnalyticsService(db)
    return await service.get_fact_categories()


@router.get("/audit/timeline", response_model=list[TimelineEntry])
async def get_audit_timeline(
    days: int = Query(default=7, le=90),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEntry]:
    """
    Временной ряд числа аудит-записей по дням.

    Ответ на вопрос «как менялась активность системы» — только COUNT
    по дням, сами аудит-записи не выгружаются (неизменяемый след,
    см. `AuditService`).

    Args:
        days: глубина периода в днях, до 90 (Query-ограничение)

    Returns:
        list[TimelineEntry]: дата → число событий
    """
    service = AnalyticsService(db)
    timeline = await service.get_audit_timeline(days)

    return [TimelineEntry(**entry) for entry in timeline]


@router.get("/audit/peak-hours", response_model=list[HourlyEntry])
async def get_peak_hours(
    db: AsyncSession = Depends(get_db),
) -> list[HourlyEntry]:
    """
    Распределение активности по часам суток.

    Группировка COUNT по часу позволяет увидеть пиковые часы и спланировать
    масштабирование воркеров Celery под реальную нагрузку.

    Returns:
        list[HourlyEntry]: час → число событий
    """
    service = AnalyticsService(db)
    hours = await service.get_peak_hours()

    return [HourlyEntry(**entry) for entry in hours]

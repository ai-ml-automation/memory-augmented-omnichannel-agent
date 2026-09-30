"""
Analytics Router
API endpoints for analytics and reporting
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
    """Dashboard statistics schema."""
    users: int
    active_sessions: int
    total_facts: int
    active_consents: int
    audit_today: int


class UserActivity(BaseModel):
    """User activity schema."""
    user_id: str
    period_days: int
    sessions: int
    facts_created: int
    audit_actions: int


class TimelineEntry(BaseModel):
    """Timeline entry schema."""
    date: str
    count: int


class HourlyEntry(BaseModel):
    """Hourly entry schema."""
    hour: int
    count: int


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """
    Get dashboard statistics.

    Returns:
        Dashboard stats
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
    Get user activity stats.

    Args:
        user_id: User identifier
        days: Analysis period

    Returns:
        User activity stats
    """
    service = AnalyticsService(db)
    stats = await service.get_user_activity(user_id, days)

    return UserActivity(**stats)


@router.get("/channels")
async def get_channel_distribution(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Get channel usage distribution.

    Returns:
        Channel distribution
    """
    service = AnalyticsService(db)
    return await service.get_channel_distribution()


@router.get("/facts/categories")
async def get_fact_categories(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Get fact category distribution.

    Returns:
        Category distribution
    """
    service = AnalyticsService(db)
    return await service.get_fact_categories()


@router.get("/audit/timeline", response_model=list[TimelineEntry])
async def get_audit_timeline(
    days: int = Query(default=7, le=90),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEntry]:
    """
    Get audit log timeline.

    Args:
        days: Number of days

    Returns:
        Timeline data
    """
    service = AnalyticsService(db)
    timeline = await service.get_audit_timeline(days)

    return [TimelineEntry(**entry) for entry in timeline]


@router.get("/audit/peak-hours", response_model=list[HourlyEntry])
async def get_peak_hours(
    db: AsyncSession = Depends(get_db),
) -> list[HourlyEntry]:
    """
    Get peak activity hours.

    Returns:
        Hourly distribution
    """
    service = AnalyticsService(db)
    hours = await service.get_peak_hours()

    return [HourlyEntry(**entry) for entry in hours]

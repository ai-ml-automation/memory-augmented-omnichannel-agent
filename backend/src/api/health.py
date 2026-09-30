"""
Health-check роутер: общее состояние сервиса и его зависимостей.

Один эндпоинт для liveness/readiness: каждый бэкенд-компонент проверяется
отдельно и с таймаутом, чтобы одна упавшая зависимость (например, Redis)
не вешала проверку. Итог — агрегированный статус: healthy только когда все
компоненты в порядке, иначе degraded. По этому эндпоинту оркестратор
(Docker/K8s) решает, перезапускать ли контейнер.
"""

import logging
import httpx

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.database import get_db
from backend.src.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """
    Проверка здоровья всех зависимостей.

    PostgreSQL и Redis проверяются всегда — они обязательны. Qdrant и Neo4j
    проверяются только при ENABLE_MEMORY=true: если память сознательно
    выключена, недоступные вектора/граф не должны ронять статус сервиса.
    Каждая проверка в try/except с таймаутом, поэтому сбой одной зависимости
    не блокирует остальные. Итог: healthy (все ок) или degraded (есть сбои).

    Args:
        db: Сессия БД для проверки PostgreSQL.

    Returns:
        Общий статус и детали по каждому компоненту.
    """
    services: dict[str, str] = {}

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "healthy"
    except Exception as e:
        logger.warning("PostgreSQL health check failed: %s", e)
        services["postgres"] = f"unhealthy: {e}"

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, socket_timeout=2)
        await r.ping()
        await r.aclose()
        services["redis"] = "healthy"
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        services["redis"] = f"unhealthy: {e}"

    # Check Qdrant (only when memory features enabled)
    if settings.ENABLE_MEMORY:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.QDRANT_URL}/healthz")
                if resp.status_code == 200:
                    services["qdrant"] = "healthy"
                else:
                    services["qdrant"] = f"unhealthy: HTTP {resp.status_code}"
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)
            services["qdrant"] = f"unhealthy: {e}"

        # Check Neo4j
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            async with driver.session() as session:
                await session.run("RETURN 1")
            await driver.close()
            services["neo4j"] = "healthy"
        except Exception as e:
            logger.warning("Neo4j health check failed: %s", e)
            services["neo4j"] = f"unhealthy: {e}"

    overall_status = "healthy" if all(
        v == "healthy" for v in services.values()
    ) else "degraded"

    return HealthResponse(
        status=overall_status,
        services=services,
    )

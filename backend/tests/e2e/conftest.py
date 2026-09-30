"""
Конфигурация E2E-тестов: жизненный цикл приложения и БД.

Поддерживает SQLite (локально) и PostgreSQL (CI): при заданном
DATABASE_URL используется реальный PG для точного JSONB/UUID.
Тяжёлые опциональные зависимости (opentelemetry, prometheus и др.)
подменяются моками ДО импорта main — иначе тесты требуют их установки.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

# Mock heavy optional dependencies before importing main
for _sub in [
    "prometheus_fastapi_instrumentator",
    "pythonjsonlogger",
    "pythonjsonlogger.jsonlogger",
    "opentelemetry",
    "opentelemetry.trace",
    "opentelemetry.exporter",
    "opentelemetry.exporter.jaeger",
    "opentelemetry.exporter.jaeger.thrift",
    "opentelemetry.sdk",
    "opentelemetry.sdk.resources",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.fastapi",
]:
    sys.modules.setdefault(_sub, MagicMock())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.src.database import get_db
from backend.src.main import app
from backend.src.models import Base

# V.1: Use real PostgreSQL when DATABASE_URL is set, else SQLite
TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
IS_POSTGRESQL = TEST_DATABASE_URL.startswith("postgresql")


# SQLite type overrides (only needed when using SQLite backend)
if not IS_POSTGRESQL:
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID

    @compiles(PG_UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        """Компилирует PG UUID в VARCHAR(36) для SQLite-бэкенда.

        Без этого объявления create_all падает: SQLite не знает
        тип UUID; 36 символов совпадают с форматом канонического UUID.
        """
        return "VARCHAR(36)"

    @compiles(PG_JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        """Компилирует PG JSONB в TEXT для SQLite-бэкенда.

        SQLite хранит JSON как текст; сравнение/сериализация
        остаются на уровне SQLAlchemy-типов.
        """
        return "TEXT"


@pytest.fixture(scope="session")
def event_loop():
    """Возвращает единый event loop на всю e2e-сессию.

    Ловит конфликт циклов: pytest-asyncio требует стабильный loop
    между корутинными фикстурами и тестами.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Создаёт движок БД и разворачивает схему на время теста.

    Для SQLite включает PRAGMA foreign_keys=ON (иначе каскадные
    ограничения молча игнорируются); после теста — drop_all и dispose.
    """
    engine_kwargs: dict = {"echo": False}
    if IS_POSTGRESQL:
        engine_kwargs.update(
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    engine = create_async_engine(TEST_DATABASE_URL, **engine_kwargs)

    if not IS_POSTGRESQL:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Включает проверку внешних ключей на каждом соединении.

            По умолчанию SQLite отключает FK-ограничения; без PRAGMA
            тесты каскадного удаления (RTBF) молча проходят мимо багов.
            """
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Открывает изолированную сессию БД для каждого теста.

    Args:
        db_engine: движок из одноимённой фикстуры.

    Yields:
        AsyncSession: сессия с expire_on_commit=False; после теста
        выполняется rollback для сброса незакоммиченных изменений.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Возвращает HTTP-клиент к приложению с переопределённой БД.

    Args:
        db_engine: движок из одноимённой фикстуры.

    Yields:
        AsyncClient: клиент поверх ASGITransport; get_db подменён,
        чтобы запросы шли в тестовую БД, а не в продовую.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
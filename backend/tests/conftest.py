"""
Конфигурация pytest для юнит-тестов: async SQLite вместо PostgreSQL.

Почему SQLite: юнит-тесты не требуют реальной БД — in-memory база быстрее
и не зависит от окружения. PostgreSQL-типы JSONB/UUID компилируются
в TEXT/VARCHAR(36) на диалекте SQLite, чтобы Base.metadata.create_all
работал без изменений моделей.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID

from backend.src.models import Base

# Use SQLite for tests (in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---- Dialect-level type compilation overrides ----

@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    """
    Компиляция PostgreSQL UUID → VARCHAR(36) для SQLite.

    Нужна, чтобы модели с UUID-полями создавались в тестовой
    in-memory базе без подключения к PostgreSQL.
    """
    return "VARCHAR(36)"


@compiles(PG_JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    """
    Компиляция PostgreSQL JSONB → TEXT для SQLite.

    SQLite не хранит JSONB; TEXT достаточно для тестов, проверяющих
    сериализацию и чтение JSON-полей моделей.
    """
    return "TEXT"


# ---- Fixtures ----

@pytest.fixture(scope="session")
def event_loop():
    """
    Event loop на всю тестовую сессию.

    Позволяет pytest-asyncio выполнять async-тесты на одном loop
    (быстрее, чем пересоздание на каждый тест); закрывается в конце.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """
    Async-движок SQLite in-memory, создаётся на каждый тест.

    Почему function-scope: изоляция — каждый тест получает чистую схему
    (create_all → teardown drop_all), данные между тестами не «протекают».
    PRAGMA foreign_keys=ON включает проверку внешних ключей (каскады RTBF).
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable foreign keys for SQLite."""
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
    """
    Async-сессия SQLAlchemy для теста.

    Обёртка над db_engine: rollback в конце гарантирует, что
    незакоммиченные изменения не утекут в следующий тест.
    expire_on_commit=False оставляет объекты доступными после commit.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

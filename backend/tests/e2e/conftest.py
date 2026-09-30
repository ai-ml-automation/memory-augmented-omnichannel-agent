"""
E2E Test Configuration
Supports both SQLite (local) and PostgreSQL (CI) backends.
When DATABASE_URL env var is set, uses real PostgreSQL for accurate JSONB/UUID testing.
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
        return "VARCHAR(36)"

    @compiles(PG_JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "TEXT"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
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
    """Async HTTP client for E2E tests."""
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
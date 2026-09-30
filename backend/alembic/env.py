# backend/alembic/env.py
"""
Окружение Alembic для асинхронных миграций PostgreSQL.

target_metadata = метаданные ORM-моделей (backend.src.models) — база для автогенерации.
URL БД берётся из настроек приложения (get_settings), а не alembic.ini: единый
источник конфигурации исключает расхождение приложения и миграций.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.src.config import get_settings
from backend.src.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Get settings for async DSN
settings = get_settings()


def run_migrations_offline() -> None:
    """
    Офлайн-режим: генерация SQL без подключения к БД.

    Использует URL из настроек и literal_binds=True, поэтому скрипт выполним
    вручную (psql) — удобно для ревью и продакшен-применения без engine.
    """
    context.configure(
        url=settings.postgres_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """
    Общий прогон миграций для переданного соединения.

    Разделяет создание соединения (async-обёртка) и выполнение миграций,
    чтобы контекст Alembic настраивался один раз в одном месте.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Онлайн-режим: выполнение миграций через async-движок.

    NullPool: миграции не должны держать постоянный пул соединений — каждая
    операция получает соединение независимо, как при разовой утилите.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Входная точка онлайн-режима: запуск асинхронного прогона.

    asyncio.run используется потому, что Alembic синхронный, а движок приложения
    async — нужен временный event loop, который закрывается после миграций.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
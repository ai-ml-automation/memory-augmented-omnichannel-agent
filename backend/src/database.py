"""
Конфигурация базы данных: асинхронный движок и фабрика сессий SQLAlchemy.

Почему async (asyncpg): FastAPI-обработчики и Celery-задачи работают
в event loop, синхронные драйверы блокировали бы его. Используется
единый `engine` для всего приложения и `async_session_factory` для
получения сессий.

Ключевые решения:
- `pool_pre_ping=True` — проверка соединения перед выдачей из пула:
  переживает перезапуск PostgreSQL без «stale connection» ошибок;
- `expire_on_commit=False` — объекты остаются доступными после commit
  (нужно для сериализации в ответах API).
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.src.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.postgres_url,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Декларативная база всех SQLAlchemy-моделей приложения.

    Наследование от `DeclarativeBase` включает декларативный стиль:
    модели описываются классами, таблицы создаются по атрибутам
    (`__tablename__`, `Column`/`Mapped`). `metadata` собирается из
    подклассов и используется миграциями Alembic (`target_metadata`).
    """

    pass


async def get_db() -> AsyncSession:
    """
    Dependency FastAPI: асинхронная сессия БД на время запроса.
    Генератор с `yield` — коммит и закрытие здесь, а не в роутерах;
    при исключении — rollback и проброс ошибки.

    Yields:
        AsyncSession: сессия, готовая к запросам в обработчике
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Создание всех таблиц БД (используется при старте и в тестах).

    `create_all` идемпотентен: существующие таблицы не пересоздаются.
    В production таблицы создаёт Alembic (`alembic upgrade head`), этот
    вызов оставлен для локальной разработки и тестовых фикстур.

    Returns:
        None
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

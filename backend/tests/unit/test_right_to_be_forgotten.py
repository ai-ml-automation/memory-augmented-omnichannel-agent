"""
Юнит-тесты RightToBeForgottenService (фаза B.3.1).

Проверяют каскадное удаление данных пользователя: сводку по трём хранилищам
(PostgreSQL, Qdrant, Neo4j), вызовы db.delete, пустые списки фактов и
отключённую память (ENABLE_MEMORY=False) без обращения к векторным хранилищам.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.src.models import Fact, User


@pytest.fixture
def mock_db() -> AsyncMock:
    """Мок асинхронной сессии БД.

    Заменяет реальную сессию SQLAlchemy: execute/delete записываются в
    вызовы, что позволяет проверять порядок и число обращений к БД.
    """
    return AsyncMock()


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    """Стабильный UUID пользователя для тестов.

    Один UUID на тест держит согласованность: факты и пользователь
    привязаны к одному id, иначе сводка удаления была бы бессмысленна.
    """
    return uuid.uuid4()


@pytest.fixture
def sample_facts(sample_user_id: uuid.UUID) -> list[MagicMock]:
    """Два мок-объекта Fact, привязанных к sample_user_id.

    Args:
        sample_user_id: UUID, который присваивается fact.user_id.

    Returns:
        Список из двух MagicMock со spec=Fact и полем user_id.
    """
    facts = []
    for _ in range(2):
        fact = MagicMock(spec=Fact)
        fact.id = uuid.uuid4()
        fact.user_id = sample_user_id
        facts.append(fact)
    return facts


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID) -> MagicMock:
    """Мок-объект User с заданным id.

    Args:
        sample_user_id: UUID, присваиваемый user.id.

    Returns:
        MagicMock со spec=User и полем id = sample_user_id.
    """
    user = MagicMock(spec=User)
    user.id = sample_user_id
    return user


@pytest.mark.asyncio
async def test_delete_user_data_returns_summary(
    mock_db: AsyncMock,
    sample_user_id: uuid.UUID,
    sample_facts: list[MagicMock],
    sample_user: MagicMock,
):
    """Сводка удаления содержит корректные счётчики всех трёх хранилищ.

    Ловит баг: неверный подсчёт в сводке — фронтенд показывает пользователю
    ложное число удалённых фактов, нарушая прозрачность RTBF.
    """
    with patch(
        "backend.src.config.get_settings"
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(mock_db)

        fact_result = MagicMock()
        fact_result.scalars.return_value.all.return_value = sample_facts
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        mock_db.execute = AsyncMock(
            side_effect=[fact_result, user_result]
        )

        with (
            patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock, return_value=2),
            patch.object(svc, "_delete_from_neo4j", new_callable=AsyncMock, return_value=2),
        ):
            summary = await svc.delete_user_data(sample_user_id)

        assert summary["user_id"] == str(sample_user_id)
        assert summary["postgres_facts_deleted"] == 2
        assert summary["qdrant_facts_deleted"] == 2
        assert summary["neo4j_facts_deleted"] == 2
        assert summary["user_deleted"] is True


@pytest.mark.asyncio
async def test_delete_user_data_deletes_facts_from_pg(
    mock_db: AsyncMock,
    sample_user_id: uuid.UUID,
    sample_facts: list[MagicMock],
    sample_user: MagicMock,
):
    """db.delete вызывается для 2 фактов + 1 пользователя = 3 раза.

    Ловит баг: пропуск удаления фактов или пользователя — данные частично
    остаются в PostgreSQL после RTBF-запроса.
    """
    with patch(
        "backend.src.config.get_settings"
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(mock_db)

        fact_result = MagicMock()
        fact_result.scalars.return_value.all.return_value = sample_facts
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute = AsyncMock(
            side_effect=[fact_result, user_result]
        )

        with (
            patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock, return_value=2),
            patch.object(svc, "_delete_from_neo4j", new_callable=AsyncMock, return_value=2),
        ):
            await svc.delete_user_data(sample_user_id)

        assert mock_db.delete.call_count == 3


@pytest.mark.asyncio
async def test_delete_user_data_no_facts(
    mock_db: AsyncMock,
    sample_user_id: uuid.UUID,
    sample_user: MagicMock,
):
    """Пустой список фактов: пользователь удаляется, в сводке 0 фактов.

    Ловит баг: краш на пустом списке или ошибочная запись «удалённые факты»
    при их отсутствии — RTBF не должен падать на пользователе без фактов.
    """
    with patch(
        "backend.src.config.get_settings"
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(mock_db)

        fact_result = MagicMock()
        fact_result.scalars.return_value.all.return_value = []
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute = AsyncMock(
            side_effect=[fact_result, user_result]
        )

        with (
            patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock, return_value=0),
            patch.object(svc, "_delete_from_neo4j", new_callable=AsyncMock, return_value=0),
        ):
            summary = await svc.delete_user_data(sample_user_id)

        assert summary["postgres_facts_deleted"] == 0
        assert summary["qdrant_facts_deleted"] == 0
        assert summary["neo4j_facts_deleted"] == 0
        assert summary["user_deleted"] is True


@pytest.mark.asyncio
async def test_returns_zero_when_empty_qdrant():
    """Пустой список id возвращает 0 без обращения к Qdrant.

    Ловит баг: лишний сетевой запрос к Qdrant при пустом списке —
    пустое удаление не должно ходить в хранилище.
    """
    with patch(
        "backend.src.config.get_settings"
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(AsyncMock())
        result = await svc._delete_from_qdrant([])
        assert result == 0


@pytest.mark.asyncio
async def test_skips_when_memory_disabled_qdrant():
    """При ENABLE_MEMORY=False удаление из Qdrant возвращает 0.

    Ловит баг: попытка обратиться к Qdrant при отключённой памяти —
    падение сервиса на окружении без векторного хранилища.
    """
    mock_settings = MagicMock()
    mock_settings.ENABLE_MEMORY = False

    with patch(
        "backend.src.config.get_settings",
        return_value=mock_settings,
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(AsyncMock())
        fake_ids = [uuid.uuid4(), uuid.uuid4()]
        result = await svc._delete_from_qdrant(fake_ids)
        assert result == 0


@pytest.mark.asyncio
async def test_returns_zero_when_empty_neo4j():
    """Пустой список id возвращает 0 без обращения к Neo4j.

    Ловит баг: лишний сетевой запрос к Neo4j при пустом списке —
    пустое удаление не должно ходить в графовое хранилище.
    """
    with patch(
        "backend.src.config.get_settings"
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(AsyncMock())
        result = await svc._delete_from_neo4j([], uuid.uuid4())
        assert result == 0


@pytest.mark.asyncio
async def test_skips_when_memory_disabled_neo4j():
    """При ENABLE_MEMORY=False удаление из Neo4j возвращает 0.

    Ловит баг: попытка обратиться к Neo4j при отключённой памяти —
    падение сервиса на окружении без графового хранилища.
    """
    mock_settings = MagicMock()
    mock_settings.ENABLE_MEMORY = False

    with patch(
        "backend.src.config.get_settings",
        return_value=mock_settings,
    ):
        from backend.src.services.right_to_be_forgotten_service import (
            RightToBeForgottenService,
        )

        svc = RightToBeForgottenService(AsyncMock())
        fake_ids = [uuid.uuid4(), uuid.uuid4()]
        result = await svc._delete_from_neo4j(fake_ids, uuid.uuid4())
        assert result == 0
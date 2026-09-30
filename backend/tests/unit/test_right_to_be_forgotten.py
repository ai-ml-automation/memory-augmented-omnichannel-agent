"""
Unit Tests for RightToBeForgottenService
Tests cascade deletion across PostgreSQL, Qdrant, and Neo4j (B.3.1).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.src.models import Fact, User


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async database session."""
    return AsyncMock()


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    """Stable UUID for tests."""
    return uuid.uuid4()


@pytest.fixture
def sample_facts(sample_user_id: uuid.UUID) -> list[MagicMock]:
    """Two mock Fact objects."""
    facts = []
    for _ in range(2):
        fact = MagicMock(spec=Fact)
        fact.id = uuid.uuid4()
        fact.user_id = sample_user_id
        facts.append(fact)
    return facts


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID) -> MagicMock:
    """Mock User object."""
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
    """Summary dict has correct counts for all stores."""
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
    """db.delete is called for 2 facts + 1 user = 3 times."""
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
    """Empty facts list - user still deleted, 0 facts in summary."""
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
    """Empty fact_ids list returns 0 without touching Qdrant."""
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
    """ENABLE_MEMORY=False causes Qdrant deletion to return 0."""
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
    """Empty fact_ids list returns 0 without touching Neo4j."""
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
    """ENABLE_MEMORY=False causes Neo4j deletion to return 0."""
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
"""
Unit Tests for Mem0MemoryService (Phase C.1.1)

Pure-mock tests — no database required.
Verifies delegation to sub-services and graceful degradation
when vector store / graph indexing fails.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Patch targets (match import names inside mem0_memory_service module)
# ---------------------------------------------------------------------------
_PATCH_FACT = "backend.src.services.mem0_memory_service.FactService"
_PATCH_VECTOR = "backend.src.services.mem0_memory_service.VectorStoreService"
_PATCH_GRAPH = "backend.src.services.mem0_memory_service.GraphService"
_PATCH_RTBF = "backend.src.services.mem0_memory_service.RightToBeForgottenService"
_PATCH_SEARCH = "backend.src.services.mem0_memory_service.MemorySearchService"


def _make_svc():
    """Create Mem0MemoryService with all internal services mocked."""
    mock_db = MagicMock()

    with patch(_PATCH_FACT) as FactCls, \
         patch(_PATCH_VECTOR) as VectorCls, \
         patch(_PATCH_GRAPH) as GraphCls, \
         patch(_PATCH_RTBF) as RtbCls, \
         patch(_PATCH_SEARCH) as SearchCls:

        from backend.src.services.mem0_memory_service import Mem0MemoryService

        svc = Mem0MemoryService(mock_db)
        # Expose mocks for assertions
        svc._fact_svc = FactCls.return_value
        svc._vector_svc = VectorCls.return_value
        svc._graph_svc = GraphCls.return_value
        svc._rtbf_svc = RtbCls.return_value
        svc._search_svc = SearchCls.return_value

        return svc


# ---------------------------------------------------------------------------
# store_fact tests
# ---------------------------------------------------------------------------


class TestStoreFact:
    """Tests for Mem0MemoryService.store_fact."""

    @pytest.mark.asyncio
    async def test_store_fact_delegates_to_fact_service(self):
        """store_fact calls FactService.store_fact with correct args."""
        svc = _make_svc()
        fact_id = uuid.uuid4()
        mock_fact = MagicMock()
        mock_fact.id = fact_id
        svc._fact_svc.store_fact = AsyncMock(return_value=mock_fact)

        uid = uuid.uuid4()
        result = await svc.store_fact(
            user_id=uid,
            fact_type="preference",
            value="Likes dark mode",
            channel="TG",
            weight=0.8,
        )

        svc._fact_svc.store_fact.assert_awaited_once_with(
            user_id=uid,
            fact_type="preference",
            value="Likes dark mode",
            channel="TG",
            weight=0.8,
        )
        assert result is mock_fact

    @pytest.mark.asyncio
    async def test_store_fact_indexes_in_vector_store(self):
        """After FactService succeeds, VectorStoreService.index_fact is called."""
        svc = _make_svc()
        fact_id = uuid.uuid4()
        mock_fact = MagicMock()
        mock_fact.id = fact_id
        svc._fact_svc.store_fact = AsyncMock(return_value=mock_fact)
        svc._vector_svc.index_fact = AsyncMock()

        uid = uuid.uuid4()
        await svc.store_fact(
            user_id=uid,
            fact_type="intent",
            value="Wants to buy laptop",
            channel="VK",
        )

        svc._vector_svc.index_fact.assert_awaited_once_with(
            fact_id=fact_id,
            user_id=uid,
            content="Wants to buy laptop",
            metadata={"type": "intent", "channel": "VK"},
        )

    @pytest.mark.asyncio
    async def test_store_fact_indexes_in_graph(self):
        """After FactService succeeds, GraphService.create_fact_node is called."""
        svc = _make_svc()
        fact_id = uuid.uuid4()
        mock_fact = MagicMock()
        mock_fact.id = fact_id
        svc._fact_svc.store_fact = AsyncMock(return_value=mock_fact)
        svc._graph_svc.create_fact_node = AsyncMock()

        uid = uuid.uuid4()
        await svc.store_fact(
            user_id=uid,
            fact_type="personal_info",
            value="Lives in Moscow",
            channel="MAX",
        )

        svc._graph_svc.create_fact_node.assert_awaited_once_with(
            fact_id=fact_id,
            user_id=uid,
            category="personal_info",
            content_summary="Lives in Moscow",
            metadata={"channel": "MAX"},
            consent_verified=True,
        )

    @pytest.mark.asyncio
    async def test_store_fact_vector_failure_is_swallowed(self):
        """VectorStoreService raising does NOT prevent store_fact from returning."""
        svc = _make_svc()
        fact_id = uuid.uuid4()
        mock_fact = MagicMock()
        mock_fact.id = fact_id
        svc._fact_svc.store_fact = AsyncMock(return_value=mock_fact)
        svc._vector_svc.index_fact = AsyncMock(side_effect=RuntimeError("Qdrant down"))
        svc._graph_svc.create_fact_node = AsyncMock()

        uid = uuid.uuid4()
        result = await svc.store_fact(
            user_id=uid,
            fact_type="intent",
            value="Test value",
            channel="TG",
        )

        assert result is mock_fact
        svc._graph_svc.create_fact_node.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_fact_graph_failure_is_swallowed(self):
        """GraphService raising does NOT prevent store_fact from returning."""
        svc = _make_svc()
        fact_id = uuid.uuid4()
        mock_fact = MagicMock()
        mock_fact.id = fact_id
        svc._fact_svc.store_fact = AsyncMock(return_value=mock_fact)
        svc._vector_svc.index_fact = AsyncMock()
        svc._graph_svc.create_fact_node = AsyncMock(
            side_effect=RuntimeError("Neo4j down")
        )

        uid = uuid.uuid4()
        result = await svc.store_fact(
            user_id=uid,
            fact_type="complaint",
            value="Slow service",
            channel="VOICE",
        )

        assert result is mock_fact
        svc._vector_svc.index_fact.assert_awaited_once()


# ---------------------------------------------------------------------------
# retrieve_facts
# ---------------------------------------------------------------------------


class TestRetrieveFacts:
    """Tests for Mem0MemoryService.retrieve_facts."""

    @pytest.mark.asyncio
    async def test_retrieve_facts_delegates(self):
        """retrieve_facts delegates to FactService.get_facts."""
        svc = _make_svc()
        expected = [MagicMock(), MagicMock()]
        svc._fact_svc.get_facts = AsyncMock(return_value=expected)

        uid = uuid.uuid4()
        result = await svc.retrieve_facts(uid, query="anything", limit=5)

        svc._fact_svc.get_facts.assert_awaited_once_with(user_id=uid, limit=5)
        assert result == expected


# ---------------------------------------------------------------------------
# search_facts
# ---------------------------------------------------------------------------


class TestSearchFacts:
    """Tests for Mem0MemoryService.search_facts."""

    @pytest.mark.asyncio
    async def test_search_facts_delegates(self):
        """search_facts delegates to FactService.search_facts."""
        svc = _make_svc()
        expected = [MagicMock()]
        svc._fact_svc.search_facts = AsyncMock(return_value=expected)

        uid = uuid.uuid4()
        result = await svc.search_facts(uid, query="laptop", limit=3)

        svc._fact_svc.search_facts.assert_awaited_once_with(
            user_id=uid, query="laptop", limit=3
        )
        assert result == expected


# ---------------------------------------------------------------------------
# delete_user_data
# ---------------------------------------------------------------------------


class TestDeleteUserData:
    """Tests for Mem0MemoryService.delete_user_data."""

    @pytest.mark.asyncio
    async def test_delete_user_data_delegates(self):
        """delete_user_data delegates to RightToBeForgottenService."""
        svc = _make_svc()
        rtbf_result = {"deleted_facts": 5, "deleted_consent": True}
        svc._rtbf_svc.delete_user_data = AsyncMock(return_value=rtbf_result)

        uid = uuid.uuid4()
        result = await svc.delete_user_data(uid)

        svc._rtbf_svc.delete_user_data.assert_awaited_once_with(user_id=uid)
        # Result is normalised to dict
        assert result == {"deleted_facts": 5, "deleted_consent": True}


# ---------------------------------------------------------------------------
# get_memory_context
# ---------------------------------------------------------------------------


class TestGetMemoryContext:
    """Tests for Mem0MemoryService.get_memory_context."""

    @pytest.mark.asyncio
    async def test_get_memory_context_delegates(self):
        """get_memory_context delegates to MemorySearchService."""
        svc = _make_svc()
        svc._search_svc.get_memory_context = AsyncMock(
            return_value="User prefers dark mode."
        )

        uid = uuid.uuid4()
        result = await svc.get_memory_context(
            uid, current_message="What do I like?", max_facts=3
        )

        svc._search_svc.get_memory_context.assert_awaited_once_with(
            user_id=uid,
            current_message="What do I like?",
            max_facts=3,
        )
        assert result == "User prefers dark mode."

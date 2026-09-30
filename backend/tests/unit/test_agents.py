"""
Unit Tests for Phase D.2 LangGraph Agents

Covers: FactExtractorAgent, MemoryManagerAgent,
        ResponseGeneratorAgent, ConflictResolverAgent.
Pure-mock tests — no database or external services required.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =========================================================================
# FactExtractorAgent
# =========================================================================

_PATCH_FE_LLM = "backend.src.agents.fact_extractor.LLMService"
_PATCH_FE_SETTINGS = "backend.src.agents.fact_extractor.settings"
_PATCH_FE_ANON = "backend.src.utils.presidio_anonymizer.anonymize_text"


class TestFactExtractorAgent:
    """Tests for FactExtractorAgent pipeline (D.2.2)."""

    @pytest.mark.asyncio
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_calls_llm(self, mock_llm_cls, mock_settings):
        """extract() calls LLM, parses JSON, and returns facts."""
        from backend.src.agents.fact_extractor import FactExtractorAgent

        mock_settings.ENABLE_LLM = True

        facts_payload = [
            {"type": "preference", "content": "likes coffee", "weight": 0.8},
        ]
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=json.dumps(facts_payload)
        )
        mock_llm_cls.return_value = mock_llm

        agent = FactExtractorAgent()
        result = await agent.extract("I like coffee")

        assert len(result) == 1
        assert result[0]["type"] == "preference"
        assert result[0]["content"] == "likes coffee"
        mock_llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_filters_emotions(self, mock_llm_cls, mock_settings):
        """Facts with type='emotion' are filtered out."""
        from backend.src.agents.fact_extractor import FactExtractorAgent

        mock_settings.ENABLE_LLM = True

        facts_payload = [
            {"type": "preference", "content": "likes tea", "weight": 0.7},
            {"type": "emotion", "content": "feels happy", "weight": 0.3},
            {"type": "fact", "content": "works at Yandex", "weight": 0.9},
        ]
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=json.dumps(facts_payload)
        )
        mock_llm_cls.return_value = mock_llm

        agent = FactExtractorAgent()
        result = await agent.extract("I feel happy and I like tea")

        assert len(result) == 2
        types = [f["type"] for f in result]
        assert "emotion" not in types

    @pytest.mark.asyncio
    @patch(_PATCH_FE_ANON)
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_anonymizes_pii(
        self, mock_llm_cls, mock_settings, mock_anon
    ):
        """PII in fact content is anonymized via Presidio."""
        from backend.src.agents.fact_extractor import FactExtractorAgent

        mock_settings.ENABLE_LLM = True

        facts_payload = [
            {"type": "fact", "content": "My name is John", "weight": 0.9},
        ]
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=json.dumps(facts_payload)
        )
        mock_llm_cls.return_value = mock_llm

        # Presidio replaces PII
        mock_anon.return_value = "My name is [PERSON]"

        agent = FactExtractorAgent()
        result = await agent.extract("My name is John and I work here")

        assert result[0]["content"] == "My name is [PERSON]"
        assert result[0]["pii_masked"] is True
        mock_anon.assert_called_once_with("My name is John")

    @pytest.mark.asyncio
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_llm_disabled_returns_empty(
        self, mock_llm_cls, mock_settings
    ):
        """When ENABLE_LLM=False, extraction returns empty list."""
        from backend.src.agents.fact_extractor import FactExtractorAgent

        mock_settings.ENABLE_LLM = False
        mock_llm_cls.return_value = AsyncMock()

        agent = FactExtractorAgent()
        result = await agent.extract("I like coffee")

        assert result == []

    @pytest.mark.asyncio
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_invalid_json_returns_empty(
        self, mock_llm_cls, mock_settings
    ):
        """Non-JSON LLM response produces empty list."""
        from backend.src.agents.fact_extractor import FactExtractorAgent

        mock_settings.ENABLE_LLM = True

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value="This is not valid JSON at all"
        )
        mock_llm_cls.return_value = mock_llm

        agent = FactExtractorAgent()
        result = await agent.extract("Hello world")

        assert result == []


# =========================================================================
# MemoryManagerAgent
# =========================================================================


class TestMemoryManagerAgent:
    """Tests for MemoryManagerAgent store/retrieve (D.2.3)."""

    @pytest.mark.asyncio
    async def test_store_facts_delegates_to_service(self):
        """store_facts() delegates to MemoryService.store_fact."""
        from backend.src.agents.memory_manager import MemoryManagerAgent

        user_id = uuid.uuid4()
        fact_id = uuid.uuid4()

        mock_fact = MagicMock()
        mock_fact.id = fact_id

        mock_service = AsyncMock()
        mock_service.store_fact = AsyncMock(return_value=mock_fact)

        agent = MemoryManagerAgent(memory_service=mock_service)
        facts = [{"type": "preference", "content": "likes coffee", "weight": 0.8}]
        results = await agent.store_facts(user_id, facts, channel="text")

        assert len(results) == 1
        assert results[0]["id"] == str(fact_id)
        assert results[0]["status"] == "stored"
        mock_service.store_fact.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_facts_handles_service_failure(self):
        """When MemoryService raises, error is recorded gracefully."""
        from backend.src.agents.memory_manager import MemoryManagerAgent

        user_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.store_fact = AsyncMock(
            side_effect=RuntimeError("DB unreachable")
        )

        agent = MemoryManagerAgent(memory_service=mock_service)
        facts = [{"type": "fact", "content": "works at Yandex", "weight": 0.9}]
        results = await agent.store_facts(user_id, facts, channel="text")

        assert len(results) == 1
        assert "error" in results[0]

    @pytest.mark.asyncio
    async def test_retrieve_facts_delegates_to_search(self):
        """retrieve_facts delegates to MemoryService.search_facts."""
        from backend.src.agents.memory_manager import MemoryManagerAgent

        user_id = uuid.uuid4()

        mock_fact = MagicMock()
        mock_fact.id = uuid.uuid4()
        mock_fact.type = "preference"
        mock_fact.value = "likes coffee"
        mock_fact.weight = 0.8

        mock_service = AsyncMock()
        mock_service.search_facts = AsyncMock(return_value=[mock_fact])

        agent = MemoryManagerAgent(memory_service=mock_service)
        results = await agent.retrieve_facts(user_id, "coffee")

        assert len(results) == 1
        assert results[0]["content"] == "likes coffee"
        assert results[0]["source"] == "memory_service"
        mock_service.search_facts.assert_awaited_once_with(user_id, "coffee", 10)


# =========================================================================
# ResponseGeneratorAgent
# =========================================================================

_PATCH_RG_LLM = "backend.src.agents.response_generator.LLMService"
_PATCH_RG_MEMORY = "backend.src.agents.response_generator.MemorySearchService"
_PATCH_RG_SETTINGS = "backend.src.agents.response_generator.settings"


class TestResponseGeneratorAgent:
    """Tests for ResponseGeneratorAgent (D.2.4)."""

    @pytest.mark.asyncio
    @patch(_PATCH_RG_SETTINGS)
    @patch(_PATCH_RG_MEMORY)
    @patch(_PATCH_RG_LLM)
    async def test_generate_calls_llm(
        self, mock_llm_cls, mock_mem_cls, mock_settings
    ):
        """generate() calls LLM and returns response with context_used=False."""
        from backend.src.agents.response_generator import ResponseGeneratorAgent

        mock_settings.ENABLE_LLM = True

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="Hello! How can I help?")
        mock_llm_cls.return_value = mock_llm

        mock_mem = mock_mem_cls.return_value
        mock_mem.get_memory_context = AsyncMock(return_value="")

        agent = ResponseGeneratorAgent(db=AsyncMock())
        result = await agent.generate(
            user_id=uuid.uuid4(),
            message="Hi there!",
        )

        assert result["response"] == "Hello! How can I help?"
        assert result["context_used"] is False
        assert result["fallback"] is False

    @pytest.mark.asyncio
    @patch(_PATCH_RG_SETTINGS)
    @patch(_PATCH_RG_MEMORY)
    @patch(_PATCH_RG_LLM)
    async def test_generate_with_memory_context(
        self, mock_llm_cls, mock_mem_cls, mock_settings
    ):
        """When memory context exists, context_used is True."""
        from backend.src.agents.response_generator import ResponseGeneratorAgent

        mock_settings.ENABLE_LLM = True

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value="I see you like coffee!"
        )
        mock_llm_cls.return_value = mock_llm

        mock_mem = mock_mem_cls.return_value
        mock_mem.get_memory_context = AsyncMock(
            return_value="Relevant info:\n1. likes coffee"
        )

        agent = ResponseGeneratorAgent(db=AsyncMock())
        result = await agent.generate(
            user_id=uuid.uuid4(),
            message="What do I like?",
        )

        assert result["response"] == "I see you like coffee!"
        assert result["context_used"] is True
        assert result["fallback"] is False

    @pytest.mark.asyncio
    @patch(_PATCH_RG_SETTINGS)
    @patch(_PATCH_RG_MEMORY)
    @patch(_PATCH_RG_LLM)
    async def test_generate_llm_disabled_returns_fallback(
        self, mock_llm_cls, mock_mem_cls, mock_settings
    ):
        """When ENABLE_LLM=False, fallback response is returned."""
        from backend.src.agents.response_generator import (
            FALLBACK_RESPONSE,
            ResponseGeneratorAgent,
        )

        mock_settings.ENABLE_LLM = False

        mock_llm = AsyncMock()
        mock_llm_cls.return_value = mock_llm

        mock_mem = mock_mem_cls.return_value
        mock_mem.get_memory_context = AsyncMock(return_value="")

        agent = ResponseGeneratorAgent(db=AsyncMock())
        result = await agent.generate(
            user_id=uuid.uuid4(),
            message="Hello",
        )

        assert result["response"] == FALLBACK_RESPONSE
        assert result["fallback"] is True
        assert result["context_used"] is False


# =========================================================================
# ConflictResolverAgent
# =========================================================================


class TestConflictResolverAgent:
    """Tests for ConflictResolverAgent resolution logic (D.2.5)."""

    def test_resolve_later_overrides_earlier(self):
        """New fact with timestamp > existing by >5 min → override."""
        from backend.src.agents.conflict_resolver import ConflictResolverAgent

        resolver = ConflictResolverAgent()
        existing = {
            "content": "works at Yandex",
            "created_at": "2026-07-14T10:00:00",
            "weight": 0.5,
        }
        new = {
            "content": "works at Sber",
            "created_at": "2026-07-14T12:00:00",
            "weight": 0.8,
        }
        result = resolver.resolve(existing, new)

        assert result["action"] == "override"
        assert result["fact"]["content"] == "works at Sber"
        assert result["requires_hitl"] is False

    def test_resolve_keep_existing_if_older(self):
        """Existing fact is newer than new → keep existing."""
        from backend.src.agents.conflict_resolver import ConflictResolverAgent

        resolver = ConflictResolverAgent()
        existing = {
            "content": "works at Sber",
            "created_at": "2026-07-14T12:00:00",
            "weight": 0.9,
        }
        new = {
            "content": "works at Yandex",
            "created_at": "2026-07-14T10:00:00",
            "weight": 0.5,
        }
        result = resolver.resolve(existing, new)

        assert result["action"] == "keep_existing"
        assert result["fact"]["content"] == "works at Sber"
        assert result["requires_hitl"] is False

    def test_resolve_hitl_for_rapid_conflict(self):
        """Timestamps within 5 minutes → requires_hitl=True."""
        from backend.src.agents.conflict_resolver import ConflictResolverAgent

        resolver = ConflictResolverAgent()
        existing = {
            "content": "likes tea",
            "created_at": "2026-07-14T10:00:00",
            "weight": 0.7,
        }
        new = {
            "content": "likes coffee",
            "created_at": "2026-07-14T10:03:00",
            "weight": 0.8,
        }
        result = resolver.resolve(existing, new)

        assert result["requires_hitl"] is True
        assert result["action"] == "flag_for_review"

    def test_resolve_by_weight_when_no_timestamps(self):
        """No datetime strings → fall back to weight comparison."""
        from backend.src.agents.conflict_resolver import ConflictResolverAgent

        resolver = ConflictResolverAgent()
        existing = {
            "content": "likes tea",
            "weight": 0.4,
        }
        new = {
            "content": "likes coffee",
            "weight": 0.9,
        }
        result = resolver.resolve(existing, new)

        assert result["action"] == "override"
        assert result["fact"]["content"] == "likes coffee"
        assert result["requires_hitl"] is False

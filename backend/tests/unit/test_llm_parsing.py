"""
V.4: Contract Tests for LLM Response Parsing
Tests resilience of FactExtractorAgent._extract_triplets to malformed LLM output.

These tests verify the parser handles:
- Markdown-wrapped JSON
- Extra text before/after JSON
- Invalid JSON
- Empty arrays
- Single object instead of array
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


# We need ENABLE_LLM=true for the agent to attempt extraction
@pytest.fixture(autouse=True)
def enable_llm():
    with patch("backend.src.agents.fact_extractor.settings") as mock:
        mock.ENABLE_LLM = True
        yield mock


@pytest.fixture
def agent():
    """Create a FactExtractorAgent with mocked LLM."""
    from backend.src.agents.fact_extractor import FactExtractorAgent

    instance = FactExtractorAgent()
    instance.llm = AsyncMock()
    return instance


class TestExtractTripletsMarkdownWrapper:
    """LLM wraps JSON in ```json ... ```."""

    @pytest.mark.asyncio
    async def test_markdown_json_wrapper(self, agent):
        """Standard markdown code fence wrapping."""
        llm_response = '```json\n[{"type": "fact", "content": "test content"}]\n```'
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("user message")

        assert len(result) == 1
        assert result[0]["type"] == "fact"
        assert result[0]["content"] == "test content"

    @pytest.mark.asyncio
    async def test_markdown_wrapper_without_language(self, agent):
        """Code fence without 'json' language tag."""
        llm_response = '```\n[{"type": "preference", "content": "likes coffee"}]\n```'
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("message")

        assert len(result) == 1
        assert result[0]["content"] == "likes coffee"


class TestExtractTripletsExtraText:
    """LLM returns explanatory text before/after JSON."""

    @pytest.mark.asyncio
    async def test_text_before_json(self, agent):
        """Explanation text before JSON array."""
        llm_response = (
            "Here are the extracted facts:\n"
            '[{"type": "fact", "content": "works at Yandex"}]'
        )
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("I work at Yandex")

        assert len(result) == 1
        assert result[0]["content"] == "works at Yandex"

    @pytest.mark.asyncio
    async def test_text_after_json(self, agent):
        """Explanation text after JSON array."""
        llm_response = (
            '[{"type": "preference", "content": "likes tea"}]\n'
            "Note: This was the only fact I found."
        )
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("I like tea")

        assert len(result) == 1
        assert result[0]["content"] == "likes tea"

    @pytest.mark.asyncio
    async def test_text_both_sides(self, agent):
        """Explanation on both sides of JSON."""
        llm_response = (
            "After analyzing the message:\n"
            '[{"type": "fact", "content": "has a cat named Barsik"}]\n'
            "I found one fact."
        )
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("My cat Barsik is fluffy")

        assert len(result) == 1
        assert "Barsik" in result[0]["content"]


class TestExtractTripletsInvalidJson:
    """LLM returns completely invalid JSON."""

    @pytest.mark.asyncio
    async def test_plain_text_response(self, agent):
        """LLM returns plain text instead of JSON."""
        agent.llm.generate = AsyncMock(return_value="This is not JSON at all")

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_partial_json(self, agent):
        """LLM returns incomplete JSON."""
        agent.llm.generate = AsyncMock(return_value='[{"type": "fact", "content":')

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_llm_returns_none_like(self, agent):
        """LLM returns empty string."""
        agent.llm.generate = AsyncMock(return_value="")

        result = await agent._extract_triplets("test")

        assert result == []


class TestExtractTripletsEdgeCases:
    """Edge cases: empty arrays, single objects, nested structures."""

    @pytest.mark.asyncio
    async def test_empty_array(self, agent):
        """LLM returns empty JSON array (no facts found)."""
        agent.llm.generate = AsyncMock(return_value="[]")

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_single_object_wrapped(self, agent):
        """LLM returns single object instead of array."""
        agent.llm.generate = AsyncMock(
            return_value='{"type": "fact", "content": "single fact"}'
        )

        result = await agent._extract_triplets("test")

        # _extract_triplets wraps single objects in a list
        assert len(result) == 1
        assert result[0]["content"] == "single fact"

    @pytest.mark.asyncio
    async def test_multiple_facts(self, agent):
        """LLM returns multiple facts in array."""
        facts = [
            {"type": "preference", "content": "likes coffee", "weight": 0.8},
            {"type": "fact", "content": "works at Yandex", "weight": 0.9},
        ]
        agent.llm.generate = AsyncMock(return_value=json.dumps(facts))

        result = await agent._extract_triplets("I work at Yandex and love coffee")

        assert len(result) == 2
        assert result[0]["type"] == "preference"
        assert result[1]["type"] == "fact"


class TestExtractTripletsEmotionFilter:
    """Verify that emotion facts are filtered out after extraction."""

    @pytest.mark.asyncio
    async def test_emotions_filtered(self, agent):
        """Emotion-type facts should be removed by _filter_emotions."""
        facts = [
            {"type": "emotion", "content": "feels happy"},
            {"type": "fact", "content": "likes coffee"},
        ]
        agent.llm.generate = AsyncMock(return_value=json.dumps(facts))

        result = await agent.extract("I'm happy and I love coffee")

        # Only non-emotion facts remain
        assert len(result) == 1
        assert result[0]["type"] == "fact"
        assert result[0]["content"] == "likes coffee"

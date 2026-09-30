"""
Unit Tests for ChatService (Phase C.3.1)

Pure-mock tests — verifies the prompt→LLM→evaluate→store pipeline.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Patch targets (match import names inside chat_service module)
# ---------------------------------------------------------------------------
_PATCH_PROMPT = "backend.src.services.chat_service.PromptBuilder"
_PATCH_LLM = "backend.src.services.chat_service.LLMService"
_PATCH_EVAL = "backend.src.services.chat_service.ResponseEvaluator"
_PATCH_MEMORY = "backend.src.services.chat_service.Mem0MemoryService"


def _make_svc():
    """Create ChatService with all internal services mocked."""
    mock_db = MagicMock()

    with patch(_PATCH_PROMPT) as PromptCls, \
         patch(_PATCH_LLM) as LLMCls, \
         patch(_PATCH_EVAL) as EvalCls, \
         patch(_PATCH_MEMORY) as MemCls:

        from backend.src.services.chat_service import ChatService

        svc = ChatService(mock_db)
        svc.prompt_builder = PromptCls.return_value
        svc.llm_service = LLMCls.return_value
        svc.evaluator = EvalCls.return_value
        svc.memory = MemCls.return_value

        return svc


# ---------------------------------------------------------------------------
# send_message tests
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for ChatService.send_message."""

    @pytest.mark.asyncio
    async def test_send_message_builds_prompt_and_generates(self):
        """Full pipeline: build_prompt → LLM generate → evaluate."""
        svc = _make_svc()

        # build_prompt returns messages
        messages = [
            {"role": "system", "content": "You are a helper."},
            {"role": "user", "content": "Hello"},
        ]
        svc.prompt_builder.build_prompt = AsyncMock(return_value=messages)

        # LLM returns response
        svc.llm_service.generate = AsyncMock(return_value="Hi there!")

        # Evaluator: no facts to store
        svc.evaluator.evaluate = AsyncMock(
            return_value={"score": 0.9, "checks": {}, "warnings": []}
        )
        svc.evaluator.should_store_fact = AsyncMock(return_value=False)

        uid = uuid.uuid4()
        result = await svc.send_message(uid, "Hello", channel_type="TG")

        # Verify build_prompt was called
        svc.prompt_builder.build_prompt.assert_awaited_once_with(
            user_id=uid, message="Hello", channel_type="TG"
        )

        # Verify LLM was called with joined prompt
        svc.llm_service.generate.assert_awaited_once()
        call_kwargs = svc.llm_service.generate.call_args
        assert "system: You are a helper." in call_kwargs.kwargs["prompt"]
        assert "user: Hello" in call_kwargs.kwargs["prompt"]
        assert call_kwargs.kwargs["max_tokens"] == 1000
        assert call_kwargs.kwargs["temperature"] == 0.7

        # Verify evaluation
        svc.evaluator.evaluate.assert_awaited_once_with(
            response="Hi there!", context="Hello"
        )

        assert result["response"] == "Hi there!"
        assert result["evaluation"]["score"] == 0.9
        assert result["facts_stored"] == 0

    @pytest.mark.asyncio
    async def test_send_message_with_history(self):
        """When history is provided, build_prompt_with_history is used."""
        svc = _make_svc()

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        messages = [
            {"role": "system", "content": "Context"},
            {"role": "user", "content": "Follow up"},
        ]
        svc.prompt_builder.build_prompt_with_history = AsyncMock(
            return_value=messages
        )
        svc.llm_service.generate = AsyncMock(return_value="Sure!")
        svc.evaluator.evaluate = AsyncMock(return_value={"score": 0.8})
        svc.evaluator.should_store_fact = AsyncMock(return_value=False)

        uid = uuid.uuid4()
        result = await svc.send_message(
            uid, "Follow up", channel_type="VK", history=history
        )

        svc.prompt_builder.build_prompt_with_history.assert_awaited_once_with(
            user_id=uid,
            message="Follow up",
            history=history,
            channel_type="VK",
        )
        svc.prompt_builder.build_prompt.assert_not_called()
        assert result["response"] == "Sure!"

    @pytest.mark.asyncio
    async def test_send_message_stores_facts(self):
        """When should_store_fact is True, extracted facts are stored."""
        svc = _make_svc()

        svc.prompt_builder.build_prompt = AsyncMock(
            return_value=[{"role": "user", "content": "Test"}]
        )
        svc.llm_service.generate = AsyncMock(return_value="Noted!")
        svc.evaluator.evaluate = AsyncMock(return_value={"score": 0.5})
        svc.evaluator.should_store_fact = AsyncMock(return_value=True)

        extracted = [
            {"type": "intent", "content": "Buy laptop", "weight": 0.9},
            {"type": "preference", "content": "Prefers macOS", "weight": 0.7},
        ]
        svc.prompt_builder.extract_facts_from_response = MagicMock(
            return_value=extracted
        )
        svc.memory.store_fact = AsyncMock(return_value=MagicMock())

        uid = uuid.uuid4()
        result = await svc.send_message(uid, "I want a MacBook")

        assert result["facts_stored"] == 2
        assert svc.memory.store_fact.await_count == 2

        # Verify first fact
        first_call = svc.memory.store_fact.call_args_list[0]
        assert first_call.kwargs["user_id"] == uid
        assert first_call.kwargs["fact_type"] == "intent"
        assert first_call.kwargs["value"] == "Buy laptop"
        assert first_call.kwargs["channel"] == "text"
        assert first_call.kwargs["weight"] == 0.9

        # Verify second fact
        second_call = svc.memory.store_fact.call_args_list[1]
        assert second_call.kwargs["fact_type"] == "preference"
        assert second_call.kwargs["value"] == "Prefers macOS"

    @pytest.mark.asyncio
    async def test_send_message_llm_disabled_returns_placeholder(self):
        """LLM disabled (RuntimeError) returns a placeholder response."""
        svc = _make_svc()

        svc.prompt_builder.build_prompt = AsyncMock(
            return_value=[{"role": "user", "content": "Hi"}]
        )
        svc.llm_service.generate = AsyncMock(
            side_effect=RuntimeError("LLM disabled")
        )

        uid = uuid.uuid4()
        result = await svc.send_message(uid, "Hello")

        assert "временно отключен" in result["response"]
        assert result["facts_stored"] == 0
        assert result["evaluation"]["score"] == 1.0


# ---------------------------------------------------------------------------
# get_llm_info
# ---------------------------------------------------------------------------


class TestGetLlmInfo:
    """Tests for ChatService.get_llm_info."""

    def test_get_llm_info(self):
        """get_llm_info returns the provider info dict from LLMService."""
        svc = _make_svc()
        provider_info = {"provider": "yandexgpt", "model": "yandexgpt-lite"}
        svc.llm_service.get_provider_info = MagicMock(return_value=provider_info)

        result = svc.get_llm_info()

        svc.llm_service.get_provider_info.assert_called_once()
        assert result == provider_info

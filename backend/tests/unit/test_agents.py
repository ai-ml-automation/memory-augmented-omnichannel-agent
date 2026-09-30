"""
Unit Tests for Phase D.2 LangGraph Agents

Покрывают: FactExtractorAgent, MemoryManagerAgent,
ResponseGeneratorAgent, ConflictResolverAgent.
Pure-mock тесты — база данных и внешние сервисы не нужны.

Зачем эти тесты: агенты — умный слой поверх памяти. Тесты фиксируют
контракт каждого агента: извлечение фактов через LLM с фильтрацией
эмоций и анонимизацией PII, сохранение/поиск через MemoryService,
генерацию ответа с контекстом памяти и graceful degradation при
отключённом LLM, а также логику разрешения конфликтов фактов.
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
    """Группа тестов FactExtractorAgent: извлечение фактов через LLM (D.2.2).

    Покрывают вызов LLM с разбором JSON-ответа, фильтрацию эмоций,
    анонимизацию PII через Presidio и graceful degradation при
    выключенном LLM или невалидном JSON.
    """

    @pytest.mark.asyncio
    @patch(_PATCH_FE_SETTINGS)
    @patch(_PATCH_FE_LLM)
    async def test_extract_calls_llm(self, mock_llm_cls, mock_settings):
        """Ловит баг, если extract не вызывает LLM или не парсит ответ.

        LLM.generate вызывается один раз, JSON-ответ разбирается в список
        фактов, поля type/content сохраняются без искажений. Сломанный
        парсинг здесь обесценит весь конвейер извлечения фактов.
        """
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
        """Ловит баг, если эмоции попадают в хранимые факты.

        Факт с type="emotion" обязан отфильтроваться: из трёх ответов LLM
        остаются только preference и fact. Эмоции нестабильны во времени
        и засоряют память клиента ложными сведениями.
        """
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
        """PII в содержании факта анонимизируется через Presidio.

        Содержимое факта должно проходить через anonymize_text: имя "John"
        заменяется на "[PERSON]", а флаг pii_masked выставляется в True.
        Пропуск анонимизации сохранит персональные данные в открытом виде.
        """
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
        """Ловит баг, если при ENABLE_LLM=False extract не пуст.

        При выключенном LLM агент обязан вернуть пустой список, не трогая
        LLM-сервис. Извлечение без провайдера упало бы на сетевом вызове
        или вернуло бы мусор — пустой результат это штатное поведение.
        """
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
        """Ловит баг, если невалидный JSON от LLM роняет extract.

        Когда generate возвращает не-JSON строку, агент обязан вернуть
        пустой список, а не бросить исключение. Ошибка парсинга — частая
        реальность LLM-ответов, её надо глотать, а не ронять конвейер.
        """
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
    """Группа тестов MemoryManagerAgent: сохранение и поиск фактов (D.2.3).

    Покрывают делегирование в MemoryService.store_fact со сбором
    результатов, graceful handling при падении сервиса и поиск фактов
    через search_facts с лимитом 10.
    """

    @pytest.mark.asyncio
    async def test_store_facts_delegates_to_service(self):
        """Ловит баг, если store_facts не сохраняет факты в память.

        Каждый факт обязан уйти в memory_service.store_fact, а результат —
        содержать id (строкой) и status="stored". Потеря вызова здесь
        означает, что извлечённый факт никогда не попадёт в память.
        """
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
        """Ловит баг, если падение MemoryService роняет store_facts.

        При исключении из store_fact результат должен содержать "error",
        а не пробрасывать исключение — агент обязан продолжить работу
        с остальными фактами и вернуть отчёт о сбое наверх.
        """
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
        """Ловит баг, если retrieve_facts не пробрасывает запрос в поиск.

        search_facts должен вызываться с (user_id, "coffee", 10) — лимит
        в 10 фактов фиксирован агентом, а результат нормализуется
        к dict с content и source="memory_service". Игнорирование лимита
        или запроса исказит подборку фактов для генератора ответа.
        """
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
    """Группа тестов ResponseGeneratorAgent: генерация ответа с памятью (D.2.4).

    Покрывают вызов LLM без контекста памяти (context_used=False),
    встраивание контекста при его наличии (context_used=True)
    и fallback-ответ при отключённом LLM.
    """

    @pytest.mark.asyncio
    @patch(_PATCH_RG_SETTINGS)
    @patch(_PATCH_RG_MEMORY)
    @patch(_PATCH_RG_LLM)
    async def test_generate_calls_llm(
        self, mock_llm_cls, mock_mem_cls, mock_settings
    ):
        """Ловит баг, если generate не возвращает ответ LLM.

        При пустом контексте памяти generate обязан вызвать LLM и вернуть
        response с context_used=False и fallback=False. Потеря флагов
        сломает аналитику качества ответов на дашборде.
        """
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
        """Ловит баг, если контекст памяти не помечается использованным.

        Когда get_memory_context возвращает непустую строку, generate
        обязан выставить context_used=True — иначе не видно, какие ответы
        ассистента опирались на память о клиенте.
        """
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
        """Ловит баг, если при ENABLE_LLM=False нет fallback-ответа.

        generate обязан вернуть FALLBACK_RESPONSE с fallback=True и
        context_used=False, не вызывая LLM. Без фолбэка чат умрёт
        при недоступности LLM-провайдера.
        """
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
    """Группа тестов ConflictResolverAgent: логика разрешения конфликтов (D.2.5).

    Покрывают приоритет более свежего факта (порог 5 минут), сохранение
    старого при более новом существующем, эскалацию в HITL при быстром
    конфликте и фолбэк на сравнение весов без временных меток.
    """

    def test_resolve_later_overrides_earlier(self):
        """Ловит баг, если новый факт не заменяет заметно более старый.

        Когда новый факт новее существующего больше чем на 5 минут,
        resolver обязан выбрать action="override" с новым содержанием
        и requires_hitl=False — без человека, конфликт очевиден.
        """
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
        """Ловит баг, если старый факт перетирает более свежий.

        Когда существующий факт новее нового, resolver обязан вернуть
        action="keep_existing" с прежним содержанием. Перезапись свежего
        факта старым потеряет актуальную информацию о клиенте.
        """
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
        """Ловит баг, если быстрый конфликт решается без человека.

        Когда разница временных меток меньше 5 минут, resolver обязан
        вернуть requires_hitl=True и action="flag_for_review" — противоречие
        за короткий срок слишком рискованно для автоматической перезаписи.
        """
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
        """Ловит баг, если конфликт без дат решается не по весам.

        При отсутствии временных меток resolver обязан сравнить weight:
        больший вес побеждает (action="override"). Пропуск фолбэка
        приведёт к падению на данных без created_at.
        """
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

"""
Unit Tests for Mem0MemoryService (Phase C.1.1)

Pure-mock тесты — база данных не нужна. Проверяют делегирование вызовов
суб-сервисам (FactService, VectorStoreService, GraphService,
RightToBeForgottenService, MemorySearchService) и graceful degradation:
падение векторного хранилища или графа не должно терять сохранённый факт.

Зачем pure-mock: mem0-оркестратор не должен знать про SQL/векторные
детали, тесты фиксируют его контракт делегирования без инфраструктуры.
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
    """Создать Mem0MemoryService со всеми внутренними сервисами-моками.

    Returns:
        Mem0MemoryService: оркестратор, у которого _fact_svc, _vector_svc,
        _graph_svc, _rtbf_svc и _search_svc заменены на MagicMock —
        доступны для assert_awaited/assert_called в тестах.
    """
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
    """Группа тестов store_fact: делегирование в FactService.

    Покрывают проброс аргументов в FactService.store_fact, индексацию
    факта в векторное хранилище и граф, а также graceful degradation
    при падении индексации.
    """

    @pytest.mark.asyncio
    async def test_store_fact_delegates_to_fact_service(self):
        """Ловит баг, если store_fact не пробрасывает аргументы в FactService.

        assert_awaited_once_with проверяет точные user_id, fact_type, value,
        channel, weight. Потерянный аргумент здесь — сломанное сохранение
        факта с неверным типом или каналом.
        """
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
        """Ловит баг, если сохранённый факт не попадает в векторное хранилище.

        index_fact обязан получить fact_id, user_id, content и metadata
        с типом и каналом. Без индекса семантический поиск не найдёт
        факт по смыслу запроса.
        """
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
        """Ловит баг, если факт не попадает в граф знаний.

        create_fact_node обязан получить id, категорию, сводку содержимого
        и consent_verified=True. Без узла в графе не построятся связи
        между фактами клиента.
        """
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
        """Ловит баг, если падение векторного хранилища теряет факт.

        Когда VectorStoreService бросает исключение, store_fact обязан
        всё равно вернуть сохранённый факт, а индексация в граф —
        продолжиться. Qdrant лежит — база фактов не должна терять данные.
        """
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
        """Ловит баг, если падение графа теряет факт.

        Когда GraphService бросает исключение, store_fact обязан всё
        равно вернуть факт, а векторная индексация — продолжиться.
        Neo4j лежит — факт должен сохраниться и быть доступным.
        """
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
    """Группа тестов retrieve_facts: делегирование в FactService.get_facts.

    Проверяют, что user_id и limit пробрасываются ниже, а параметр query
    намеренно не передаётся — он не входит в контракт get_facts.
    """

    @pytest.mark.asyncio
    async def test_retrieve_facts_delegates(self):
        """Ловит баг, если retrieve_facts не пробрасывает user_id и limit.

        FactService.get_facts должен вызываться ровно с этими аргументами,
        а результат — возвращаться без изменений. Неверный лимит или
        потерянный user_id исказят выборку фактов.
        """
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
    """Группа тестов search_facts: делегирование в FactService.search_facts.

    Проверяют проброс query и limit в поиск по расшифрованным значениям
    и неизменность возвращаемого списка фактов.
    """

    @pytest.mark.asyncio
    async def test_search_facts_delegates(self):
        """Ловит баг, если search_facts не пробрасывает query и limit.

        FactService.search_facts должен вызываться ровно с user_id, query
        и limit, а результат — возвращаться как есть. Потеря query
        превратит поиск в выдачу всех фактов пользователя.
        """
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
    """Группа тестов delete_user_data: делегирование в RTBF-сервис.

    Проверяют вызов RightToBeForgottenService.delete_user_data и
    нормализацию результата к словарю — основа права на забвение.
    """

    @pytest.mark.asyncio
    async def test_delete_user_data_delegates(self):
        """Ловит баг, если delete_user_data не вызывает RTBF-сервис.

        RightToBeForgottenService.delete_user_data обязан вызываться
        с user_id, а результат — нормализоваться к dict с deleted_facts
        и deleted_consent. Молчаливый пропуск удаления = данные остаются.
        """
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
    """Группа тестов get_memory_context: делегирование в MemorySearchService.

    Проверяют проброс user_id, current_message и max_facts в построение
    контекстной строки для LLM.
    """

    @pytest.mark.asyncio
    async def test_get_memory_context_delegates(self):
        """Ловит баг, если контекст строится без нужных параметров.

        MemorySearchService.get_memory_context обязан получить current_message
        и max_facts, а вернуть строку контекста для LLM. Потеря сообщения
        пользователя обесценит контекст памяти в ответе ассистента.
        """
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

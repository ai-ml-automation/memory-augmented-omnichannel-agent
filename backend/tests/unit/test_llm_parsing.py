"""
V.4: Contract Tests for LLM Response Parsing
Проверяют устойчивость FactExtractorAgent._extract_triplets
к «грязному» выводу LLM.

Зачем эти тесты: LLM не гарантирует чистый JSON. Парсер обязан
переживать markdown-обёртку ```json```, пояснительный текст вокруг
JSON, невалидный/пустой/объектный ответ и фильтровать эмоции —
иначе один капризный ответ LLM роняет извлечение фактов (V.4).
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


# We need ENABLE_LLM=true for the agent to attempt extraction
@pytest.fixture(autouse=True)
def enable_llm():
    """Autouse-фикстура: включить ENABLE_LLM на время каждого теста.

    Без этого флага агент не пытается извлекать факты и возвращает
    пустой список — фикстура снимает зависимость от реальных настроек.

    Yields:
        mock: мок модуля settings с ENABLE_LLM=True (patch активен).
    """
    with patch("backend.src.agents.fact_extractor.settings") as mock:
        mock.ENABLE_LLM = True
        yield mock


@pytest.fixture
def agent():
    """Создать FactExtractorAgent с замоканным LLM.

    Returns:
        FactExtractorAgent: агент, у которого llm заменён на AsyncMock —
        в тестах задаётся return_value для generate.
    """
    from backend.src.agents.fact_extractor import FactExtractorAgent

    instance = FactExtractorAgent()
    instance.llm = AsyncMock()
    return instance


class TestExtractTripletsMarkdownWrapper:
    """Группа тестов markdown-обёртки JSON.

    LLM часто оборачивает JSON в ```json ... ``` — парсер обязан
    вырезать код-фенс с языковым тегом и без него.
    """

    @pytest.mark.asyncio
    async def test_markdown_json_wrapper(self, agent):
        """Ловит баг, если парсер не вырезает ```json```-обёртку.

        Стандартный код-фенс с языковым тегом "json" обязан быть
        распознан и разобран в список фактов. Сырой json.loads
        на таком ответе упал бы с исключением.
        """
        llm_response = '```json\n[{"type": "fact", "content": "test content"}]\n```'
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("user message")

        assert len(result) == 1
        assert result[0]["type"] == "fact"
        assert result[0]["content"] == "test content"

    @pytest.mark.asyncio
    async def test_markdown_wrapper_without_language(self, agent):
        """Ловит баг, если код-фенс без языкового тега не разбирается.

        LLM иногда пишет ``` без "json" — парсер обязан распознать
        и этот вариант. Пропуск тега не должен ронять извлечение.
        """
        llm_response = '```\n[{"type": "preference", "content": "likes coffee"}]\n```'
        agent.llm.generate = AsyncMock(return_value=llm_response)

        result = await agent._extract_triplets("message")

        assert len(result) == 1
        assert result[0]["content"] == "likes coffee"


class TestExtractTripletsExtraText:
    """Группа тестов пояснительного текста вокруг JSON.

    LLM добавляет фразы до/после массива фактов — парсер обязан
    извлекать JSON из любого окружения.
    """

    @pytest.mark.asyncio
    async def test_text_before_json(self, agent):
        """Ловит баг, если текст перед JSON ломает парсинг.

        Пояснение «Here are the extracted facts:» перед массивом не должно
        мешать: парсер обязан найти JSON-подстроку и разобрать её.
        """
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
        """Ловит баг, если текст после JSON ломает парсинг.

        Комментарий после массива («Note: ...») не должен попасть в парсер
        — факты извлекаются корректно, хвост отбрасывается.
        """
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
        """Ловит баг, если текст с двух сторон JSON мешает извлечению.

        Массив фактов в окружении пояснений с обеих сторон обязан быть
        найден и разобран — комбинированный случай с кириллицей.
        """
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
    """Группа тестов полностью невалидного JSON.

    LLM может вернуть plain text, обрезанный JSON или пустую строку —
    парсер обязан вернуть пустой список, а не бросить исключение.
    """

    @pytest.mark.asyncio
    async def test_plain_text_response(self, agent):
        """Ловит баг, если plain text от LLM роняет парсер.

        Ответ без JSON вовсе обязан дать пустой список фактов.
        Исключение здесь уронило бы весь конвейер обработки сообщения.
        """
        agent.llm.generate = AsyncMock(return_value="This is not JSON at all")

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_partial_json(self, agent):
        """Ловит баг, если обрезанный JSON роняет парсер.

        Незавершённый JSON (обрыв на середине) обязан дать пустой список
        — LLM часто обрезает длинные ответы, это штатный сбой, не ошибка.
        """
        agent.llm.generate = AsyncMock(return_value='[{"type": "fact", "content":')

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_llm_returns_none_like(self, agent):
        """Ловит баг, если пустая строка от LLM роняет парсер.

        Пустой ответ "" обязан дать пустой список фактов — молчание
        модели это «фактов не найдено», а не сбой приложения.
        """
        agent.llm.generate = AsyncMock(return_value="")

        result = await agent._extract_triplets("test")

        assert result == []


class TestExtractTripletsEdgeCases:
    """Группа тестов граничных случаев: пустой массив, одиночный объект.

    Покрывают JSON-массивы разных форм и вложенности, которые LLM
    реально генерирует.
    """

    @pytest.mark.asyncio
    async def test_empty_array(self, agent):
        """Ловит баг, если пустой массив не даёт пустой результат.

        "[]" означает «фактов не найдено» — результат обязан быть
        пустым списком, без исключений и мусорных элементов.
        """
        agent.llm.generate = AsyncMock(return_value="[]")

        result = await agent._extract_triplets("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_single_object_wrapped(self, agent):
        """Ловит баг, если одиночный объект вместо массива теряется.

        LLM иногда возвращает один объект {...} вместо массива — парсер
        обязан обернуть его в список. Сырой json.loads дал бы dict,
        и код по индексации сломался бы.
        """
        agent.llm.generate = AsyncMock(
            return_value='{"type": "fact", "content": "single fact"}'
        )

        result = await agent._extract_triplets("test")

        # _extract_triplets wraps single objects in a list
        assert len(result) == 1
        assert result[0]["content"] == "single fact"

    @pytest.mark.asyncio
    async def test_multiple_facts(self, agent):
        """Ловит баг, если парсер теряет факты из многоэлементного массива.

        Массив из двух фактов (preference + fact) обязан вернуться
        целиком с сохранением порядка и типов — потери факта здесь
        обедняют память о клиенте.
        """
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
    """Группа тестов фильтрации эмоций после извлечения.

    Проверяют, что факты с type="emotion" удаляются из итогового
    результата extract, а остальные сохраняются.
    """

    @pytest.mark.asyncio
    async def test_emotions_filtered(self, agent):
        """Ловит баг, если эмоции просачиваются в итоговые факты.

        Из пары «emotion + fact» в результате обязан остаться только
        fact — эмоции нестабильны и не должны храниться как факты
        о клиенте.
        """
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

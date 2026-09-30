"""
Агент извлечения фактов из сообщений пользователя (этап D.2.2).

Назначение: превращать неструктурированный текст в структурированные
факты (type/content/weight), готовые к записи в память.
Почему через LLM: факты формулируются человеком вариативно, правило на
регулярках не покрывает перефразировки, а few-shot промпт задаёт формат.
Почему этапы вынесены в отдельные методы, а не линейный код: пайплайн
извлечение -> фильтр эмоций -> маскирование PII должен оставаться
расширяемым (например, эвристики вместо LLM при выключенном ENABLE_LLM).
Почему маскируем PII до записи: персональные данные (имена, контакты) не
должны попадать в память — требование приватности, и маскировка на входе
надёжнее, чем фильтрация при каждом чтении.

Конвейер: extract_triplets -> filter_emotions -> anonymize_pii.
"""

import json
import logging
import re
from typing import Any

from backend.src.config import get_settings
from backend.src.services.llm_service import LLMService

logger = logging.getLogger(__name__)
settings = get_settings()

EXTRACTION_PROMPT = (
    "Извлеки факты из "
    "следующего сообщения "
    "пользователя.\n"
    "Верни JSON-массив объектов с полями:\n"
    "- type: тип факта (preference, fact, intent, emotion)\n"
    "- content: текст факта\n"
    "- weight: важность (0.1-1.0)\n"
    "\n"
    "Правила:\n"
    '- Не извлекай эмоции (type="emotion") - '
    "они будут отфильтрованы\n"
    "- Факты должны быть "
    "конкретными и полезными "
    "для запоминания\n"
    "- Примеры: "
    '"любит кофе" (preference), '
    '"работает в Яндексе" (fact), '
    '"хочет купить машину" (intent)\n'
    "\n"
    "Сообщение: {message}\n"
    "\n"
    "Ответ (только JSON):"
)


class FactExtractorAgent:
    """
    Агент извлечения фактов (D.2.2).

    Конвейер: LLM-извлечение -> фильтр эмоций -> маскирование PII.
    Эмоции отбрасываем сразу: они эфемерны, и их хранение засоряет
    память, создавая ложные сигналы при поиске.
    """

    def __init__(self) -> None:
        self.llm = LLMService()

    async def extract(self, message: str) -> list[dict[str, Any]]:
        """
        Запустить полный конвейер извлечения.

        Args:
            message: Исходное сообщение пользователя.

        Returns:
            Список фактов {type, content, weight, pii_masked?}.
        """
        # Step 1: Extract triplets via LLM
        facts = await self._extract_triplets(message)

        # Step 2: Filter emotions
        facts = self._filter_emotions(facts)

        # Step 3: Anonymize PII
        facts = self._anonymize_pii(facts)

        return facts

    async def _extract_triplets(self, message: str) -> list[dict[str, Any]]:
        """Извлечь факты через LLM с few-shot промптом.

        Почему few-shot: примеры в промпте фиксируют формат JSON и
        допустимые типы фактов (preference/fact/intent/emotion), иначе
        LLM самовольно меняет схему. При выключенном ENABLE_LLM
        возвращаем пустой список — признак «фактов нет», а не ошибка.
        """
        if not settings.ENABLE_LLM:
            logger.warning("LLM disabled, skipping fact extraction")
            return []

        try:
            prompt = EXTRACTION_PROMPT.format(message=message)
            response = await self.llm.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,
            )

            # Parse JSON response
            # Try to extract JSON from response (may have markdown wrapper or extra text)
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            # If direct parse fails, try to find JSON array in the text
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                match = re.search(r"\[.*\]", json_str, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                else:
                    raise
            if not isinstance(parsed, list):
                parsed = [parsed]

            logger.info("Extracted %d facts from message", len(parsed))
            return parsed

        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return []
        except Exception as e:
            logger.error("Fact extraction failed: %s", e)
            return []

    def _filter_emotions(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Отфильтровать факты типа emotion (D.2.2).

        Почему: эмоции эфемерны и не являются фактами о пользователе;
        их хранение раздувает память и искажает выборку при поиске.
        """
        filtered = [
            f for f in facts
            if f.get("type", "").lower() != "emotion"
        ]
        removed = len(facts) - len(filtered)
        if removed:
            logger.info("Filtered %d emotional facts", removed)
        return filtered

    def _anonymize_pii(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Заменить PII в содержимом фактов через Presidio (D.2.2).

        Почему до записи, а не при чтении: маскируем один раз на входе,
        чтобы персональные данные не оседали в памяти (приватность).
        Изменённый факт помечается pii_masked — для аудита обработки.
        Presidio опционален (ImportError -> пропуск), чтобы не тянуть
        тяжёлую зависимость, когда она не установлена.
        """
        if not settings.ENABLE_LLM:
            return facts

        try:
            from backend.src.utils.presidio_anonymizer import anonymize_text

            for fact in facts:
                content = fact.get("content", "")
                if content:
                    anonymized = anonymize_text(content)
                    fact["content"] = anonymized
                    if anonymized != content:
                        fact["pii_masked"] = True

            return facts
        except ImportError:
            logger.debug("Presidio not available, skipping PII anonymization")
            return facts
        except Exception as e:
            logger.warning("PII anonymization failed: %s", e)
            return facts

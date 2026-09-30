"""
Агент управления памятью в диалоге (этап D.2.3).

Назначение: тонкий бизнес-слой поверх MemoryService (PG+Qdrant+Neo4j).
Почему тонкий: вся логика хранения/поиска сосредоточена в сервисе,
а агент отвечает за контракт диалога — какой формат факта принимается,
что вернуть вызывающему и как не потерять ошибку сохранения.
Почему через внедрённый сервис (DI): агент не создаёт соединения сам,
тестируется с фейковым сервисом без БД и векторного индекса.

store_facts: делегирует MemoryService.store_fact() по одному факту.
retrieve_facts: делегирует MemoryService.search_facts().
"""

import logging
import uuid
from typing import Any

from backend.src.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryManagerAgent:
    """
    Агент управления памятью (D.2.3).

    Делегирует все операции внедрённому MemoryService (DI): агент не
    создаёт подключения и не знает о конкретных хранилищах — это
    позволяет подменять сервис в тестах и менять слой памяти без
    правок в диалоговом коде.
    """

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    async def store_facts(
        self,
        user_id: uuid.UUID,
        facts: list[dict[str, Any]],
        channel: str = "text",
    ) -> list[dict[str, Any]]:
        """
        Сохранить факты через внедрённый MemoryService.

        Почему по одному, а не батчем: сервис хранит факт в нескольких
        хранилищах (PG/Qdrant/Neo4j), и при сбое на одном факте нужно
        сохранить остальные — батч уронил бы всё разом. Пустое содержимое
        пропускаем: факт без текста бесполезен и засорит индекс.

        Args:
            user_id: Идентификатор пользователя.
            facts: Список фактов {type, content, weight}.
            channel: Тип канала (text/telegram/vk/max).

        Returns:
            Результаты по каждому факту: {id, type, content, weight,
            status} при успехе либо {type, content, error} при сбое.
        """
        stored: list[dict[str, Any]] = []

        for fact_data in facts:
            fact_type = fact_data.get("type", "fact")
            content = fact_data.get("content", "")
            weight = fact_data.get("weight", 0.5)

            if not content:
                continue

            try:
                result = await self.memory_service.store_fact(
                    user_id=user_id,
                    fact_type=fact_type,
                    value=content,
                    channel=channel,
                    weight=weight,
                )
                stored.append({
                    "id": str(result.id) if hasattr(result, "id") else None,
                    "type": fact_type,
                    "content": content,
                    "weight": weight,
                    "status": "stored",
                })
            except Exception as e:
                logger.error("Failed to store fact via service: %s", e)
                stored.append({
                    "type": fact_type,
                    "content": content,
                    "error": str(e),
                })

        return stored

    async def retrieve_facts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Получить факты через внедрённый MemoryService.

        Args:
            user_id: Идентификатор пользователя.
            query: Поисковый запрос.
            limit: Максимум результатов.

        Returns:
            Список фактов {id, type, content, weight, source} —
            единая схема для диалогового слоя независимо от хранилища.
        """
        results = await self.memory_service.search_facts(
            user_id, query, limit
        )
        return [
            {
                "id": str(fact.id),
                "type": fact.type,
                "content": fact.value,
                "weight": fact.weight,
                "source": "memory_service",
            }
            for fact in results
        ]

"""
Mem0 Memory Service: конкретная реализация MemoryService на основе
FactService, VectorStoreService и GraphService.

ПОЧЕМУ graceful degradation: сбои внешних хранилищ (Qdrant, Neo4j)
не блокируют основное хранение фактов в PostgreSQL — индексация
в вектор и граф выполняется best-effort.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.fact_service import FactService
from backend.src.services.graph_service import GraphService
from backend.src.services.memory_search_service import MemorySearchService
from backend.src.services.memory_service import MemoryService
from backend.src.services.right_to_be_forgotten_service import RightToBeForgottenService
from backend.src.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class Mem0MemoryService(MemoryService):
    """
    Конкретная реализация MemoryService.

    Делегирует хранение фактов FactService, векторную индексацию
    VectorStoreService, граф — GraphService, удаление по RTBF —
    RightToBeForgottenService. Внешние хранилища деградируют мягко.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._fact_service = FactService(db)
        self._vector_store = VectorStoreService()
        self._graph_service = GraphService()
        self._rtbf_service = RightToBeForgottenService(db)
        self._search_service = MemorySearchService(db)

    async def store_fact(
        self,
        user_id: uuid.UUID,
        fact_type: str,
        value: str,
        channel: str,
        weight: float = 1.0,
    ) -> Any:
        """
        Сохранить факт: PostgreSQL обязателен, вектор и граф — best-effort.

        ПОЧЕМУ: основное хранение (FactService) не должно зависеть
        от внешних сервисов — их сбой логируется и не роняет запись.
        """
        fact = await self._fact_service.store_fact(
            user_id=user_id,
            fact_type=fact_type,
            value=value,
            channel=channel,
            weight=weight,
        )

        # Best-effort: index in Qdrant vector store
        try:
            await self._vector_store.index_fact(
                fact_id=fact.id,
                user_id=user_id,
                content=value,
                metadata={"type": fact_type, "channel": channel},
            )
        except Exception as exc:
            logger.warning(
                "Vector indexing failed for fact %s: %s",
                fact.id,
                exc,
            )

        # Best-effort: create node in Neo4j knowledge graph
        try:
            await self._graph_service.create_fact_node(
                fact_id=fact.id,
                user_id=user_id,
                category=fact_type,
                content_summary=value[:200],
                metadata={"channel": channel},
                consent_verified=True,
            )
        except Exception as exc:
            logger.warning(
                "Graph indexing failed for fact %s: %s",
                fact.id,
                exc,
            )

        return fact

    async def retrieve_facts(
        self,
        user_id: uuid.UUID,
        query: str = "",
        limit: int = 10,
    ) -> list[Any]:
        """
        Получить факты через FactService.get_facts.

        ПОЧЕМУ query игнорируется: интерфейс ABC требует параметр,
        но выборка последних фактов не фильтрует по тексту — для
        поиска используйте search_facts.
        """
        return await self._fact_service.get_facts(
            user_id=user_id,
            limit=limit,
        )

    async def search_facts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[Any]:
        """
        Найти факты по тексту через FactService.search_facts.

        Реализация текстового поиска (in-memory по расшифрованным
        значениям) — см. предупреждения в FactService.search_facts.
        """
        return await self._fact_service.search_facts(
            user_id=user_id,
            query=query,
            limit=limit,
        )

    async def delete_user_data(self, user_id: uuid.UUID) -> dict[str, Any]:
        """
        Удалить все данные пользователя через RightToBeForgottenService.

        Возврат нормализуется к dict[str, Any] — сигнатура ABC
        допускает Any, но контракт интерфейса остаётся строгим.
        """
        result = await self._rtbf_service.delete_user_data(user_id=user_id)
        # Normalise return to dict[str, Any] as declared in the ABC
        return dict(result)

    async def get_memory_context(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_facts: int = 5,
    ) -> str:
        """
        Контекст памяти для промпта LLM через MemorySearchService.

        Гибридный поиск (keyword + vector + graph) с реранжированием;
        подробности — в MemorySearchService.get_memory_context.
        """
        return await self._search_service.get_memory_context(
            user_id=user_id,
            current_message=current_message,
            max_facts=max_facts,
        )

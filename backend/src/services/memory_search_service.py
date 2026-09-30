"""
Сервис гибридного поиска по памяти: факты (PostgreSQL), векторы
(Qdrant) и граф (Neo4j) в едином интерфейсе.

III.3: опциональный реранжировщик Cross-Encoder для релевантности.
γ.1: модель загружается лениво в thread pool, чтобы не блокировать
event loop при холодном старте.
"""

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.services.fact_service import FactService
from backend.src.services.graph_service import GraphService
from backend.src.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)
settings = get_settings()


class MemorySearchService:
    """
    Единый сервис поиска по памяти.

    Комбинирует стратегии:
    - keyword: текстовый поиск (PostgreSQL, in-memory по расшифровке);
    - vector: семантический поиск (Qdrant);
    - graph: обход графа знаний (Neo4j);
    - hybrid: объединение всех стратегий + реранжирование (III.3).

    ПОЧЕМУ гибрид: каждая стратегия видит свой срез памяти — ключевые
    слова точны, векторы ловят синонимы, граф находит связанные факты.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fact_service = FactService(db)
        self.vector_service = VectorStoreService()
        self.graph_service = GraphService()
        self._ranker = None

    async def _get_ranker(self) -> Any:
        """
        Ленивая инициализация Cross-Encoder реранжировщика (III.3, γ.1).

        Модель загружается в thread pool, чтобы не блокировать event
        loop; при недоступности помечается False и поиск идёт без реранга.
        """
        if self._ranker is None:
            if not settings.ENABLE_LLM:
                return None
            try:
                from sentence_transformers import CrossEncoder

                # γ.1: Load model in thread pool to avoid blocking event loop
                loop = asyncio.get_running_loop()
                self._ranker = await loop.run_in_executor(
                    None,
                    lambda: CrossEncoder("BAAI/bge-reranker-large", device="cpu"),
                )
                logger.info("Cross-Encoder ranker loaded: bge-reranker-large")
            except (ImportError, Exception) as e:
                logger.warning(
                    "Cross-Encoder ranker not available, skipping re-ranking: %s",
                    type(e).__name__,
                )
                self._ranker = False  # mark as unavailable
        return self._ranker if self._ranker is not False else None

    async def search(
        self,
        user_id: uuid.UUID,
        query: str,
        search_type: str = "hybrid",
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Поиск по памяти выбранной стратегией.

        Стратегия задаёт, какие хранилища опрашиваются: keyword,
        vector, graph или hybrid (все три + реранжирование).

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            search_type: Тип поиска (keyword, vector, graph, hybrid)
            limit: Максимум результатов

        Returns:
            Результаты поиска с метаданными
        """
        results = {
            "query": query,
            "search_type": search_type,
            "results": [],
            "metadata": {},
        }

        if search_type == "keyword":
            results["results"] = await self._keyword_search(user_id, query, limit)
        elif search_type == "vector":
            results["results"] = await self._vector_search(user_id, query, limit)
        elif search_type == "graph":
            results["results"] = await self._graph_search(user_id, query, limit)
        elif search_type == "hybrid":
            results["results"] = await self._hybrid_search(user_id, query, limit)
        else:
            raise ValueError(f"Unknown search type: {search_type}")

        results["metadata"]["total"] = len(results["results"])
        return results

    async def _keyword_search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Текстовый поиск по PostgreSQL (через FactService.search_facts).

        ПОЧЕМУ in-memory: значения хранятся зашифрованными (B.1.2),
        поэтому поиск идёт по расшифрованным данным в памяти.

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Найденные факты
        """
        facts = await self.fact_service.search_facts(user_id, query, limit)

        return [
            {
                "id": str(fact.id),
                "type": "keyword",
                "category": fact.type,
                "content": fact.value,
                "confidence": fact.weight,
                "score": 1.0,
            }
            for fact in facts
        ]

    async def _vector_search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Семантический поиск по векторам в Qdrant.

        ПОЧЕМУ пустой результат при ENABLE_LLM=False: эмбеддинги
        требуют LLM-модели, без неё векторный поиск невозможен.

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Похожие факты с оценками
        """
        if not settings.ENABLE_LLM:
            return []

        try:
            results = await self.vector_service.search_similar(
                user_id=user_id,
                query=query,
                limit=limit,
            )

            return [
                {
                    "id": result["id"],
                    "type": "vector",
                    "content": result["content"],
                    "score": result["score"],
                    "metadata": result.get("metadata", {}),
                }
                for result in results
            ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def _graph_search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Поиск по графу знаний в Neo4j.

        Обход глубины 2 (связи фактов пользователя), фильтрация узлов
        по вхождению query в summary узла типа Fact.

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Связанные факты из графа
        """
        if not settings.ENABLE_LLM:
            return []

        try:
            graph_data = await self.graph_service.get_user_facts_graph(
                user_id=user_id,
                depth=2,
            )

            # Filter by query in summary
            results = [
                node
                for node in graph_data.get("nodes", [])
                if node.get("type") == "Fact"
                and query.lower() in node.get("summary", "").lower()
            ][:limit]

            return [
                {
                    "id": result["id"],
                    "type": "graph",
                    "category": result.get("category", ""),
                    "content": result.get("summary", ""),
                    "score": 0.8,
                }
                for result in results
            ]
        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
            return []

    async def _hybrid_search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Гибридный поиск: keyword + vector + graph + реранжирование.

        Выборка limit*3 (запас для реранга), дедупликация по id,
        затем Cross-Encoder реранжирование (III.3) или сортировка
        по исходному score при его недоступности.

        Args:
            user_id: Идентификатор пользователя
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Объединённые результаты с оценками
        """
        # Fetch more results initially for better re-ranking
        fetch_limit = limit * 3
        all_results = []

        # Keyword search (always available)
        keyword_results = await self._keyword_search(user_id, query, fetch_limit)
        all_results.extend(keyword_results)

        # Vector search (if enabled)
        vector_results = await self._vector_search(user_id, query, fetch_limit)
        all_results.extend(vector_results)

        # Graph search (if enabled)
        graph_results = await self._graph_search(user_id, query, fetch_limit)
        all_results.extend(graph_results)

        # Deduplicate by ID
        seen_ids = set()
        unique_results = []

        for result in all_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                unique_results.append(result)

        # III.3: Cross-Encoder re-ranking
        ranker = await self._get_ranker()
        if ranker and len(unique_results) > 0:
            try:
                pairs = [[query, r.get("content", "")] for r in unique_results]
                scores = ranker.predict(pairs)
                for i, r in enumerate(unique_results):
                    r["rerank_score"] = float(scores[i])
                unique_results.sort(
                    key=lambda x: x.get("rerank_score", 0), reverse=True
                )
                logger.debug("Re-ranked %d results", len(unique_results))
            except Exception as e:
                logger.warning(
                    "Re-ranking failed, using original scores: %s", e
                )
        else:
            # Sort by original score
            unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return unique_results[:limit]

    async def get_memory_context(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_facts: int = 5,
    ) -> str:
        """
        Контекст памяти для промпта LLM.

        Гибридный поиск по текущему сообщению; результаты собираются
        в строку «Релевантная информация из памяти: ...» для подстановки
        в промпт.

        Args:
            user_id: Идентификатор пользователя
            current_message: Текущее сообщение пользователя
            max_facts: Максимум фактов в контексте

        Returns:
            Строка контекста для LLM
        """
        search_results = await self.search(
            user_id=user_id,
            query=current_message,
            search_type="hybrid",
            limit=max_facts,
        )

        if not search_results["results"]:
            return ""

        context_parts = ["Релевантная информация из памяти:"]

        for i, result in enumerate(search_results["results"], 1):
            content = result.get("content", "")
            if isinstance(content, dict):
                content = str(content)
            context_parts.append(f"{i}. {content}")

        return "\n".join(context_parts)

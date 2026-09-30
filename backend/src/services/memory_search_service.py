"""
Memory Search Service
Combined search across facts, vectors, and graph.

III.3: Optional Cross-Encoder re-ranking for improved relevance.
γ.1: Preload Cross-Encoder at startup to eliminate cold start latency.
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
    Unified memory search service.

    Combines:
    - Keyword search (PostgreSQL)
    - Semantic search (Qdrant vectors)
    - Graph traversal (Neo4j)
    - III.3: Cross-Encoder re-ranking (optional, when ENABLE_LLM=True)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fact_service = FactService(db)
        self.vector_service = VectorStoreService()
        self.graph_service = GraphService()
        self._ranker = None

    async def _get_ranker(self) -> Any:
        """Lazy initialization of Cross-Encoder ranker (III.3, γ.1).

        Loads the model in a thread pool to avoid blocking the event loop.
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
        Search memory using specified strategy.

        Args:
            user_id: User identifier
            query: Search query
            search_type: Search type (keyword, vector, graph, hybrid)
            limit: Maximum results

        Returns:
            Search results with metadata
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
        Keyword search in PostgreSQL.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            Matching facts
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
        Semantic vector search in Qdrant.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            Similar facts with scores
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
        Graph-based search in Neo4j.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            Related facts from graph
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
        Hybrid search combining keyword + vector + graph + re-ranking.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            Combined results with scores
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
        Get memory context for LLM prompt.

        Args:
            user_id: User identifier
            current_message: Current user message
            max_facts: Maximum facts to include

        Returns:
            Context string for LLM
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

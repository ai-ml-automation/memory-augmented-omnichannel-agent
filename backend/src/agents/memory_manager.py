"""
Memory Manager Agent
Thin business-logic layer over MemoryService (Phase D.2.3).

store_facts: delegates to MemoryService (PG+Qdrant+Neo4j)
retrieve_facts: delegates to MemoryService.search_facts()
"""

import logging
import uuid
from typing import Any

from backend.src.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryManagerAgent:
    """
    Agent for managing memory operations.
    Delegates all storage to MemoryService via DI.
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
        Store facts via the injected MemoryService.

        Args:
            user_id: User identifier
            facts: List of fact dicts with type, content, weight
            channel: Channel type

        Returns:
            List of stored fact results
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
        Retrieve facts via the injected MemoryService.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            List of facts
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

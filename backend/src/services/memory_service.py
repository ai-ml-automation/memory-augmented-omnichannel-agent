"""
Memory Service
Abstract base class for memory operations (Phase C.1.1).

Defines the unified interface that concrete implementations
(e.g. Mem0MemoryService) must satisfy.
"""

import abc
import uuid
from typing import Any



class MemoryService(abc.ABC):
    """Abstract memory service interface (Phase C.1.1)."""

    @abc.abstractmethod
    async def store_fact(
        self,
        user_id: uuid.UUID,
        fact_type: str,
        value: str,
        channel: str,
        weight: float = 1.0,
    ) -> Any:
        """Store a fact in memory."""
        ...

    @abc.abstractmethod
    async def retrieve_facts(
        self,
        user_id: uuid.UUID,
        query: str = "",
        limit: int = 10,
    ) -> list[Any]:
        """Retrieve facts from memory."""
        ...

    @abc.abstractmethod
    async def search_facts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[Any]:
        """Search facts by text."""
        ...

    @abc.abstractmethod
    async def delete_user_data(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Delete all user data (RTBF)."""
        ...

    @abc.abstractmethod
    async def get_memory_context(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_facts: int = 5,
    ) -> str:
        """Get memory context string for LLM prompt."""
        ...

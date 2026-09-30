"""
Vector Store Service
Integration with Qdrant for vector similarity search (Phase D.1).
Uses sentence-transformers for real embeddings.

III.2: Dedicated ThreadPoolExecutor for embedding computation
to prevent API thread exhaustion under high load.
"""

import concurrent.futures
import logging
import time
import uuid
from typing import Any

from backend.src.config import get_settings
from backend.src.metrics import QDRANT_SEARCH_DURATION

logger = logging.getLogger(__name__)
settings = get_settings()

# III.2: Dedicated thread pool for embedding computation.
# ThreadPoolExecutor (not ProcessPool) because sentence-transformers
# releases GIL during inference. 16 workers handles 50+ concurrent
# requests without blocking the FastAPI event loop.
_embedding_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=16,
    thread_name_prefix="embedding",
)


class VectorStoreService:
    """
    Vector store service using Qdrant.
    Phase D.1: Real embeddings via sentence-transformers.
    """

    def __init__(self):
        self._client = None
        self._model = None
        self._collection = "facts"

    def _get_client(self) -> Any:
        """Lazy initialization of Qdrant client."""
        if self._client is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("Vector store disabled (ENABLE_LLM=false)")

            try:
                from qdrant_client import QdrantClient

                self._client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                )
                logger.info("Qdrant client initialized")
            except ImportError:
                raise RuntimeError("qdrant-client package not installed")

        return self._client

    def _get_model(self) -> Any:
        """Lazy initialization of sentence-transformers model (Phase D.1)."""
        if self._model is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("Embeddings disabled (ENABLE_LLM=false)")

            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info(
                    "SentenceTransformer model loaded: %s",
                    settings.EMBEDDING_MODEL,
                )
            except ImportError:
                raise RuntimeError("sentence-transformers package not installed")

        return self._model

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text (Phase D.1).

        Args:
            text: Input text

        Returns:
            List of floats (embedding vector)
        """
        model = self._get_model()
        import asyncio
        loop = asyncio.get_event_loop()
        # III.2: Use dedicated embedding thread pool
        embedding = await loop.run_in_executor(
            _embedding_executor,
            lambda: model.encode(text, normalize_embeddings=True),
        )
        return embedding.tolist()

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts (Phase D.1).

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        model = self._get_model()
        import asyncio
        loop = asyncio.get_event_loop()
        # III.2: Use dedicated embedding thread pool
        embeddings = await loop.run_in_executor(
            _embedding_executor,
            lambda: model.encode(texts, normalize_embeddings=True, batch_size=32),
        )
        return embeddings.tolist()

    async def index_fact(
        self,
        fact_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Index a fact with real embedding (Phase D.1).

        Args:
            fact_id: Fact identifier
            user_id: User identifier
            content: Fact content to embed
            metadata: Optional metadata

        Returns:
            True if indexed successfully
        """
        if not settings.ENABLE_LLM:
            logger.warning("Vector store disabled, skipping indexing")
            return False

        try:
            client = self._get_client()

            # Phase D.1: Generate real embedding
            embedding = await self.get_embedding(content)

            client.upsert(
                collection_name=self._collection,
                points=[
                    {
                        "id": str(fact_id),
                        "vector": embedding,
                        "payload": {
                            "user_id": str(user_id),
                            "content": content,
                            **(metadata or {}),
                        },
                    }
                ],
            )

            logger.info("Fact %s indexed in vector store", fact_id)
            return True
        except Exception as e:
            logger.error("Failed to index fact: %s", e)
            return False

    async def search_similar(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for similar facts using real query embedding (Phase D.1).

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results

        Returns:
            List of similar facts with scores
        """
        if not settings.ENABLE_LLM:
            logger.warning("Vector store disabled, skipping search")
            return []

        start_time = time.perf_counter()
        try:
            client = self._get_client()

            # Phase D.1: Generate real query embedding
            query_embedding = await self.get_embedding(query)

            results = client.search(
                collection_name=self._collection,
                query_vector=query_embedding,
                query_filter={
                    "must": [
                        {
                            "key": "user_id",
                            "match": {"value": str(user_id)},
                        }
                    ]
                },
                limit=limit,
            )

            return [
                {
                    "id": point.id,
                    "score": point.score,
                    "content": point.payload.get("content", ""),
                    "metadata": {
                        k: v
                        for k, v in point.payload.items()
                        if k != "content"
                    },
                }
                for point in results
            ]
        except Exception as e:
            logger.error("Failed to search vector store: %s", e)
            return []
        finally:
            duration = time.perf_counter() - start_time
            QDRANT_SEARCH_DURATION.labels(collection=self._collection).observe(duration)

    async def delete_fact(self, fact_id: uuid.UUID) -> bool:
        """
        Delete fact from vector index.

        Args:
            fact_id: Fact identifier

        Returns:
            True if deleted
        """
        if not settings.ENABLE_LLM:
            return False

        try:
            client = self._get_client()
            client.delete(
                collection_name=self._collection,
                points_selector=[str(fact_id)],
            )
            logger.info("Fact %s deleted from vector store", fact_id)
            return True
        except Exception as e:
            logger.error("Failed to delete fact from vector store: %s", e)
            return False

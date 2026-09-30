"""
Сервис векторного поиска по фактам на базе Qdrant (Phase D.1).

Реальные эмбеддинги считаются sentence-transformers: это позволяет находить
семантически близкие факты, даже если в запросе нет общих ключевых слов.

Ключевые решения:
- выделенный ThreadPoolExecutor для эмбеддингов (III.2): инференс отпускает GIL,
  поэтому не блокирует event loop FastAPI; 16 воркеров держат 50+ запросов;
- ленивая инициализация клиента и модели — сервис стартует без Qdrant
  и sentence-transformers (ENABLE_LLM=false);
- поиск фильтруется по user_id: коллекция общая, а изоляция пользователей
  обеспечивается фильтром запроса, а не отдельными коллекциями.

@see memory_search_service (гибридный поиск), QDRANT_SEARCH_DURATION
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
    Сервис векторного хранилища на базе Qdrant (Phase D.1).

    Ответственность: индексация фактов реальными эмбеддингами и семантический
    поиск по ним с фильтрацией по владельцу.

    Жизненный цикл: один экземпляр на приложение; клиент Qdrant и модель
    sentence-transformers создаются лениво при первой необходимости.

    Почему Qdrant: выделенная векторная БД масштабируется независимо от
    PostgreSQL и поддерживает фильтры по payload (user_id) на стороне поиска,
    что сохраняет изоляцию данных пользователей.

    @see memory_search_service, VectorStoreService.get_embedding
    """

    def __init__(self):
        """
        Инициализация сервиса без создания клиента и модели.

        Клиент Qdrant и модель эмбеддингов инициализируются лениво
        при первом обращении (_get_client/_get_model), чтобы приложение
        могло стартовать без векторной БД и ML-зависимостей.
        """
        self._client = None
        self._model = None
        self._collection = "facts"

    def _get_client(self) -> Any:
        """
        Ленивая инициализация клиента Qdrant.

        Почему лениво: qdrant-client может быть не установлен, а сам Qdrant —
        недоступен; сервис обязан стартовать (ENABLE_LLM=false) и сообщать
        о недоступности хранилища только в момент реальной операции.

        Raises:
            RuntimeError: если хранилище отключено или пакет не установлен
        """
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
        """
        Ленивая загрузка модели sentence-transformers (Phase D.1).

        Модель (settings.EMBEDDING_MODEL) скачивается/загружается один раз
        и переиспользуется: загрузка тяжёлая (сотни МБ), поэтому происходит
        только при первой реальной потребности в эмбеддингах, а не при старте.

        Raises:
            RuntimeError: если эмбеддинги отключены или пакет не установлен
        """
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
        Расчёт эмбеддинга для одного текста (Phase D.1).

        Вычисление выносится в выделенный пул потоков _embedding_executor
        (III.2): model.encode блокирует поток на время инференса, а пул
        изолирует это от event loop FastAPI. normalize_embeddings=True
        приводит векторы к единичной длине — косинусное сходство тогда
        эквивалентно скалярному произведению.

        Args:
            text: входной текст для векторизации

        Returns:
            список float — вектор эмбеддинга
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
        Расчёт эмбеддингов для списка текстов (Phase D.1).

        Пакетная обработка (batch_size=32) заметно быстрее посимвольного
        вызова get_embedding: модель эффективнее использует GPU/CPU на пакетах.
        Как и одиночная версия, выполняется в выделенном пуле потоков (III.2).

        Args:
            texts: список текстов для векторизации

        Returns:
            список векторов эмбеддингов (по одному на текст)
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
        Индексация факта в векторном хранилище с реальным эмбеддингом (Phase D.1).

        user_id кладётся в payload точки: без него последующий search_similar
        не смог бы отфильтровать результаты по владельцу, и пользователи
        видели бы чужие факты. Метаданные распаковываются в payload, поэтому
        могут переопределять служебные ключи — вызывающий код отвечает
        за их корректность.

        Args:
            fact_id: идентификатор факта (uuid)
            user_id: идентификатор владельца факта
            content: текст факта для эмбеддинга
            metadata: дополнительные поля payload

        Returns:
            True, если факт проиндексирован (или хранилище отключено)
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
        Поиск фактов, похожих на запрос, реальным эмбеддингом запроса (Phase D.1).

        Обязательный фильтр по user_id не даёт выдать факты другого
        пользователя: векторная коллекция общая, и только фильтр запроса
        обеспечивает изоляцию (privacy, 152-ФЗ). Длительность поиска всегда
        фиксируется в метрике QDRANT_SEARCH_DURATION — включая ошибки,
        поэтому наблюдение за метрикой видит и деградацию хранилища.

        Args:
            user_id: идентификатор пользователя (фильтр владельца)
            query: поисковый запрос
            limit: максимальное число результатов

        Returns:
            список dict с ключами id, score, content, metadata
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
        Удаление факта из векторного индекса.

        Вызывается каскадом из right_to_be_forgotten_service (RTBF, 152-ФЗ):
        векторная копия факта должна удаляться вместе с записью в PostgreSQL,
        иначе семантический поиск продолжит выдавать удалённые ПДн.

        Args:
            fact_id: идентификатор факта

        Returns:
            True, если факт удалён (или хранилище отключено)
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

"""
Интеграционные тесты vector store эмбеддингов (Phase D.1).

Подменяют тяжёлые библиотеки (sentence_transformers, qdrant_client)
через sys.modules ДО импорта VectorStoreService, поэтому тесты
работают без установленных torch/sentence-transformers и без
реального Qdrant. Проверяют контракт сервиса: реальный вызов encode
с normalize_embeddings, передачу query_vector в поиск, ленивую
загрузку модели.
"""

import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest


def _make_fake_modules():
    """Создаёт полный набор моков sentence_transformers и qdrant_client.

    Returns:
        (mock_model, mock_client, fake_st, fake_qdrant): модель с encode
        (возвращает вектор 384), клиент Qdrant, фейковые модули.
    """
    mock_model = MagicMock()
    mock_embedding = [0.1] * 384
    mock_model.encode.return_value = MagicMock(
        tolist=MagicMock(return_value=mock_embedding)
    )

    mock_client = MagicMock()

    fake_st = MagicMock()
    fake_st.SentenceTransformer = MagicMock(return_value=mock_model)

    fake_qdrant = MagicMock()
    fake_qdrant.QdrantClient = MagicMock(return_value=mock_client)

    return mock_model, mock_client, fake_st, fake_qdrant


def _install_fake_modules(fake_st, fake_qdrant):
    """Собирает словарь подмены sys.modules для импорта сервиса.

    Args:
        fake_st: фейковый модуль sentence_transformers.
        fake_qdrant: фейковый модуль qdrant_client.

    Returns:
        dict: карта «имя модуля → мок» для patch.dict(sys.modules, ...).
    """
    fake = {
        "sentence_transformers": fake_st,
        "qdrant_client": fake_qdrant,
    }
    for mod in ("bcrypt", "_bcrypt"):
        if mod not in sys.modules:
            fake[mod] = MagicMock()
    return fake


class TestVectorStoreEmbeddings:
    """Группа тестов контракта VectorStoreService на фейках зависимостей.

    Покрывают реальный вызов encode (index_fact), передачу
    query_vector в поиск (search_similar) и ленивую загрузку модели
    (get_embedding). Тяжёлые библиотеки подменены через sys.modules.
    """

    @pytest.mark.asyncio
    async def test_index_fact_generates_real_embedding(self):
        """Ловит отключение реального эмбеддинга: факт индексируется «вхолостую».

        index_fact обязан вызвать encode с normalize_embeddings=True
        и отправить upsert в Qdrant; иначе векторный поиск
        возвращает пустоту (Phase D.1).
        """
        mock_model, mock_client, fake_st, fake_qdrant = _make_fake_modules()
        fake_modules = _install_fake_modules(fake_st, fake_qdrant)

        with patch.dict(sys.modules, fake_modules, clear=False):
            from backend.src.services.vector_store_service import (
                VectorStoreService,
            )

            with patch(
                "backend.src.services.vector_store_service.settings"
            ) as mock_settings:
                mock_settings.ENABLE_LLM = True
                mock_settings.QDRANT_URL = "http://localhost:6333"
                mock_settings.QDRANT_API_KEY = ""
                mock_settings.EMBEDDING_MODEL = "test-model"

                svc = VectorStoreService()
                fact_id = uuid.uuid4()
                user_id = uuid.uuid4()

                result = await svc.index_fact(fact_id, user_id, "test content")

                assert result is True
                mock_model.encode.assert_called_once_with(
                    "test content", normalize_embeddings=True
                )
                mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_uses_real_query_embedding(self):
        """Ловит поиск без эмбеддинга запроса: query_vector теряется.

        search_similar обязан закодировать запрос и передать вектор
        в search; без этого поиск по смыслу вырождается в пустой
        результат (Phase D.1).
        """
        mock_model, mock_client, fake_st, fake_qdrant = _make_fake_modules()

        mock_point = MagicMock()
        mock_point.id = str(uuid.uuid4())
        mock_point.score = 0.95
        mock_point.payload = {
            "content": "test fact",
            "user_id": "some-uuid",
        }
        mock_client.search.return_value = [mock_point]

        fake_modules = _install_fake_modules(fake_st, fake_qdrant)

        with patch.dict(sys.modules, fake_modules, clear=False):
            from backend.src.services.vector_store_service import (
                VectorStoreService,
            )

            with patch(
                "backend.src.services.vector_store_service.settings"
            ) as mock_settings:
                mock_settings.ENABLE_LLM = True
                mock_settings.QDRANT_URL = "http://localhost:6333"
                mock_settings.QDRANT_API_KEY = ""
                mock_settings.EMBEDDING_MODEL = "test-model"

                svc = VectorStoreService()
                user_id = uuid.uuid4()

                results = await svc.search_similar(user_id, "search query")

                mock_model.encode.assert_called_once_with(
                    "search query", normalize_embeddings=True
                )
                mock_client.search.assert_called_once()
                call_kwargs = mock_client.search.call_args
                assert call_kwargs.kwargs["query_vector"] == [0.1] * 384
                assert len(results) == 1
                assert results[0]["content"] == "test fact"

    @pytest.mark.asyncio
    async def test_embedding_lazy_loading(self):
        """Ловит жадную загрузку модели: SentenceTransformer создаётся рано.

        Модель должна создаваться только при первом запросе эмбеддинга
        (лениво) — при старте приложения тяжёлая загрузка недопустима.
        """
        mock_model, mock_client, fake_st, fake_qdrant = _make_fake_modules()
        fake_modules = _install_fake_modules(fake_st, fake_qdrant)

        with patch.dict(sys.modules, fake_modules, clear=False):
            from backend.src.services.vector_store_service import (
                VectorStoreService,
            )

            with patch(
                "backend.src.services.vector_store_service.settings"
            ) as mock_settings:
                mock_settings.ENABLE_LLM = True
                mock_settings.QDRANT_URL = "http://localhost:6333"
                mock_settings.QDRANT_API_KEY = ""
                mock_settings.EMBEDDING_MODEL = "test-model"

                svc = VectorStoreService()

                assert svc._model is None

                await svc.get_embedding("trigger loading")

                fake_st.SentenceTransformer.assert_called_once_with("test-model")
                assert svc._model is mock_model
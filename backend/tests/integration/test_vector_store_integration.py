"""
Integration tests for vector store embeddings (Phase D.1).

Mocks heavy libraries (sentence_transformers, qdrant_client) via
sys.modules BEFORE importing VectorStoreService, so tests run without
torch/sentence-transformers installed.
"""

import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest


def _make_fake_modules():
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
    fake = {
        "sentence_transformers": fake_st,
        "qdrant_client": fake_qdrant,
    }
    for mod in ("bcrypt", "_bcrypt"):
        if mod not in sys.modules:
            fake[mod] = MagicMock()
    return fake


class TestVectorStoreEmbeddings:

    @pytest.mark.asyncio
    async def test_index_fact_generates_real_embedding(self):
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
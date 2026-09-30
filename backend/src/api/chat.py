"""
Чат-роутер: API сообщений и генерации ответов (Phase C.3.1).

C.3.1: роутер остаётся тонким — вся логика (память, оценка ответа, магазин
фактов) живёт в ChatService. Здесь только десериализация запроса и перевод
ошибок в HTTP-статусы, поэтому API не разбухает, а логика переиспользуется
другими каналами (voice, webhooks).
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.services.chat_service import ChatService
from backend.src.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Запрос к чату: текст, канал и история для контекста.

    history — последние сообщения диалога, чтобы LLM отвечал с учётом
    контекста, а не только на последнюю реплику (опционально).
    """

    message: str
    channel_type: str = "text"
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    """Ответ чата: текст, оценка качества ответа и число сохранённых фактов.

    evaluation и facts_stored обязательны: клиент всегда видит, насколько
    ответ подкреплён памятью и что записалось в память.
    """

    response: str
    evaluation: dict[str, Any]
    facts_stored: int


class HealthCheck(BaseModel):
    """Состояние LLM-интеграции.

    Отдаёт провайдера, флаг ENABLE_LLM и состояние клиента модели. По этим
    данным фронтенд решает, показывать ли поле ввода чата и какие подсказки
    давать пользователю.
    """

    provider: str
    enabled: bool
    initialized: bool


@router.post("/users/{user_id}/message", response_model=ChatResponse)
async def send_message(
    user_id: uuid.UUID,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Отправить сообщение пользователя и получить ответ AI.

    C.3.1: делегируем ChatService — он достаёт релевантные факты из памяти,
    формирует промпт, генерирует ответ, оценивает его и сохраняет новые факты.

    Если LLM выключен (ENABLE_LLM=false), сервис бросает RuntimeError: он
    превращается в вежливый ответ со статусом 200, а не в 500. Остальное — 500.

    Args:
        user_id: Владелец диалога — изоляция памяти между пользователями.
        data: Сообщение, канал и история.
        db: Сессия БД.

    Returns:
        Текст ответа, оценка и число записанных в память фактов.

    Raises:
        500: Внутренняя ошибка обработки сообщения.
    """
    try:
        svc = ChatService(db)
        result = await svc.send_message(
            user_id=user_id,
            message=data.message,
            channel_type=data.channel_type,
            history=data.history,
        )
        return ChatResponse(**result)
    except RuntimeError as e:
        if "LLM disabled" in str(e):
            return ChatResponse(
                response="Извините, AI-ассистент временно отключен.",
                evaluation={"score": 1.0, "checks": {}, "warnings": []},
                facts_stored=0,
            )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthCheck)
async def llm_health_check() -> HealthCheck:
    """Проверка здоровья LLM-интеграции (провайдер, флаг, инициализация).

    По этим данным фронтенд решает, показывать ли поле ввода чата.
    """
    llm_service = LLMService()
    info = llm_service.get_provider_info()
    return HealthCheck(
        provider=info["provider"],
        enabled=info["enabled"],
        initialized=info["initialized"],
    )


@router.post("/evaluate")
async def evaluate_response(
    response: str,
    context: str | None = None,
) -> dict[str, Any]:
    """
    Отдельная оценка готового ответа (без генерации).

    Ленивый импорт ResponseEvaluator: тяжёлая модель подтягивается только
    когда фича реально используется, чтобы не нагружать процесс при старте.
    Нужен, когда ответ сгенерирован другим каналом, а оценку хочется получить
    тем же механизмом, что и в чате.

    Args:
        response: Текст ответа для оценки.
        context: Исходный контекст (сообщение пользователя).

    Returns:
        Результат оценки ответа.
    """
    from backend.src.services.response_evaluator import ResponseEvaluator
    evaluator = ResponseEvaluator()
    return await evaluator.evaluate(response=response, context=context)

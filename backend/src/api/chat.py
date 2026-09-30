"""
Chat Router
API endpoints for chat and response generation (Phase C.3.1).
Thin router — all logic in ChatService.
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
    """Chat request schema."""
    message: str
    channel_type: str = "text"
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    """Chat response schema."""
    response: str
    evaluation: dict[str, Any]
    facts_stored: int


class HealthCheck(BaseModel):
    """LLM health check schema."""
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
    Send message and get AI response.
    C.3.1: Delegates to ChatService.
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
    """Check LLM service health."""
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
    """Evaluate a response."""
    from backend.src.services.response_evaluator import ResponseEvaluator
    evaluator = ResponseEvaluator()
    return await evaluator.evaluate(response=response, context=context)

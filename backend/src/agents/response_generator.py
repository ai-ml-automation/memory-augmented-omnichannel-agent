"""
Агент генерации персонализированных ответов (этап D.2.4).

Назначение: собрать контекст из памяти и историю диалога, сформировать
промпт и получить ответ LLM; при недоступности LLM — честный fallback.
Почему память ищется отдельным сервисом: поиск релевантных фактов
(векторный + графовый) — отдельная задача, генератору нужен уже готовый
контекст-блок, а не сырые факты.
Почему fallback встроен в генератор: диалог не должен обрываться из-за
сбоя LLM — пользователю всегда приходит ответ, помеченный fallback=True.

Конвейер: build_prompt -> call_llm -> fallback.
"""

import logging
import uuid as uuid_mod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.services.llm_service import LLMService
from backend.src.services.memory_search_service import MemorySearchService

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "\u0422\u044b - \u043f\u043e\u043b\u0435\u0437\u043d\u044b\u0439 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0439 "
    "\u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442.\n"
    "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e "
    "\u0438\u0437 \u043f\u0430\u043c\u044f\u0442\u0438 \u0434\u043b\u044f \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438 \u043e\u0442\u0432\u0435\u0442\u0430.\n"
    "\u041d\u0435 \u0443\u043f\u043e\u043c\u0438\u043d\u0430\u0439, \u0447\u0442\u043e \u0442\u044b \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0448\u044c "
    "\u043f\u0430\u043c\u044f\u0442\u044c - \u043f\u0440\u043e\u0441\u0442\u043e \u043e\u0442\u0432\u0435\u0447\u0430\u0439 \u0435\u0441\u0442\u0435\u0441\u0442\u0435\u0441\u0442\u043d\u043e.\n"
    "\n"
    "\u0415\u0441\u043b\u0438 \u0443 \u0442\u0435\u0431\u044f \u043d\u0435\u0442 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u0438 "
    "\u0434\u043b\u044f \u043e\u0442\u0432\u0435\u0442\u0430, \u0441\u043a\u0430\u0436\u0438 \u043e\u0431 \u044d\u0442\u043e\u043c \u0447\u0435\u0441\u0442\u043d\u043e."
)

FALLBACK_RESPONSE = (
    "\u0418\u0437\u0432\u0438\u043d\u0438\u0442\u0435, \u044f \u043f\u043e\u043a\u0430 \u043d\u0435 \u043c\u043e\u0433\u0443 "
    "\u043e\u0442\u0432\u0435\u0442\u0438\u0442\u044c \u043d\u0430 \u044d\u0442\u043e\u0442 \u0432\u043e\u043f\u0440\u043e\u0441. "
    "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435."
)


class ResponseGeneratorAgent:
    """
    Агент генерации ответов (D.2.4).

    Собирает контекст памяти (до 5 фактов), историю диалога и зовёт LLM.
    Персонализация не упоминается в ответе явно — системный промпт
    запрещает говорить «я использовал твою память», иначе ассистент
    выглядит искусственным.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LLMService()
        self.memory_search = MemorySearchService(db)

    async def generate(
        self,
        user_id: Any,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """
        Сгенерировать персонализированный ответ.

        Почему user_id принимает UUID или str: вызывающий слой (роутеры)
        получает идентификатор из разных источников, и невалидный формат
        не должен ронять диалог — просто не даст контекст памяти.

        Args:
            user_id: Идентификатор пользователя (UUID или строка).
            message: Сообщение пользователя.
            history: Опциональная история диалога.

        Returns:
            {response, context_used, fallback}: ответ, был ли использован
            контекст памяти, и сработал ли fallback.
        """
        # Resolve user_id to UUID
        user_uuid: uuid_mod.UUID | None = None
        if isinstance(user_id, uuid_mod.UUID):
            user_uuid = user_id
        elif isinstance(user_id, str):
            try:
                user_uuid = uuid_mod.UUID(user_id)
            except ValueError:
                user_uuid = None

        # 1. Retrieve memory context
        context = ""
        context_used = False
        if user_uuid:
            try:
                context = await self.memory_search.get_memory_context(
                    user_id=user_uuid,
                    current_message=message,
                    max_facts=5,
                )
                context_used = bool(context)
            except Exception as e:
                logger.warning("Memory search failed: %s", e)

        # 2. Build prompt
        prompt = self._build_prompt(message, context, history)

        # 3. Call LLM or fallback
        if settings.ENABLE_LLM:
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    max_tokens=1000,
                    temperature=0.7,
                )
                return {
                    "response": response,
                    "context_used": context_used,
                    "fallback": False,
                }
            except Exception as e:
                logger.error("LLM generation failed: %s", e)

        # 4. Fallback
        return {
            "response": FALLBACK_RESPONSE,
            "context_used": False,
            "fallback": True,
        }

    def _build_prompt(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Собрать промпт из системной части, контекста памяти и истории.

        Почему история ограничена 10 сообщениями: длинный контекст
        размывает внимание LLM и дороже по токенам; для персонализации
        хватает ближайшего отрезка диалога.
        """
        parts = [SYSTEM_PROMPT, ""]

        if context:
            parts.append(context)
            parts.append("")

        if history:
            parts.append("\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u0434\u0438\u0430\u043b\u043e\u0433\u0430:")
            for msg in history[-10:]:  # Last 10 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")
            parts.append("")

        parts.append(f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c: {message}")
        parts.append("\u041e\u0442\u0432\u0435\u0442:")

        return "\n".join(parts)

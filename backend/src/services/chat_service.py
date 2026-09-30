"""
Оркестрация текстового чат-сценария (Phase C.3.1): сообщение → ответ.

Конвейер: сборка промпта (PromptBuilder) → генерация ответа (LLMService) →
оценка качества (ResponseEvaluator) → сохранение извлечённых фактов
(Mem0MemoryService).

Ключевые решения:
- отдельный сервис, а не логика в роутере: чат-сценарий переиспользуется
  из API, вебхуков и голосового сценария;
- факты сохраняются только после проверки качества ответа — это защищает
  долговременную память от мусора и токсичных ответов;
- при отключённом LLM (RuntimeError "LLM disabled") возвращается вежливый
  отказ, а не ошибка 500.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.llm_service import LLMService
from backend.src.services.mem0_memory_service import Mem0MemoryService
from backend.src.services.prompt_builder import PromptBuilder
from backend.src.services.response_evaluator import ResponseEvaluator

logger = logging.getLogger(__name__)


class ChatService:
    """
    Главный сервис текстового чата: собирает конвейер ответа из зависимостей.

    Жизненный цикл: создаётся с сессией БД на время обработки запроса; держит
    композицию PromptBuilder, LLMService, ResponseEvaluator, Mem0MemoryService.

    Почему так: единая точка оркестрации позволяет API, вебхукам и тестам
    вызывать один и тот же сценарий, не дублируя порядок шагов.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Создание сервиса с заданной сессией БД.

        Компоненты конвейера создаются один раз на запрос: сервис не хранит
        состояние между вызовами send_message (одна сессия = один диалог).
        """
        self.db = db
        self.prompt_builder = PromptBuilder(db)
        self.llm_service = LLMService()
        self.evaluator = ResponseEvaluator()
        self.memory = Mem0MemoryService(db)

    async def send_message(
        self,
        user_id: uuid.UUID,
        message: str,
        channel_type: str = "text",
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """
        Обработка сообщения пользователя: промпт → LLM → оценка → сохранение фактов.

        Порядок шагов фиксирован: сначала оценка качества (ResponseEvaluator), и только
        при прохождении порога факты сохраняются в память — мусорные ответы не должны
        загрязнять долговременную память пользователя.

        Args:
            user_id: владелец диалога и фактов
            message: текст сообщения
            channel_type: тип канала (text/voice) — влияет на промпт
            history: история диалога; при передаче промпт строится с контекстом

        Returns:
            dict: response, evaluation, facts_stored

        Raises:
            RuntimeError: сбой LLM, кроме "LLM disabled" (возвращается отказ)
        """
        try:
            # 1. Build prompt
            if history:
                messages = await self.prompt_builder.build_prompt_with_history(
                    user_id=user_id,
                    message=message,
                    history=history,
                    channel_type=channel_type,
                )
            else:
                messages = await self.prompt_builder.build_prompt(
                    user_id=user_id,
                    message=message,
                    channel_type=channel_type,
                )

            # 2. Generate response
            prompt_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in messages
            )
            response = await self.llm_service.generate(
                prompt=prompt_text,
                max_tokens=1000,
                temperature=0.7,
            )

            # 3. Evaluate response
            evaluation = await self.evaluator.evaluate(
                response=response,
                context=message,
            )

            # 4. Store facts if applicable
            facts_stored = 0
            if await self.evaluator.should_store_fact(response, evaluation):
                extracted_facts = self.prompt_builder.extract_facts_from_response(response)
                for fact_data in extracted_facts:
                    await self.memory.store_fact(
                        user_id=user_id,
                        fact_type=fact_data.get("type", "intent"),
                        value=fact_data.get("content", ""),
                        channel=channel_type,
                        weight=fact_data.get("weight", 1.0),
                    )
                    facts_stored += 1

            return {
                "response": response,
                "evaluation": evaluation,
                "facts_stored": facts_stored,
            }

        except RuntimeError as e:
            if "LLM disabled" in str(e):
                return {
                    "response": "Извините, AI-ассистент временно отключен.",
                    "evaluation": {"score": 1.0, "checks": {}, "warnings": []},
                    "facts_stored": 0,
                }
            raise

    def get_llm_info(self) -> dict[str, Any]:
        """
        Текущий провайдер LLM и его статус.

        Используется API/health-эндпоинтами для диагностики: позволяет узнать,
        какой из каскадных провайдеров (YandexGPT/vLLM/GigaChat) активен,
        не вызывая генерацию.

        Returns:
            dict: сведения о провайдере от LLMService.get_provider_info
        """
        return self.llm_service.get_provider_info()

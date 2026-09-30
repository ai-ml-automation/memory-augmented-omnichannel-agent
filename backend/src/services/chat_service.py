"""
Chat Service
Business logic for chat and response generation (Phase C.3.1).
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
    """Service for chat and response generation (Phase C.3.1)."""

    def __init__(self, db: AsyncSession) -> None:
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
        Process chat message: build prompt -> LLM -> evaluate -> store facts.

        Returns:
            Dict with response, evaluation, facts_stored
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
        """Get LLM provider info."""
        return self.llm_service.get_provider_info()

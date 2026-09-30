"""
Prompt Builder
Constructs prompts with context and memory for LLM
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.services.memory_search_service import MemorySearchService

logger = logging.getLogger(__name__)
settings = get_settings()


class PromptBuilder:
    """
    Builds prompts for LLM with context from memory.

    Components:
    - System prompt (role, constraints)
    - User context (name, preferences)
    - Memory context (relevant facts)
    - Current message
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_search = MemorySearchService(db)

    async def build_prompt(
        self,
        user_id: uuid.UUID,
        message: str,
        channel_type: str = "text",
        max_memory_facts: int = 5,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        """
        Build complete prompt for LLM.

        Args:
            user_id: User identifier
            message: User's message
            channel_type: Channel type
            max_memory_facts: Maximum memory facts to include

        Returns:
            List of message dicts for LLM
        """
        messages = []

        # 1. System prompt
        system_prompt = self._build_system_prompt(channel_type)
        messages.append({"role": "system", "content": system_prompt})

        # 2. Memory context
        memory_context = await self.memory_search.get_memory_context(
            user_id=user_id,
            current_message=message,
            max_facts=max_memory_facts,
        )

        if memory_context:
            messages.append({
                "role": "system",
                "content": f"Контекст из памяти:\n{memory_context}",
            })

        # 3. User message
        messages.append({"role": "user", "content": message})

        return messages

    def _build_system_prompt(self, channel_type: str) -> str:
        """
        Build system prompt.

        Args:
            channel_type: Channel type

        Returns:
            System prompt string
        """
        base_prompt = """Вы - полезный ассистент компании. 
Отвечайте на русском языке. Будьте вежливы и помогайте пользователю.

Правила:
1. Используйте информацию из контекста памяти для персонализации
2. Не разглашайте персональные данные других пользователей
3. Если не знаете ответ - честно скажите
4. Соблюдайте 152-ФЗ о персональных данных"""

        # Add channel-specific instructions
        if channel_type == "VOICE":
            base_prompt += "\n5. Отвечайте кратко для озвучки"
        elif channel_type in ["MAX", "TG", "VK"]:
            base_prompt += "\n5. Используйте эмодзи умеренно"

        return base_prompt

    async def build_prompt_with_history(
        self,
        user_id: uuid.UUID,
        message: str,
        history: list[dict[str, str]],
        channel_type: str = "text",
        max_history: int = 10,
        max_memory_facts: int = 5,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        """
        Build prompt with conversation history.

        Args:
            user_id: User identifier
            message: Current message
            history: Conversation history
            channel_type: Channel type
            max_history: Maximum history messages
            max_memory_facts: Maximum memory facts

        Returns:
            List of message dicts
        """
        messages = []

        # 1. System prompt
        system_prompt = self._build_system_prompt(channel_type)
        messages.append({"role": "system", "content": system_prompt})

        # 2. Memory context
        memory_context = await self.memory_search.get_memory_context(
            user_id=user_id,
            current_message=message,
            max_facts=max_memory_facts,
        )

        if memory_context:
            messages.append({
                "role": "system",
                "content": f"Контекст из памяти:\n{memory_context}",
            })

        # 3. Conversation history (limited)
        for entry in history[-max_history:]:
            messages.append({
                "role": entry.get("role", "user"),
                "content": entry.get("content", ""),
            })

        # 4. Current message
        messages.append({"role": "user", "content": message})

        return messages

    def extract_facts_from_response(
        self,
        response: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Extract potential facts from LLM response.

        This is a simple heuristic; will be enhanced with LLM in Phase 4.3.

        Args:
            response: LLM response text

        Returns:
            List of potential facts
        """
        facts = []

        # Simple extraction: sentences that might contain user info
        sentences = response.split(".")

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Look for patterns suggesting user info
            lower = sentence.lower()
            if any(
                keyword in lower
                for keyword in ["ваш", "ваша", "ваше", "вас", "вам"]
            ):
                facts.append({
                    "content": sentence,
                    "category": "interaction",
                    "confidence": 0.5,
                })

        return facts

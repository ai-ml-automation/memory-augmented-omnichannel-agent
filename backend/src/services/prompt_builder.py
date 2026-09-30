"""
Построитель промптов для LLM с контекстом из памяти пользователя.

Формирует последовательность сообщений: системный промпт, контекст из памяти
(релевантные факты), историю диалога и текущее сообщение. Здесь память
превращается в контекст диалога.

Ключевые решения:
- контекст памяти идёт системным сообщением — LLM воспринимает факты как данность;
- системный промпт зависит от канала (голос — кратко, мессенджеры — эмодзи):
  формат ответа должен соответствовать каналу омниканальности;
- извлечение фактов из ответа — эвристика без LLM-разбора: экономит токены.

@see memory_search_service, LLMService
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
    Сборка промптов для LLM с контекстом из памяти.

    Ответственность: превратить идентификатор пользователя и его сообщение
    в полный набор сообщений для LLM, обогащённый фактами из памяти.

    Жизненный цикл: создаётся на каждый запрос (или переиспользуется
    в рамках обработчика); внутри держит MemorySearchService для выборки
    релевантных фактов.

    Почему отдельный класс: сборка промпта — это бизнес-правило (что и как
    показывать LLM), а не деталь LLM-клиента; разделение позволяет тестировать
    сборку без реального LLM и менять формат промпта независимо от провайдера.

    Компоненты: системный промпт, контекст памяти, история, текущее сообщение.

    @see LLMService, MemorySearchService
    """

    def __init__(self, db: AsyncSession):
        """
        Инициализация построителя промптов.

        Принимает асинхронную сессию БД и создаёт MemorySearchService:
        выборка контекста памяти выполняется тем же экземпляром сессии,
        чтобы не плодить подключения и не ломать транзакцию вызывающего кода.

        Args:
            db: асинхронная сессия SQLAlchemy
        """
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
        Сборка полного промпта для LLM.

        Порядок сообщений важен: системный промпт и контекст памяти идут до
        сообщения пользователя, чтобы LLM использовал факты как данность
        при генерации ответа. Контекст памяти запрашивается асинхронно
        через MemorySearchService (гибридный поиск) — см. get_memory_context.

        Args:
            user_id: идентификатор пользователя
            message: сообщение пользователя
            channel_type: тип канала (влияет на системный промпт)
            max_memory_facts: максимум фактов памяти в контексте

        Returns:
            список dict с ключами role и content для LLM
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
        Сборка системного промпта с правилами ассистента.

        Правила зашиты в промпт, а не в код: менять поведение ассистента
        (персонализация, 152-ФЗ, тон ответа) можно без релиза приложения.
        Канал добавляет своё правило: голос требует кратких ответов
        для озвучки, мессенджеры допускают умеренные эмодзи.

        Args:
            channel_type: тип канала (text, VOICE, MAX, TG, VK)

        Returns:
            строка системного промпта
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
        Сборка промпта с историей диалога.

        История ограничивается последними max_history сообщениями: полная
        история не помещается в контекст LLM и размывает внимание модели.
        Сообщения истории добавляются в исходном порядке, чтобы модель
        сохранила причинно-следственную цепочку диалога; текущее сообщение
        пользователя идёт последним.

        Args:
            user_id: идентификатор пользователя
            message: текущее сообщение пользователя
            history: история диалога (список dict role/content)
            channel_type: тип канала
            max_history: максимум сообщений истории
            max_memory_facts: максимум фактов памяти в контексте

        Returns:
            список dict с ключами role и content для LLM
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
        Извлечение потенциальных фактов из ответа LLM.

        Простая эвристика: предложения с обращениями «ваш/ваша/вас/вам»
        считаются фактами об интеракции (категория interaction, уверенность
        0.5). Почему эвристика, а не LLM-разбор: бесплатный способ собрать
        факты без доп. вызовов LLM; точность повышается в более поздних
        фазах (планировался LLM-разбор в Phase 4.3).

        Args:
            response: текст ответа LLM

        Returns:
            список потенциальных фактов (dict: content, category, confidence)
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

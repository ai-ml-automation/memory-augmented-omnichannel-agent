"""
Единый обработчик входящих сообщений из всех каналов (MAX/TG/VK/VOICE).

Конвейер: идентификация пользователя по привязке канала → проверка согласия
(152-ФЗ) → обработка с учётом памяти → аудит действия.

Ключевые решения:
- один класс на все каналы: логика идентификации и consent-гейта не дублируется
  в каждом вебхуке;
- согласие проверяется ДО обработки — сообщения без согласия не анализируются
  и не сохраняются (152-ФЗ);
- каждое обработанное сообщение аудируется (AuditService) для следов
  регуляторных проверок.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.models import User
from backend.src.services.audit_service import AuditService
from backend.src.services.channel_binding_service import ChannelBindingService
from backend.src.services.consent_service import ConsentService

logger = logging.getLogger(__name__)
settings = get_settings()


class MessageHandler:
    """
    Единый обработчик входящих сообщений каналов.

    Жизненный цикл: создаётся с сессией БД на время запроса; для каждого
    сообщения выполняет идентификацию → проверку согласия → обработку → аудит.

    Почему единый: все каналы (MAX/TG/VK/VOICE) приходят в один pipeline,
    что гарантирует одинаковое соблюдение 152-ФЗ (consent-гейт и аудит)
    независимо от источника сообщения.

    Композиция: ChannelBindingService (идентификация), ConsentService (согласие),
    AuditService (журнал действий).
    """

    def __init__(self, db: AsyncSession):
        """
        Создание обработчика с сессией БД.

        Сервисы-зависимости создаются один раз на запрос; все они работают
        с одной транзакцией БД (db), что важно для согласованности аудита.
        """
        self.db = db
        self.binding_service = ChannelBindingService(db)
        self.consent_service = ConsentService(db)
        self.audit_service = AuditService(db)

    async def handle_message(
        self,
        channel_type: str,
        external_id: str,
        text: str,
        **kwargs: Any,
    ) -> str:
        """
        Обработка входящего сообщения канала.

        Порядок критичен для 152-ФЗ: незнакомый пользователь получает предложение
        зарегистрироваться, пользователь без активного согласия — отказ; только
        после прохождения обоих гейтов сообщение обрабатывается и аудируется.

        Args:
            channel_type: тип канала (MAX, TG, VK, VOICE)
            external_id: идентификатор пользователя в канале
            text: текст сообщения
            **kwargs: дополнительный контекст (например, голосовая метадата)

        Returns:
            текст ответа для отправки в канал
        """
        # 1. Identify user
        user = await self.binding_service.find_user_by_channel(
            channel_type=channel_type,
            external_id=external_id,
        )

        if not user:
            return await self._handle_unknown_user(channel_type, external_id)

        # 2. Check consent (152-FZ)
        has_consent = await self.consent_service.has_active_consent(
            user_id=user.id,
        )

        if not has_consent:
            return await self._handle_no_consent(user)

        # 3. Process message (placeholder for AI pipeline)
        response = await self._process_with_memory(
            user=user,
            text=text,
            **kwargs,
        )

        # 4. Audit log
        await self.audit_service.log_action(
            user_id=user.id,
            action="READ",
            source=channel_type,
        )

        return response

    async def _handle_unknown_user(
        self,
        channel_type: str,
        external_id: str,
    ) -> str:
        """
        Ответ незнакомому пользователю канала.

        Почему отказ, а не создание пользователя: авторизация выполняется только
        через веб-интерфейс (осознанное согласие 152-ФЗ), поэтому сообщения из
        каналов без привязки не порождают персональные данные.

        Args:
            channel_type: тип канала для логирования
            external_id: идентификатор пользователя в канале для логирования

        Returns:
            текст с инструкцией зарегистрироваться
        """
        logger.info(
            f"Unknown user: {channel_type}:{external_id}"
        )
        return (
            "Для использования бота необходимо зарегистрироваться "
            "через веб-интерфейс."
        )

    async def _handle_no_consent(self, user: User) -> str:
        """
        Ответ пользователю без активного согласия.

        Согласие — обязательное условие обработки персональных данных (152-ФЗ),
        поэтому сообщение НЕ анализируется и НЕ сохраняется; фиксируется warning
        в лог для администратора.

        Args:
            user: пользователь без согласия (используется только id)

        Returns:
            текст с требованием дать согласие
        """
        logger.warning(
            f"User {user.id} has no active consent"
        )
        return (
            "Для обработки сообщений необходимо дать согласие "
            "на обработку персональных данных."
        )

    async def _process_with_memory(
        self,
        user: User,
        text: str,
        **kwargs: Any,
    ) -> str:
        """
        Обработка сообщения с контекстом памяти (заглушка AI-конвейера).

        Место для интеграции (Phase 3–4): поиск фактов в памяти, сборка контекста,
        генерация ответа LLM и сохранение новых фактов. Сейчас возвращает эхо-ответ,
        чтобы каналы могли работать без зависимостей от ML-компонент.

        Почему заглушка, а не сразу полный конвейер: сервис разворачивается и
        тестируется без LLM (см. ENABLE_LLM), текстовые и голосовые сценарии
        подключаются к реальному конвейеру через ChatService/VoiceService.

        Args:
            user: идентифицированный пользователь
            text: текст сообщения
            **kwargs: дополнительный контекст

        Returns:
            текст ответа
        """
        # TODO: Integrate with memory service (Phase 3)
        # TODO: Integrate with LLM service (Phase 4)
        logger.info(f"Processing message for user {user.id}")

        return f"Обработка сообщения: {text}"


def register_default_handler() -> None:
    """
    Регистрация обработчика по умолчанию для всех каналов.

    Вызывается при инициализации приложения, чтобы у роутера (MessageRouter)
    всегда был fallback-хендлер до подключения канальных обработчиков.

    Почему пустая: конкретные каналы регистрируют свои обработчики отдельно,
    функция оставлена как точка расширения для инициализации.
    """
    # This will be called during app initialization
    pass

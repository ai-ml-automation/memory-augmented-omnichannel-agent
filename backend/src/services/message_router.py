"""
Роутер входящих сообщений: выбор обработчика по типу канала.

Реестр обработчиков (dict channel_type → async handler) позволяет вебхукам
MAX/TG/VK/VOICE делегировать сообщение нужному сценарию без ветвлений
в каждом эндпоинте.

Ключевые решения:
- ключ канала нормализуется в верхний регистр — каналы и настройки передают
  тип в разном регистре;
- идентификация пользователя выполняется до вызова обработчика: обработчики
  получают уже известный user_id;
- сбой обработчика не роняет канал — возвращается безопасный текст ошибки.
"""

import logging
from typing import Any, Callable, Coroutine

from backend.src.config import get_settings
from backend.src.services.channel_binding_service import ChannelBindingService

logger = logging.getLogger(__name__)
settings = get_settings()


class MessageRouter:
    """
    Маршрутизация сообщений по типу канала.

    Жизненный цикл: реестр наполняется при старте приложения (register_handler),
    каждый входящий запрос проходит route_message.

    Почему реестр вместо if/elif: добавление нового канала — это один вызов
    register_handler, без правки роутера; обработчик изолирован и тестируем отдельно.

    Поток: идентификация пользователя (ChannelBindingService) → вызов обработчика
    с user_id → ответ каналу.
    """

    def __init__(self):
        """
        Пустой реестр обработчиков.

        Наполняется регистрацией через register_handler; хранит только обработчики
        с ключом в верхнем регистре (нормализация выполняется при регистрации).
        """
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, str]]] = {}

    def register_handler(
        self,
        channel_type: str,
        handler: Callable[..., Coroutine[Any, Any, str]],
    ) -> None:
        """
        Регистрация асинхронного обработчика для типа канала.

        Ключ приводится к верхнему регистру: вебхуки и конфигурация могут
        передавать тип в разном регистре, а маршрутизация (route_message)
        использует ту же нормализацию.

        Args:
            channel_type: тип канала (MAX, TG, VK, VOICE)
            handler: корутина-обработчик, принимающая user_id и text
        """
        self._handlers[channel_type.upper()] = handler
        logger.info(f"Registered handler for channel: {channel_type}")

    async def route_message(
        self,
        channel_type: str,
        external_id: str,
        text: str,
        binding_service: ChannelBindingService,
        **kwargs: Any,
    ) -> str:
        """
        Маршрутизация сообщения в зарегистрированный обработчик.

        Сначала идентифицируется пользователь: без привязки канала возвращается
        отказ (152-ФЗ — данные без регистрации не обрабатываются). Исключения
        обработчика превращаются в безопасный текст — канал не падает.

        Args:
            channel_type: тип канала (ключ реестра)
            external_id: идентификатор пользователя в канале
            text: текст сообщения
            binding_service: сервис поиска пользователя по привязке
            **kwargs: доп. контекст, передаётся в обработчик

        Returns:
            текст ответа
        Raises:
            ValueError: если для типа канала не зарегистрирован обработчик
        """
        handler = self._handlers.get(channel_type.upper())

        if not handler:
            raise ValueError(f"No handler registered for channel: {channel_type}")

        # Identify user
        user = await binding_service.find_user_by_channel(
            channel_type=channel_type,
            external_id=external_id,
        )

        if not user:
            logger.warning(
                f"No user found for {channel_type}:{external_id}"
            )
            return "Для использования бота необходимо зарегистрироваться через веб-интерфейс."

        # Route to handler
        try:
            response = await handler(
                user_id=user.id,
                text=text,
                **kwargs,
            )
            return response
        except Exception as e:
            logger.error(f"Handler error for {channel_type}: {e}")
            return "Произошла ошибка при обработке сообщения."

    def get_registered_channels(self) -> list[str]:
        """
        Список зарегистрированных типов каналов.

        Используется для диагностики и health-проверок: показывает, какие
        каналы реально подключены (ключи в верхнем регистре).

        Returns:
            list[str]: типы каналов реестра
        """
        return list(self._handlers.keys())


# Default message router instance
message_router = MessageRouter()

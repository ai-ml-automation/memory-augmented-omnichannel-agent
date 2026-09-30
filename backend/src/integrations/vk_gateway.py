"""
Шлюз VK (интеграция через vk_api, Callback API).

Назначение: единая точка общения с VK — отправка исходящих сообщений
и нормализация входящих событий Callback API.
Почему vk_api-сессия ленивая: библиотека и токен доступа нужны только
при реальной отправке, тяжёлая инициализация не задерживает старт.
Почему гейт ENABLE_LLM: флаг используется как общий выключатель
внешних интеграций — при его отключении сессия не создаётся.
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VKGateway:
    """
    Шлюз VK (vk_api, Callback API).

    Сессия VkApi создаётся лениво с токеном доступа из настроек.
    Ошибки отправки не пробрасываются наверх: шлюз возвращает False,
    чтобы диалоговый конвейер продолжал работу.
    """

    def __init__(self):
        self._session = None
        self._access_token = settings.VK_ACCESS_TOKEN
        self._group_id = settings.VK_GROUP_ID

    def _get_session(self) -> Any:
        """Ленивая инициализация VK-сессии.

        Почему лениво: vk_api — опциональная зависимость, она
        импортируется только при первой отправке. Отсутствующий пакет
        превращается в RuntimeError с понятным текстом.
        """
        if self._session is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("VK integration disabled (ENABLE_LLM=false)")

            try:
                import vk_api

                self._session = vk_api.VkApi(token=self._access_token)
                logger.info("VK session initialized")
            except ImportError:
                raise RuntimeError("vk_api package not installed")

        return self._session

    async def send_message(
        self,
        user_id: str | int,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """
        Отправить сообщение пользователю VK.

        Почему random_id: VK API требует уникальный идентификатор,
        чтобы не отправлять дубли при сетевых ретраях; по умолчанию 0,
        вызывающий может передать свой. Ключ извлекается из kwargs,
        чтобы не уехать в **{...} как неизвестный параметр.

        Args:
            user_id: Идентификатор пользователя VK.
            message: Текст сообщения.
            **kwargs: Дополнительные параметры.

        Returns:
            True при успешной отправке.
        """
        if not settings.ENABLE_LLM:
            logger.warning("VK integration disabled, skipping send")
            return False

        try:
            session = self._get_session()
            vk = session.get_api()
            vk.messages.send(
                user_id=user_id,
                message=message,
                random_id=kwargs.get("random_id", 0),
                **{k: v for k, v in kwargs.items() if k != "random_id"},
            )
            logger.info(f"Message sent to VK user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send VK message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Разобрать входящий вебхук VK (Callback API).

        Почему обработка и object.message, и самого object: Callback API
        кладёт данные события в поле object, но в части событий это уже
        готовое сообщение — схема должна переживать оба варианта.

        Args:
            data: Сырое событие Callback API от VK.

        Returns:
            Нормализованная схема {channel, external_id, text,
            message_id, timestamp} — единый контракт для message_handler.
        """
        object_data = data.get("object", {})
        message = object_data.get("message", {}) if isinstance(object_data, dict) else object_data

        return {
            "channel": "VK",
            "external_id": str(message.get("user_id", "")),
            "text": message.get("text", ""),
            "message_id": str(message.get("id", "")),
            "timestamp": message.get("date", 0),
        }

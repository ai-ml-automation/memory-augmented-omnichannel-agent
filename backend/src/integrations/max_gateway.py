"""
Шлюз MAX (интеграция через aiomax SDK).

Назначение: единая точка общения с мессенджером MAX — отправка
исходящих сообщений и нормализация входящих вебхуков.
Почему отдельный шлюз, а не общий: у каждого мессенджера своя модель
идентификации отправителя и своя структура вебхука; шлюз прячет эти
отличия за единым контрактом. MAX близок к Telegram по формату
(sender в message), но схема payload своя.
Почему гейт ENABLE_LLM: флаг используется как общий выключатель
внешних интеграций — при его отключении клиент не создаётся.
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MAXGateway:
    """
    Шлюз MAX (aiomax SDK).

    Клиент Bot создаётся лениво — при первом использовании; токен
    берётся из настроек. Ошибки отправки не пробрасываются наверх:
    шлюз возвращает False, чтобы диалоговый конвейер продолжал работу.
    """

    def __init__(self):
        self._client = None
        self._bot_token = settings.MAX_BOT_TOKEN

    def _get_client(self) -> Any:
        """Ленивая инициализация MAX-клиента.

        Почему лениво: aiomax — опциональная зависимость, импортируется
        только при первой отправке. Отсутствующий пакет превращается
        в RuntimeError с понятным текстом.
        """
        if self._client is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("MAX integration disabled (ENABLE_LLM=false)")

            try:
                import aiomax

                self._client = aiomax.Bot(token=self._bot_token)
                logger.info("MAX client initialized")
            except ImportError:
                raise RuntimeError("aiomax package not installed")

        return self._client

    async def send_message(
        self,
        user_external_id: str,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """
        Отправить сообщение пользователю MAX.

        Почему принимает именно внешний идентификатор: MAX-диалог ведётся
        по внешнему id отправителя (chat_id), а не по внутреннему user_id
        системы — маппинг делает channel_binding_service.

        Args:
            user_external_id: Внешний идентификатор пользователя в MAX.
            text: Текст сообщения.
            **kwargs: Дополнительные параметры.

        Returns:
            True при успешной отправке.
        """
        if not settings.ENABLE_LLM:
            logger.warning("MAX integration disabled, skipping send")
            return False

        try:
            client = self._get_client()
            await client.send_message(
                chat_id=user_external_id,
                text=text,
                **kwargs,
            )
            logger.info(f"Message sent to MAX user {user_external_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send MAX message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Разобрать входящий вебхук MAX.

        Почему отправитель берётся из message.sender: в отличие от
        Telegram, где from на уровне message, в MAX отправитель вложен
        в объект sender — нормализация прячет это от обработчика.

        Args:
            data: Сырой вебхук MAX.

        Returns:
            Нормализованная схема {channel, external_id, text,
            message_id, timestamp} — единый контракт для message_handler.
        """
        return {
            "channel": "MAX",
            "external_id": str(data.get("message", {}).get("sender", {}).get("id", "")),
            "text": data.get("message", {}).get("text", ""),
            "message_id": str(data.get("message", {}).get("id", "")),
            "timestamp": data.get("message", {}).get("date", 0),
        }

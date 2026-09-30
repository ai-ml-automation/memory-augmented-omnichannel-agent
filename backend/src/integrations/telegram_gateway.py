"""
Шлюз Telegram (интеграция через aiogram 3.x).

Назначение: единая точка общения с Telegram Bot API — отправка
исходящих сообщений и нормализация входящих вебхуков.
Почему отдельный класс-обёртка: aiogram — толстая зависимость, и она
должна оставаться опциональной (не грузиться при старте приложения);
код диалога при этом работает с простым контрактом send/get_webhook_data.
Почему гейт ENABLE_LLM: флаг используется как общий выключатель
внешних интеграций — при его отключении бот не инициализируется.
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramGateway:
    """
    Шлюз Telegram (aiogram 3.x).

    Клиент Bot создаётся лениво — при первом использовании; токен
    берётся из настроек. Ошибки отправки не пробрасываются наверх:
    шлюз возвращает False, чтобы диалоговый конвейер продолжал работу.
    """

    def __init__(self):
        self._bot = None
        self._bot_token = settings.TELEGRAM_BOT_TOKEN

    def _get_bot(self) -> Any:
        """Ленивая инициализация Telegram-бота.

        Почему лениво: aiogram тянет тяжёлые зависимости, и клиент
        создаётся только когда реально нужно отправить сообщение.
        Отсутствующий пакет превращается в RuntimeError с понятным
        текстом, а не голый ImportError.
        """
        if self._bot is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("Telegram integration disabled (ENABLE_LLM=false)")

            try:
                from aiogram import Bot

                self._bot = Bot(token=self._bot_token)
                logger.info("Telegram bot initialized")
            except ImportError:
                raise RuntimeError("aiogram package not installed")

        return self._bot

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """
        Отправить сообщение в Telegram-чат.

        Почему возвращает bool, а не бросает: сбой отправки не должен
        останавливать диалог — вызывающий конвейер решает, что делать
        с недоставленным сообщением (лог, retry, fallback-канал).

        Args:
            chat_id: Идентификатор чата.
            text: Текст сообщения.
            **kwargs: Дополнительные параметры aiogram (parse_mode и т.п.).

        Returns:
            True при успешной отправке.
        """
        if not settings.ENABLE_LLM:
            logger.warning("Telegram integration disabled, skipping send")
            return False

        try:
            bot = self._get_bot()
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs,
            )
            logger.info(f"Message sent to Telegram chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def get_webhook_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Разобрать входящий вебхук Telegram (Update).

        Почему обрабатывается и edited_message: пользователь часто
        правит сообщение, и правка должна доезжать до обработчика —
        иначе агент отвечает на устаревший текст.

        Args:
            data: Сырой объект Update от Telegram.

        Returns:
            Нормализованная схема {channel, external_id, text,
            message_id, timestamp, username, first_name} — единый
            контракт для message_handler по всем каналам.
        """
        message = data.get("message", {}) or data.get("edited_message", {})
        from_user = message.get("from", {})

        return {
            "channel": "TG",
            "external_id": str(from_user.get("id", "")),
            "text": message.get("text", ""),
            "message_id": str(message.get("message_id", "")),
            "timestamp": message.get("date", 0),
            "username": from_user.get("username", ""),
            "first_name": from_user.get("first_name", ""),
        }

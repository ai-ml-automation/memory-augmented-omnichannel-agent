"""
Асинхронная обработка входящих сообщений через Celery.

Webhook-роутеры отвечают клиенту 200 OK сразу (fire-and-forget), а тяжёлый
конвейер MessageHandler (идентификация → consent-гейт 152-ФЗ → память → аудит)
выполняется здесь, в фоне, отдельным воркером. Это развязывает время ответа
мессенджера (Telegram/VK ждут быстрый ACK) и время обработки.

Ключевые решения:
- Celery, а не asyncio-таск-менеджер: задачи переживают рестарт API-процесса
  и могут ретраиться; webhook не блокируется обработкой;
- синхронная задача + asyncio.run: Celery не вызывает asyncio-корутины нативно,
  поэтому внутренний пайплайн запускается через asyncio.run;
- retry-политика 2 попытки с паузой 30 с: транзиентные сетевые сбои
  (недоступность БД/мессенджера) уходят повторным запуском.
"""

import logging

from backend.src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="backend.src.tasks.message_tasks.process_message",
)
def process_message(
    self,
    channel_type: str,
    external_id: str,
    text: str,
) -> dict:
    """
    Запуск полного конвейера обработки сообщения в фоне.

    Почему задача, а не прямой вызов: вебхук отвечает 200 сразу, а MessageHandler
    выполняет медленные шаги (LLM, память, аудит). Здесь же выполняется коммит
    транзакции — факты и аудит-записи становятся durable после обработки.

    Ретраи: при любом исключении задача перезапускается (max_retries=2, пауза 30 с)
    — типичная причина сбоя транзиентная (сеть, недоступность БД). После исчерпания
    попыток исключение пробрасывается в Celery и видно в логах воркера/Flower.

    Args:
        channel_type: тип канала (TG, VK, MAX, VOICE)
        external_id: внешний идентификатор пользователя в канале
        text: текст входящего сообщения

    Returns:
        dict с ключом ``response`` — ответ, сгенерированный конвейером
    """
    import asyncio
    from backend.src.database import async_session_factory
    from backend.src.services.message_handler import MessageHandler

    async def _process():
        async with async_session_factory() as db:
            handler = MessageHandler(db)
            response = await handler.handle_message(
                channel_type=channel_type,
                external_id=external_id,
                text=text,
            )
            await db.commit()
            return {"response": response}

    try:
        result = asyncio.run(_process())
        logger.info(
            "Processed message from %s:%s",
            channel_type,
            external_id,
        )
        return result
    except Exception as exc:
        logger.error("Message processing failed: %s", exc)
        raise self.retry(exc=exc)

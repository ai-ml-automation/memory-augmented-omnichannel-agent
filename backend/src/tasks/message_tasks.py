"""
Celery tasks for message processing.
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
    Process incoming message asynchronously.

    Dispatched from webhooks — returns 200 OK immediately.
    This task runs the full MessageHandler pipeline in background.

    Args:
        channel_type: Channel type (TG, VK, MAX, VOICE)
        external_id: External user ID
        text: Message text

    Returns:
        Result dict with response text
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

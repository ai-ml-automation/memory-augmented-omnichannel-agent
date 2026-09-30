"""
Фоновая задача извлечения фактов из сообщений (III.4).

Запускается из вебхуков в фоне: LLM-извлечение фактов — операция медленная
и дорогая, её нельзя выполнять в HTTP-обработчике. В отличие от keyword-эвристик,
FactExtractorAgent понимает контекст и возвращает структурированные факты
с типом и весом.

Ключевые решения:
- LLM-извлечение вместо эвристик — III.4: качество фактов, фильтр эмоций;
- анонимизация PII и фильтр эмоций выполняются до записи — 152-ФЗ;
- хранение по одному факту в цикле: сбой одного факта не теряет остальные
  (warning в лог, обработка продолжается).
"""

import logging
import uuid

from backend.src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="backend.src.tasks.fact_tasks.extract_facts",
)
def extract_facts(
    self,
    user_id: str,
    message: str,
    channel: str,
) -> dict:
    """
    LLM-извлечение фактов из сообщения и их сохранение в память.

    Почему задача: вебхук отвечает 200 сразу, а цепочка «LLM-извлечение → фильтр
    эмоций → анонимизация PII → запись» занимает секунды. Факты сохраняются
    по одному — частичный сбой одного факта не прерывает обработку остальных.

    Ретраи: max_retries=3 с паузой 60 с — LLM-провайдеры (YandexGPT/vLLM/GigaChat)
    подвержены транзиентным таймаутам; после исчерпания попыток исключение
    уходит в Celery. Повторный запуск безопасен: дубликаты отсекаются хранилищем.

    Args:
        user_id: идентификатор пользователя (строка, конвертируется в UUID)
        message: текст сообщения для извлечения фактов
        channel: тип канала (TG, VK, MAX, VOICE) — сохраняется с каждым фактом

    Returns:
        dict: ``facts_stored`` — сколько фактов записано, ``facts`` — извлечённые факты
    """
    import asyncio
    from backend.src.database import async_session_factory
    from backend.src.agents.fact_extractor import FactExtractorAgent
    from backend.src.services.mem0_memory_service import Mem0MemoryService

    async def _extract():
        async with async_session_factory() as db:
            # III.4: Use LLM-based FactExtractorAgent
            extractor = FactExtractorAgent()
            facts = await extractor.extract(message)

            # Store extracted facts via MemoryService
            memory = Mem0MemoryService(db)
            stored = 0
            for fact in facts:
                try:
                    await memory.store_fact(
                        user_id=uuid.UUID(user_id),
                        fact_type=fact.get("type", "personal_info"),
                        value=fact.get("content", ""),
                        channel=channel,
                        weight=fact.get("weight", 0.5),
                    )
                    stored += 1
                except Exception as e:
                    logger.warning(
                        "Failed to store fact: %s — %s",
                        e,
                        fact.get("content", "")[:50],
                    )

            await db.commit()
            return {"facts_stored": stored, "facts": facts}

    try:
        result = asyncio.run(_extract())
        logger.info(
            "Extracted %d facts for user %s (LLM-based)",
            result["facts_stored"],
            user_id,
        )
        return result
    except Exception as exc:
        logger.error("Fact extraction failed: %s", exc)
        raise self.retry(exc=exc)

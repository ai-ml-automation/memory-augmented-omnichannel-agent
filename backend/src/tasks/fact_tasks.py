"""
Celery tasks for fact extraction and processing.

III.4: Uses FactExtractorAgent (LLM-based) instead of keyword heuristics.
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
    Async task: extract facts from a message using LLM and store them.

    III.4: Uses FactExtractorAgent (LLM-based extraction) instead of
    keyword heuristics. Pipeline: LLM extract -> filter emotions -> anonymize PII.

    Dispatched from webhooks for background processing.

    Args:
        user_id: User ID string
        message: User message text
        channel: Channel type (TG, VK, MAX, VOICE)

    Returns:
        Result dict with facts_stored count and extracted facts
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

"""
Celery tasks for periodic maintenance (DecayAgent).

III.1: Gradual memory decay — weight decreases by 1% per day
instead of instant supersede at expiry.
"""

import logging
from datetime import datetime

from sqlalchemy import update

from backend.src.celery_app import celery_app

logger = logging.getLogger(__name__)

# III.1: Decay coefficient — weight multiplied by this factor each run
DECAY_FACTOR = 0.99  # 1% weight reduction per day
MIN_WEIGHT = 0.1     # Below this, fact is marked superseded


@celery_app.task(
    name="backend.src.tasks.decay_tasks.run_decay_agent",
)
def run_decay_agent() -> dict:
    """
    Periodic task: gradual memory decay + hard expiry.

    Called every hour via Celery Beat.
    1. Multiplies all active fact weights by DECAY_FACTOR (gradual decay).
    2. Marks facts past expires_at as superseded (hard expiry).
    3. Marks facts with weight < MIN_WEIGHT as superseded.

    Returns:
        Dict with counts of decayed, hard-expired, and soft-expired facts.
    """
    import asyncio
    from backend.src.database import async_session_factory
    from backend.src.models import Fact

    async def _decay():
        async with async_session_factory() as db:
            # 1. III.1: Gradual weight decay for all active facts
            await db.execute(
                update(Fact)
                .where(Fact.is_superseded == False)  # noqa: E712
                .values(weight=Fact.weight * DECAY_FACTOR)
            )

            # 2. Hard expiry: facts past expires_at → superseded
            hard_expired = await db.execute(
                update(Fact)
                .where(
                    Fact.expires_at <= datetime.utcnow(),
                    Fact.is_superseded == False,  # noqa: E712
                )
                .values(is_superseded=True, weight=0.1)
            )

            # 3. Soft expiry: weight decayed below threshold → superseded
            soft_expired = await db.execute(
                update(Fact)
                .where(
                    Fact.weight < MIN_WEIGHT,
                    Fact.is_superseded == False,  # noqa: E712
                )
                .values(is_superseded=True, weight=MIN_WEIGHT)
            )

            await db.commit()

            total_expired = hard_expired.rowcount + soft_expired.rowcount
            logger.info(
                "DecayAgent: hard_expired=%d soft_expired=%d total=%d",
                hard_expired.rowcount,
                soft_expired.rowcount,
                total_expired,
            )
            return {
                "hard_expired": hard_expired.rowcount,
                "soft_expired": soft_expired.rowcount,
                "total_expired": total_expired,
            }

    result = asyncio.run(_decay())
    return result

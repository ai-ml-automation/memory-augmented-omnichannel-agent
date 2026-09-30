"""
Периодическая задача обслуживания памяти: затухание и истечение фактов (III.1).

Запускается Celery Beat каждый час. Реализует постепенное затухание памяти:
вес факта умножается на DECAY_FACTOR (0.99) — потеря 1% в день, вместо
мгновенного вытеснения по истечении срока. Это соответствует III.1: память
«забывается» плавно, а не исчезает целиком.

Ключевые решения:
- три механизма: постепенный decay, жёсткое истечение по expires_at,
  мягкое по MIN_WEIGHT — покрывают старость, срок и низкую значимость;
- одна UPDATE-операция на механизм (пакетно) — без чтения строк в Python;
- задача без bind/retry: идемпотентна (повторное применение не ломает
  состояние) — при сбое безопасно перезапустить вручную.
"""

import logging
from datetime import datetime

from sqlalchemy import update

from backend.src.celery_app import celery_app

logger = logging.getLogger(__name__)

# III.1: коэффициент затухания — вес умножается на него при каждом прогоне (1%/день)
DECAY_FACTOR = 0.99
# Ниже этого порога факт считается забытым — мягкое истечение
MIN_WEIGHT = 0.1


@celery_app.task(
    name="backend.src.tasks.decay_tasks.run_decay_agent",
)
def run_decay_agent() -> dict:
    """
    Применение затухания и истечения ко всем активным фактам.

    Почему пакетными UPDATE, а не построчно: фактов много, цикл в Python
    медленный и создаёт лишнюю нагрузку на БД. Все три шага идемпотентны:
    повторный прогон не ухудшает состояние (вес уже ≤ порога — строка
    не попадает в UPDATE).

    Порядок важен: сначала постепенный decay (все активные), затем жёсткое
    истечение по expires_at, затем мягкое по весу. Истёкший факт помечается
    superseded с весом MIN_WEIGHT, чтобы дальнейший decay его не трогал.

    Returns:
        dict: ``hard_expired`` — истекло по сроку, ``soft_expired`` — по весу,
        ``total_expired`` — сумма (для метрики/лога)
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

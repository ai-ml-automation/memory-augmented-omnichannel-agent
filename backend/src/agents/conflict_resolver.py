"""
Агент разрешения конфликтов фактов (этап D.2.5).

Назначение: когда приходит факт, противоречащий сохранённому, решить,
что сохранить. Почему «поздний перекрывает ранний»: для большинства
фактов о пользователе (предпочтения, контакты) актуально последнее
значение — старые данные устаревают.
Почему окно HITL в 5 минут: если противоречие пришло почти сразу,
это похоже на ошибку ввода или дубль — автоматическое перезаписывание
опасно, нужен человек в цикле (flag_for_review).
Почему метрики: число конфликтов по типу решения (override/keep/hitl)
показывает, насколько агрессивно перезаписывается память.

Правило: later overrides earlier. HITL: конфликты в пределах 5 минут.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from backend.src.metrics import CONFLICTS_DETECTED_TOTAL

logger = logging.getLogger(__name__)

# HITL threshold: conflicts within this window require human review
HITL_THRESHOLD_MINUTES = 5


class ConflictResolverAgent:
    """
    Агент разрешения конфликтов фактов (D.2.5).

    Правило «поздний перекрывает ранний»; при быстрых противоречиях
    (окно HITL) — пометка на ручную проверку вместо автоматической
    перезаписи, чтобы не потерять данные из-за ошибочного ввода.
    """

    def __init__(self) -> None:
        self.hitl_threshold = timedelta(minutes=HITL_THRESHOLD_MINUTES)

    def resolve(
        self,
        existing_fact: dict[str, Any],
        new_fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Разрешить конфликт между сохранённым и новым фактом.

        Правила:
        1. Разница во времени > 5 минут: поздний перекрывает ранний.
        2. Разница <= 5 минут: пометка на HITL (flag_for_review).
        3. Время недоступно: решение по весу (новый с большим весом
           перекрывает) — время важнее веса, но вес — честный фолбэк.

        Args:
            existing_fact: Текущий факт {created_at, content, weight}.
            new_fact: Новый факт {created_at, content, weight}.

        Returns:
            {action, fact, requires_hitl, reason}: действие, выбранный
            факт, нужен ли HITL и обоснование.
        """
        existing_time = self._parse_time(existing_fact.get("created_at"))
        new_time = self._parse_time(new_fact.get("created_at"))

        if existing_time is None or new_time is None:
            # Cannot determine time - use weight as tiebreaker
            return self._resolve_by_weight(existing_fact, new_fact)

        time_diff = abs(new_time - existing_time)

        if time_diff > self.hitl_threshold:
            # Later overrides earlier
            if new_time > existing_time:
                logger.info(
                    "Conflict resolved: new fact overrides existing (delta=%s)",
                    time_diff,
                )
                CONFLICTS_DETECTED_TOTAL.labels(resolution="override").inc()
                return {
                    "action": "override",
                    "fact": new_fact,
                    "requires_hitl": False,
                    "reason": f"Newer fact (delta={time_diff})",
                }
            else:
                logger.info(
                    "Conflict resolved: existing fact kept (delta=%s)",
                    time_diff,
                )
                CONFLICTS_DETECTED_TOTAL.labels(resolution="keep_existing").inc()
                return {
                    "action": "keep_existing",
                    "fact": existing_fact,
                    "requires_hitl": False,
                    "reason": f"Existing fact is newer (delta={time_diff})",
                }
        else:
            # Within threshold - HITL required
            logger.warning(
                "Conflict requires HITL review (delta=%s < threshold=%s)",
                time_diff,
                self.hitl_threshold,
            )
            CONFLICTS_DETECTED_TOTAL.labels(resolution="hitl_required").inc()
            return {
                "action": "flag_for_review",
                "fact": existing_fact,
                "new_fact": new_fact,
                "requires_hitl": True,
                "reason": f"Conflicts within {time_diff}, HITL required",
            }

    def _resolve_by_weight(
        self,
        existing_fact: dict[str, Any],
        new_fact: dict[str, Any],
    ) -> dict[str, Any]:
        """Разрешить по весу, когда время недоступно.

        Почему вес: при отсутствии created_at нет объективного критерия
        свежести, и единственный доступный сигнал важности — weight,
        заданный на этапе извлечения фактов.
        """
        existing_weight = existing_fact.get("weight", 0.5)
        new_weight = new_fact.get("weight", 0.5)

        if new_weight > existing_weight:
            return {
                "action": "override",
                "fact": new_fact,
                "requires_hitl": False,
                "reason": f"New fact has higher weight ({new_weight} > {existing_weight})",
            }
        else:
            return {
                "action": "keep_existing",
                "fact": existing_fact,
                "requires_hitl": False,
                "reason": f"Existing fact has equal or higher weight ({existing_weight} >= {new_weight})",
            }

    def _parse_time(self, value: Any) -> datetime | None:
        """Разобрать время из различных форматов.

        Почему принимает и datetime, и строку: факты приходят из
        хранилища (datetime) и от внешних слоёв (ISO-строка); невалидное
        значение не бросаем, а возвращаем None — далее сработает
        резолюция по весу.
        """
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

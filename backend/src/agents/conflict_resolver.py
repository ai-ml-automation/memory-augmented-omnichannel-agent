"""
Conflict Resolver Agent
Resolves conflicts between fact versions (Phase D.2.5).

Rule: later overrides earlier
HITL: for conflicts within 5 minutes
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
    Agent for resolving fact conflicts.
    Phase D.2.5: Later-overrides-earlier rule, HITL for rapid conflicts.
    """

    def __init__(self) -> None:
        self.hitl_threshold = timedelta(minutes=HITL_THRESHOLD_MINUTES)

    def resolve(
        self,
        existing_fact: dict[str, Any],
        new_fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Resolve conflict between existing and new fact.

        Rules:
        1. If timestamps differ by >5 min: later overrides earlier
        2. If timestamps differ by <=5 min: requires HITL (flag for review)

        Args:
            existing_fact: Current fact with 'created_at', 'content', 'weight'
            new_fact: New fact with 'created_at', 'content', 'weight'

        Returns:
            Resolution dict with 'action', 'fact', 'requires_hitl'
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
        """Resolve by weight when timestamps unavailable."""
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
        """Parse datetime from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

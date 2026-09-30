"""
Response Evaluator
Evaluates quality and safety of LLM responses
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ResponseEvaluator:
    """
    Evaluates LLM responses for quality and safety.

    Checks:
    - Toxicity
    - Relevance
    - Factuality
    - PII leakage
    """

    def __init__(self):
        self._toxicity_model = None
        self._relevance_model = None

    async def evaluate(
        self,
        response: str,
        context: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Evaluate response quality.

        Args:
            response: LLM response
            context: Original context/message

        Returns:
            Evaluation results
        """
        results = {
            "score": 1.0,
            "checks": {},
            "warnings": [],
        }

        # 1. Toxicity check
        toxicity = await self._check_toxicity(response)
        results["checks"]["toxicity"] = toxicity

        if toxicity["score"] < 0.8:
            results["score"] *= toxicity["score"]
            results["warnings"].append(
                f"Potential toxicity detected: {toxicity['score']:.2f}"
            )

        # 2. PII leakage check
        pii = await self._check_pii_leakage(response)
        results["checks"]["pii"] = pii

        if pii["detected"]:
            results["score"] *= 0.5
            results["warnings"].append(
                f"PII detected: {pii['types']}"
            )

        # 3. Relevance check (if context provided)
        if context:
            relevance = await self._check_relevance(response, context)
            results["checks"]["relevance"] = relevance

            if relevance["score"] < 0.5:
                results["score"] *= 0.8
                results["warnings"].append(
                    f"Low relevance: {relevance['score']:.2f}"
                )

        # 4. Length check
        length_ok = await self._check_length(response)
        results["checks"]["length"] = length_ok

        if not length_ok["ok"]:
            results["score"] *= 0.9
            results["warnings"].append(length_ok["reason"])

        return results

    async def _check_toxicity(self, text: str) -> dict[str, Any]:
        """
        Check for toxic content.

        Args:
            text: Text to check

        Returns:
            Toxicity score
        """
        if not settings.ENABLE_LLM:
            return {"score": 1.0, "detected": False}

        # Simple keyword-based check (placeholder for model-based)
        toxic_keywords = [
            "дурак", "идиот", "тупой", "глупый",
            "урод", "мерзавец", "подонок",
        ]

        text_lower = text.lower()
        detected = [kw for kw in toxic_keywords if kw in text_lower]

        score = 1.0 - (len(detected) * 0.2)
        return {
            "score": max(0.0, score),
            "detected": len(detected) > 0,
            "keywords": detected,
        }

    async def _check_pii_leakage(self, text: str) -> dict[str, Any]:
        """
        Check for PII leakage.

        Args:
            text: Text to check

        Returns:
            PII detection results
        """
        import re

        pii_patterns = {
            "phone": r"\b\+?[7-8][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b",
            "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            "inn": r"\b\d{12}\b",
            "snils": r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b",
        }

        detected_types = []

        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, text):
                detected_types.append(pii_type)

        return {
            "detected": len(detected_types) > 0,
            "types": detected_types,
        }

    async def _check_relevance(
        self,
        response: str,
        context: str,
    ) -> dict[str, Any]:
        """
        Check response relevance to context.

        Args:
            response: LLM response
            context: Original context

        Returns:
            Relevance score
        """
        # Simple keyword overlap (placeholder for embedding similarity)
        context_words = set(context.lower().split())
        response_words = set(response.lower().split())

        if not context_words:
            return {"score": 0.5}

        overlap = context_words.intersection(response_words)
        score = len(overlap) / len(context_words)

        return {"score": min(1.0, score)}

    async def _check_length(self, text: str) -> dict[str, Any]:
        """
        Check response length.

        Args:
            text: Response text

        Returns:
            Length check results
        """
        max_length = 2000
        min_length = 10

        if len(text) > max_length:
            return {
                "ok": False,
                "reason": f"Response too long: {len(text)} chars",
            }

        if len(text) < min_length:
            return {
                "ok": False,
                "reason": f"Response too short: {len(text)} chars",
            }

        return {"ok": True, "length": len(text)}

    async def should_store_fact(
        self,
        response: str,
        evaluation: dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        """
        Determine if response contains storable facts.

        Args:
            response: LLM response
            evaluation: Evaluation results

        Returns:
            True if should store
        """
        # Don't store if quality is low
        if evaluation["score"] < 0.7:
            return False

        # Don't store if PII detected
        if evaluation["checks"].get("pii", {}).get("detected"):
            return False

        # Check for factual content indicators
        factual_indicators = [
            "ваш", "ваша", "ваше",
            "вы указали", "вы сказали",
            "по данным", "согласно",
        ]

        response_lower = response.lower()
        has_factual = any(ind in response_lower for ind in factual_indicators)

        return has_factual

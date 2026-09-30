"""
Оценка качества и безопасности ответов LLM.

Скоринг ответа по четырём проверкам: токсичность, утечка PII, релевантность
и длина. Итоговый score = 1.0, умноженный на штрафы за нарушения — чем больше
проблем, тем ниже качество.

Ключевые решения:
- штраф за PII самый жёсткий (×0.5): персональные данные в ответе недопустимы
  (152-ФЗ);
- проверки реализованы как лёгкие эвристики (ключевые слова, regex, пересечение
  слов) и заменяются на ML-модели при ENABLE_LLM=true — интерфейс не меняется;
- evaluate вызывается перед сохранением фактов: низкое качество блокирует
  запись в память.
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ResponseEvaluator:
    """
    Оценка ответов LLM по качеству и безопасности.

    Жизненный цикл: создаётся без тяжёлых зависимостей; ML-модели (токсичность,
    релевантность) инициализируются лениво при ENABLE_LLM=true.

    Почему эвристики вместо моделей по умолчанию: приложение должно работать
    и тестироваться без ML-стека, а пороги оценок (0.7 для сохранения фактов)
    зависят от точности используемых проверок.

    Метрики: score в диапазоне 0..1; чем ближе к 1, тем ответ лучше.
    """

    def __init__(self):
        """
        Инициализация без загрузки моделей.

        Слоты _toxicity_model и _relevance_model заполняются лениво при первом
        использовании (если ENABLE_LLM=true) — экономит память и время старта.
        """
        self._toxicity_model = None
        self._relevance_model = None

    async def evaluate(
        self,
        response: str,
        context: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Оценка качества ответа по всем проверкам.

        Итоговый score мультипликативный: каждая проваленная проверка умножает
        текущий score на свой штраф (PII ×0.5 — самый строгий, 152-ФЗ; низкая
        релевантность ×0.8; слишком длинный/короткий ответ ×0.9). Так оценка
        отражает накопление проблем, а не только худшую из них.

        Args:
            response: текст ответа LLM
            context: исходное сообщение/контекст; проверка релевантности
                выполняется только при его наличии

        Returns:
            dict: score (0..1), checks (детали по каждой проверке),
                warnings (список причин снижения)
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
        Проверка на токсичность ответа.

        При ENABLE_LLM=false проверка пропускается (score 1.0, detected False):
        заглушка не должна блокировать работу без ML-стека. При включённом LLM
        используется список запрещённых слов, каждый найденный термин снижает
        score на 0.2 (минимум 0.0).

        Args:
            text: текст для проверки

        Returns:
            dict: score (0..1), detected (True при наличии токсичных слов),
                keywords (список найденных слов)
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
        Проверка ответа на утечку персональных данных (PII).

        Просматривает текст регулярными выражениями по типам: телефон, email,
        ИНН (12 цифр), СНИЛС. Обнаружение любого типа — признак потенциальной
        утечки: ответы LLM не должны содержать персональные данные (152-ФЗ).

        Почему import re внутри метода: модуль нужен только здесь, импорт
        на верхнем уровне не даёт выигрыша, а изоляция упрощает тестирование.

        Args:
            text: текст для проверки

        Returns:
            dict: detected (True при совпадении), types (список найденных типов)
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
        Оценка релевантности ответа контексту.

        Используется пересечение множеств слов как placeholder для будущего
        сравнения эмбеддингов: дёшево, детерминированно и работает без ML.
        Пустой контекст даёт нейтральные 0.5.

        Args:
            response: текст ответа LLM
            context: исходный контекст/сообщение

        Returns:
            dict: score (0..1), доля слов контекста, встретившихся в ответе
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
        Проверка длины ответа.

        Лимиты: максимум 2000 символов (защита от "простыни" текста в каналы
        с ограничением длины сообщения), минимум 10 символов (отсечение пустых
        и бессодержательных ответов). Нарушение снижает итоговый score (×0.9).

        Args:
            text: текст ответа

        Returns:
            dict: ok (True при прохождении), reason (причина отказа),
                length (длина текста при ok=True)
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
        Решение: сохранять ли факты из ответа в память.

        Три условия: score ≥ 0.7 (достаточно качественный ответ), отсутствие PII
        (персональные данные не должны попадать в память — 152-ФЗ) и наличие
        фактологических маркеров ("вы сказали", "по данным" и т.п.), отделяющих
        утверждения о пользователе от обычного текста.

        Args:
            response: текст ответа LLM
            evaluation: результат evaluate (score и checks)

        Returns:
            True, если ответ содержит факты для сохранения
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

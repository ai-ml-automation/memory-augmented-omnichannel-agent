"""
Утилита анонимизации PII через Microsoft Presidio (152-ФЗ).

Персональные данные (ФИО, телефоны, адреса, документы) маскируются ДО записи
в БД — это требование 152-ФЗ о защите персональных данных при хранении.

Использует кастомные русские распознаватели документов РФ (II.2): паспорт,
СНИЛС, ИНН, ОГРН (см. presidio_russian). Поведение при сбое — fail-open:
исходный текст возвращается без анонимизации, ошибка логируется для аудита.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded singleton instances
_analyzer: Any = None
_anonymizer: Any = None


def _get_analyzer() -> Any:
    """
    Ленивая инициализация AnalyzerEngine с русскими распознавателями.

    Lazy, потому что Presidio тяжёлый: движок создаётся при первом использовании,
    а не при импорте модуля. Если русский пакет недоступен — fallback на стандартный
    AnalyzerEngine; если presidio-analyzer не установлен — RuntimeError с инструкцией.
    """
    global _analyzer
    if _analyzer is None:
        try:
            from backend.src.utils.presidio_russian import get_russian_analyzer

            _analyzer = get_russian_analyzer()
            logger.info("Presidio AnalyzerEngine initialized (with Russian recognizers)")
        except ImportError:
            try:
                from presidio_analyzer import AnalyzerEngine

                _analyzer = AnalyzerEngine()
                logger.info("Presidio AnalyzerEngine initialized (default only)")
            except ImportError:
                raise RuntimeError(
                    "presidio-analyzer not installed. "
                    "Install with: pip install presidio-analyzer"
                )
    return _analyzer


def _get_anonymizer() -> Any:
    """
    Ленивая инициализация AnonymizerEngine.

    Аналогично `_get_analyzer`: движок создаётся при первом обращении;
    при отсутствии пакета — RuntimeError с инструкцией по установке.
    """
    global _anonymizer
    if _anonymizer is None:
        try:
            from presidio_anonymizer import AnonymizerEngine

            _anonymizer = AnonymizerEngine()
            logger.info("Presidio AnonymizerEngine initialized")
        except ImportError:
            raise RuntimeError(
                "presidio-anonymizer not installed. "
                "Install with: pip install presidio-anonymizer"
            )
    return _anonymizer


# Default entity types to detect (PII relevant for 152-FZ)
DEFAULT_ENTITY_TYPES = [
    "PERSON",       # ФИО
    "PHONE_NUMBER", # Телефоны
    "EMAIL_ADDRESS",# Электронная почта
    "LOCATION",     # Адреса, геолокация
    "CREDIT_CARD",  # Банковские карты
    "IP_ADDRESS",   # IP-адреса
    # II.2: Russian document types (152-FZ)
    "PASSPORT_RU",  # Паспорт РФ
    "SNILS",        # Страховой номер
    "INN",          # ИНН
    "OGRN",         # ОГРН
]


def anonymize_text(
    text: str,
    language: str = "en",
    entity_types: list[str] | None = None,
    anonymize_action: str = "replace",
) -> str:
    """
    Обнаружение и анонимизация PII: сущности → <ENTITY_TYPE>.
    Args:
        text: входной текст
        language: код языка (default "en")
        entity_types: типы сущностей (default DEFAULT_ENTITY_TYPES)
        anonymize_action: действие ("replace", "redact", "hash", "encrypt")
    Returns:
        текст с PII, заменённым на плейсхолдеры
    """
    if not text or not text.strip():
        return text

    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    target_entities = entity_types or DEFAULT_ENTITY_TYPES

    try:
        # Analyze — detect PII entities
        results = analyzer.analyze(
            text=text,
            entities=target_entities,
            language=language,
        )

        if not results:
            return text

        # Anonymize — replace detected entities
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
        )

        return anonymized.text

    except Exception as e:
        logger.warning(
            "Presidio anonymization failed, returning original text: %s",
            type(e).__name__,
        )
        # Fail-open: return original text rather than blocking the flow
        # This is logged for audit purposes
        return text


def detect_pii(
    text: str,
    language: str = "en",
    entity_types: list[str] | None = None,
) -> list[dict]:
    """
    Обнаружение PII без анонимизации — для аудита: список сущностей с позициями.
    При пустом тексте или ошибке анализа возвращается пустой список.
    Args:
        text: входной текст
        language: код языка (default "en")
        entity_types: типы сущностей (default DEFAULT_ENTITY_TYPES)
    Returns:
        list[dict] с entity_type, start, end, score
    """
    if not text or not text.strip():
        return []

    analyzer = _get_analyzer()
    target_entities = entity_types or DEFAULT_ENTITY_TYPES

    try:
        results = analyzer.analyze(
            text=text,
            entities=target_entities,
            language=language,
        )
        return [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 3),
            }
            for r in results
        ]
    except Exception as e:
        logger.warning("PII detection failed: %s", type(e).__name__)
        return []

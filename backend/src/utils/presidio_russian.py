"""
Presidio Russian Recognizers
Custom PII recognizers for Russian documents (152-FZ).
Detects: PASSPORT_RU, SNILS, INN, OGRN
"""

import logging

logger = logging.getLogger(__name__)

_russian_analyzer = None


def create_russian_analyzer():
    try:
        from presidio_analyzer import (
            AnalyzerEngine,
            PatternRecognizer,
            RecognizerRegistry,
        )

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers()

        passport_ru = PatternRecognizer(
            supported_entity="PASSPORT_RU",
            name="passport_ru_recognizer",
            patterns=[
                {"name": "passport_spaced", "regex": r"\d{4}\s\d{6}", "score": 0.85},
                {"name": "passport_compact", "regex": r"\d{10}", "score": 0.4},
            ],
            supported_language="ru",
        )

        snils = PatternRecognizer(
            supported_entity="SNILS",
            name="snils_recognizer",
            patterns=[
                {"name": "snils_dashed", "regex": r"\d{3}-\d{3}-\d{3}\s?\d{2}", "score": 0.95},
                {"name": "snils_compact", "regex": r"\d{11}", "score": 0.3},
            ],
            supported_language="ru",
        )

        inn = PatternRecognizer(
            supported_entity="INN",
            name="inn_recognizer",
            patterns=[
                {"name": "inn_12", "regex": r"\d{12}", "score": 0.7},
                {"name": "inn_10", "regex": r"\d{10}", "score": 0.4},
            ],
            supported_language="ru",
        )

        ogrn = PatternRecognizer(
            supported_entity="OGRN",
            name="ogrn_recognizer",
            patterns=[
                {"name": "ogrn_13", "regex": r"\d{13}", "score": 0.6},
                {"name": "ogrnip_15", "regex": r"\d{15}", "score": 0.6},
            ],
            supported_language="ru",
        )

        registry.add_recognizer(passport_ru)
        registry.add_recognizer(snils)
        registry.add_recognizer(inn)
        registry.add_recognizer(ogrn)

        analyzer = AnalyzerEngine(registry=registry)
        logger.info("Presidio Russian AnalyzerEngine initialized")
        return analyzer

    except ImportError:
        raise RuntimeError(
            "presidio-analyzer not installed. "
            "Install with: pip install presidio-analyzer"
        )


def get_russian_analyzer():
    global _russian_analyzer
    if _russian_analyzer is None:
        _russian_analyzer = create_russian_analyzer()
    return _russian_analyzer
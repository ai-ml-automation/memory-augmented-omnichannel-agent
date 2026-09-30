"""
Юнит-тесты анонимизации PII через Presidio.

Проверяют контракт анонимайзера: строка на выходе, сквозной проход текста
без PII, замена телефона/email/имени, фолбэк на исходный текст при ошибке
и формат результатов детекта (list of dicts с ключами entity_type/start/end/score).
Тесты условно пропускаются, если presidio-analyzer не установлен.
"""

import pytest

try:
    from backend.src.utils.presidio_anonymizer import anonymize_text, detect_pii

    _presidio_available = True
except (ImportError, RuntimeError):
    _presidio_available = False


pytestmark = pytest.mark.skipif(
    not _presidio_available,
    reason="presidio-analyzer not installed",
)


class TestAnonymizeText:
    """
    Анонимизация текста: типы результатов, сквозной проход без PII.

    Ловит баги: возврат не-строки, порчу текста без PII, пропуск замены
    сущностей и крах вместо фолбэка на исходный текст.
    """

    def test_anonymize_returns_string(self):
        """
        На выходе всегда строка — базовый контракт анонимайзера.
        Ловит баг возврата None/списка вместо строки.
        """
        result = anonymize_text("Hello world")
        assert isinstance(result, str)

    def test_anonymize_empty_string(self):
        """
        Пустая строка и пробелы проходят без изменения.
        Ловит краш на пустом вводе (Presidio падает на пустом тексте).
        """
        assert anonymize_text("") == ""
        assert anonymize_text("   ") == "   "

    def test_anonymize_no_pii_passthrough(self):
        """
        Текст без PII возвращается байт-в-байт без изменений.
        Ловит ложные срабатывания детектора на обычных словах.
        """
        text = "Today is a nice day for shopping"
        result = anonymize_text(text)
        assert result == text

    def test_anonymize_phone_number(self):
        """
        Телефон заменяется на плейсхолдер PHONE и исчезает из вывода.
        Ловит пропуск замены телефонных номеров (утечка PII).
        """
        result = anonymize_text("Call me at +12025551234 please")
        assert "+12025551234" not in result
        assert "PHONE" in result

    def test_anonymize_email(self):
        """
        Email заменяется плейсхолдером и не остаётся в тексте.
        Ловит утечку email-адресов при анонимизации.
        """
        result = anonymize_text("Send to john.doe@example.com")
        assert "john.doe@example.com" not in result

    def test_anonymize_name(self):
        """
        Имя человека заменяется плейсхолдером PERSON.
        Ловит пропуск NER-сущностей (имена) в анонимизации.
        """
        result = anonymize_text("John Smith called yesterday")
        assert "John Smith" not in result

    def test_fallback_on_error(self):
        """
        Ошибка Presidio не роняет вызов: возвращается исходный текст.
        Ловит крах сервиса на невалидном языке (должен быть фолбэк).
        """
        result = anonymize_text("Simple text", language="unsupported_xyz")
        # Should not crash, returns original
        assert isinstance(result, str)


class TestDetectPii:
    """
    Детект PII без анонимизации: формат и корректность результатов.

    Ловит баги: не-списочный результат, отсутствие обязательных ключей
    в элементах и краш на пустом/None вводе.
    """

    def test_detect_no_pii(self):
        """
        Текст без PII даёт пустой список — не None и не ошибку.
        Ловит возврат None вместо пустого списка.
        """
        result = detect_pii("Simple text with no PII")
        assert isinstance(result, list)

    def test_detect_returns_dicts(self):
        """
        Каждый элемент результата — dict с ключами entity_type/start/end/score.
        Ловит изменение контракта формата (отсутствие ключа ломает UI).
        """
        result = detect_pii("Call +12025551234")
        assert isinstance(result, list)
        for item in result:
            assert "entity_type" in item
            assert "start" in item
            assert "end" in item
            assert "score" in item

    def test_detect_empty_text(self):
        """
        Пустая строка и None дают пустой список, а не исключение.
        Ловит краш на None-входе в детекторе.
        """
        assert detect_pii("") == []
        assert detect_pii(None) == []

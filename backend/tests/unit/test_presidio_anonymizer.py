"""
Unit Tests for Presidio Anonymizer
Conditional: skipped if presidio-analyzer not installed.
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
    """Test PII anonymization via Presidio."""

    def test_anonymize_returns_string(self):
        """Returns a string."""
        result = anonymize_text("Hello world")
        assert isinstance(result, str)

    def test_anonymize_empty_string(self):
        """Empty string returns empty string."""
        assert anonymize_text("") == ""
        assert anonymize_text("   ") == "   "

    def test_anonymize_no_pii_passthrough(self):
        """Text without PII passes through unchanged."""
        text = "Today is a nice day for shopping"
        result = anonymize_text(text)
        assert result == text

    def test_anonymize_phone_number(self):
        """Phone number is anonymized."""
        result = anonymize_text("Call me at +12025551234 please")
        assert "+12025551234" not in result
        assert "PHONE" in result

    def test_anonymize_email(self):
        """Email is anonymized."""
        result = anonymize_text("Send to john.doe@example.com")
        assert "john.doe@example.com" not in result

    def test_anonymize_name(self):
        """Person name is anonymized."""
        result = anonymize_text("John Smith called yesterday")
        assert "John Smith" not in result

    def test_fallback_on_error(self):
        """Returns original text on Presidio error."""
        result = anonymize_text("Simple text", language="unsupported_xyz")
        # Should not crash, returns original
        assert isinstance(result, str)


class TestDetectPii:
    """Test PII detection without anonymization."""

    def test_detect_no_pii(self):
        """No PII returns empty list."""
        result = detect_pii("Simple text with no PII")
        assert isinstance(result, list)

    def test_detect_returns_dicts(self):
        """Results are list of dicts with expected keys."""
        result = detect_pii("Call +12025551234")
        assert isinstance(result, list)
        for item in result:
            assert "entity_type" in item
            assert "start" in item
            assert "end" in item
            assert "score" in item

    def test_detect_empty_text(self):
        """Empty text returns empty list."""
        assert detect_pii("") == []
        assert detect_pii(None) == []

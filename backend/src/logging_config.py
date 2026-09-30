"""
Structured logging configuration (Phase F.2.1).

Uses python-json-logger for structured JSON logs with context fields
(user_id, session_id, trace_id) for correlation.

II.3: PII redacting filter masks phones and emails in log output.
"""

import logging
import re
import sys
from typing import Any

from pythonjsonlogger import jsonlogger


class PIIRedactingFilter(logging.Filter):
    """Mask phone numbers and email addresses in log messages (II.3).

    Prevents raw PII from appearing in structured logs if FactExtractor
    fails before anonymization.
    """

    # Phone: +7 followed by 10 digits, or similar international formats
    PHONE_PATTERN = re.compile(r'\+?\d[\d\s\-()]{7,15}\d')
    # Email: standard email pattern
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.PHONE_PATTERN.sub('[PHONE_REDACTED]', record.msg)
            record.msg = self.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', record.msg)
        # Also mask args if present (lazy formatting)
        if record.args and isinstance(record.args, dict):
            masked = {}
            for k, v in record.args.items():
                if isinstance(v, str):
                    v = self.PHONE_PATTERN.sub('[PHONE_REDACTED]', v)
                    v = self.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', v)
                masked[k] = v
            record.args = masked
        return True


class ContextFilter(logging.Filter):
    """Add context fields to log records."""

    def __init__(self) -> None:
        super().__init__()
        self._context: dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set context fields for this request."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear context fields."""
        self._context.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self._context.items():
            setattr(record, key, value)
        return True


# Global context filter for request context
context_filter = ContextFilter()


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Use JSON format (True) or text format (False)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # II.3: Add PII redacting filter (masks phones/emails before write)
    root_logger.addFilter(PIIRedactingFilter())

    # Add context filter
    root_logger.addFilter(context_filter)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(context_filter)

    if json_output:
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def log_with_context(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a message with context fields.

    Args:
        logger_instance: Logger to use
        level: Log level (logging.INFO, etc.)
        message: Log message
        **kwargs: Context fields to include
    """
    # Set context on the global filter
    context_filter.set_context(**kwargs)
    try:
        logger_instance.log(level, message)
    finally:
        context_filter.clear_context()

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
    """
    Маскирование телефонных номеров и email в логах (требование II.3).

    Защита персональных данных: PII не должны попадать в структурированные
    логи даже при сбое — например, если FactExtractor упал до анонимизации
    Presidio, в сообщении останется сырой номер. Фильтр заменит его на
    метку `[PHONE_REDACTED]`/`[EMAIL_REDACTED]`. Применяется ко всем
    записям корневого логгера.
    """

    # Телефон: +7 или аналогичные международные форматы (7–15 цифр с разделителями)
    PHONE_PATTERN = re.compile(r'\+?\d[\d\s\-()]{7,15}\d')
    # Email: стандартный паттерн почтового адреса
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    )

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Маскирование PII в msg и args записи: при lazy-форматировании
        данные могут лежать в args отдельно от строки формата. Всегда
        True — фильтр не отбрасывает записи, только чистит их.

        Returns:
            bool: True (запись всегда проходит дальше)
        """
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.PHONE_PATTERN.sub('[PHONE_REDACTED]', record.msg)
            record.msg = self.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', record.msg)
        # Маскируем и args при наличии (lazy-форматирование)
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
    """
    Добавление контекстных полей в записи лога.

    Поля (user_id, session_id, trace_id) проставляются глобальному
    фильтру перед логированием и очищаются после — так все записи
    одного запроса получают одинаковый контекст для корреляции
    (см. `log_with_context`).
    """

    def __init__(self) -> None:
        super().__init__()
        self._context: dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """
        Установка контекстных полей для текущего запроса.

        Args:
            **kwargs: произвольные поля (user_id, session_id, trace_id)
        """
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """
        Очистка контекста после обработки запроса.

        Вызывается в `finally`, чтобы контекст предыдущего запроса не
        просочился в следующий (общий глобальный фильтр).
        """
        self._context.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Копирование контекстных полей в запись лога.

        Returns:
            bool: True (записи не отбрасываются)
        """
        for key, value in self._context.items():
            setattr(record, key, value)
        return True


# Глобальный фильтр контекста: общий для всех записей приложения
context_filter = ContextFilter()


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Настройка структурированного логирования: пересоздаёт обработчики
    корневого логгера (очищает старые, вешает PII-фильтр, контекстный
    фильтр и StreamHandler в stdout для docker logs).

    Args:
        log_level: уровень (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: True — JSON (Loki), False — текст
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Удаление существующих обработчиков (безопасный повторный вызов)
    root_logger.handlers.clear()

    # II.3: PII-фильтр маскирует телефоны/email до записи
    root_logger.addFilter(PIIRedactingFilter())

    # Контекстный фильтр
    root_logger.addFilter(context_filter)

    # Обработчик
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
    Логирование с контекстными полями: контекст ставится на глобальный
    фильтр и в `finally` очищается — даже при исключении не утечёт.
    Args:
        logger_instance: логгер, в который пишем
        level: уровень (logging.INFO и т.п.)
        message: текст сообщения
        **kwargs: контекстные поля для записи
    """
    # Контекст на глобальном фильтре — применится к следующей записи
    context_filter.set_context(**kwargs)
    try:
        logger_instance.log(level, message)
    finally:
        context_filter.clear_context()

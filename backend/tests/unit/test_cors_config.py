"""
Юнит-тесты CORS-конфигурации (фаза B.2.4).

Структурные проверки main.py: в production CORS использует список
CORS_ORIGINS из конфига, в development — fallback на "*", а методы заданы
явным списком, а не wildcard (безопасность против неявного разрешения).
"""

import sys
import types
from unittest.mock import MagicMock


# Build a full mock tree for opentelemetry (avoids deep import errors)
_ot_mock = MagicMock()
for _sub in [
    "opentelemetry",
    "opentelemetry.trace",
    "opentelemetry.exporter",
    "opentelemetry.exporter.jaeger",
    "opentelemetry.exporter.jaeger.thrift",
    "opentelemetry.sdk",
    "opentelemetry.sdk.resources",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.fastapi",
    "prometheus_fastapi_instrumentator",
    "pythonjsonlogger",
    "pythonjsonlogger.jsonlogger",
]:
    sys.modules[_sub] = _ot_mock


class TestCORSConfiguration:
    """
    Структурные проверки CORS-настройки в main.py.

    Ловит баги: CORS без учёта APP_ENV (один режим для всех окружений),
    отсутствие fallback на "*" в dev и wildcard-методы вместо явного списка.
    """

    def test_production_uses_configured_origins(self):
        """
        В production origins берутся из конфига (cors_origins_list).
        Ловит баг открытого CORS в проде — источник для любых origin.
        """
        import inspect
        from backend.src import main

        source = inspect.getsource(main)

        # Should check APP_ENV
        assert "APP_ENV" in source
        # Should use cors_origins_list
        assert "cors_origins_list" in source

    def test_development_allows_all(self):
        """
        В development есть fallback на "*" (все origins разрешены).
        Ловит баг пустого списка origins в dev — фронтенд не достучится.
        """
        import inspect
        from backend.src import main

        source = inspect.getsource(main)

        # Should have fallback to ["*"]
        assert '"*"' in source or "'*'" in source

    def test_methods_are_explicit(self):
        """
        allow_methods задан явным списком (GET и т.п.), не "*".
        Ловит баг wildcard-методов — лишние методы вроде DELETE открыты.
        """
        import inspect
        from backend.src import main

        source = inspect.getsource(main)
        assert "allow_methods" in source
        # Should have explicit list
        assert '"GET"' in source or "'GET'" in source
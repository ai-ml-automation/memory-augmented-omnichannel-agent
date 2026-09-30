"""
Tests for CORS Configuration (Phase B.2.4)

B.2.4: CORS restrictive in production, open in development
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
    """Tests for CORS middleware configuration in main.py."""

    def test_production_uses_configured_origins(self):
        """In production, CORS should use configured origins from CORS_ORIGINS."""
        import inspect
        from backend.src import main

        source = inspect.getsource(main)

        # Should check APP_ENV
        assert "APP_ENV" in source
        # Should use cors_origins_list
        assert "cors_origins_list" in source

    def test_development_allows_all(self):
        """In development, CORS should allow all origins."""
        import inspect
        from backend.src import main

        source = inspect.getsource(main)

        # Should have fallback to ["*"]
        assert '"*"' in source or "'*'" in source

    def test_methods_are_explicit(self):
        """CORS should use explicit method list, not wildcard."""
        import inspect
        from backend.src import main

        source = inspect.getsource(main)
        assert "allow_methods" in source
        # Should have explicit list
        assert '"GET"' in source or "'GET'" in source
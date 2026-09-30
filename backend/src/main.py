"""
FastAPI Application Entry Point
Main application with router registration and health checks

Security (Phase B.2.4):
- CORS: restrictive in production (reads APP_ENV + CORS_ORIGINS)

Monitoring (Phase F.1):
- Prometheus metrics via prometheus-fastapi-instrumentator
- Custom business metrics (LLM latency, Qdrant search, facts, conflicts)

Logging (Phase F.2.1):
- Structured JSON logs via python-json-logger
- Context fields: user_id, session_id, trace_id

Tracing (Phase F.2.2):
- OpenTelemetry distributed tracing with Jaeger export
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

from backend.src.api.admin_channels import router as admin_channels_router
from backend.src.api.admin_users import router as admin_users_router
from backend.src.api.analytics import router as analytics_router
from backend.src.api.auth import router as auth_router
from backend.src.api.chat import router as chat_router
from backend.src.api.consents import router as consents_router
from backend.src.api.health import router as health_router
from backend.src.api.memory import router as memory_router
from backend.src.api.voice import router as voice_router
from backend.src.api.webhooks import router as webhooks_router
from backend.src.config import get_settings
from backend.src.database import async_session_factory
from backend.src.logging_config import setup_logging
from backend.src.middleware import JWTMiddleware
from backend.src.tracing import setup_tracing

settings = get_settings()

# F.2.1: Setup structured logging
setup_logging(
    log_level=settings.LOG_LEVEL if hasattr(settings, "LOG_LEVEL") else "INFO",
    json_output=settings.APP_ENV == "production",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    setup_tracing()
    logger.info("Application starting", extra={"env": settings.APP_ENV})

    # γ.1: Preload Cross-Encoder in background (non-blocking)
    if settings.ENABLE_LLM:

        async def _preload_ranker() -> None:
            try:
                from backend.src.services.memory_search_service import (
                    MemorySearchService,
                )

                async with async_session_factory() as db:
                    service = MemorySearchService(db)
                    ranker = await service._get_ranker()
                    if ranker:
                        logger.info("Cross-Encoder preloaded successfully")
            except Exception as e:
                logger.warning("Cross-Encoder preload failed: %s", e)

        asyncio.create_task(_preload_ranker())

    yield
    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="Memory-Augmented Omnichannel Agent",
    description="Omnichannel agent with long-term memory",
    version="0.1.0",
    lifespan=lifespan,
)

# B.2.4: CORS middleware - restrictive in production
_is_production = settings.APP_ENV == "production"
if _is_production:
    # Production: only allow configured origins
    _cors_origins = settings.cors_origins_list
else:
    # Development: allow all origins
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# JWT middleware
app.add_middleware(JWTMiddleware)

# F.2.2: OpenTelemetry tracing
FastAPIInstrumentor.instrument_app(app)

# F.1.1: Prometheus metrics
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(consents_router)
app.include_router(webhooks_router)
app.include_router(admin_users_router)
app.include_router(admin_channels_router)
app.include_router(memory_router)
app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(analytics_router)

# Expose /metrics endpoint
instrumentator.instrument(app).expose(app)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Memory-Augmented Omnichannel Agent"}

"""
Пакет бизнес-логики.

Реэкспортирует публичные сервисы, чтобы потребители импортировали их из
одного места (`from backend.src.services import AuthService`) вместо
глубоких путей. Список __all__ фиксирует публичный контракт пакета:
всё, что не перечислено, считается внутренним API и может меняться
без предупреждения.
"""

from backend.src.services.auth_service import AuthService
from backend.src.services.consent_service import ConsentService
from backend.src.services.session_service import SessionService
from backend.src.services.audit_service import AuditService
from backend.src.services.channel_binding_service import ChannelBindingService
from backend.src.services.message_router import MessageRouter, message_router
from backend.src.services.message_handler import MessageHandler
from backend.src.services.fact_service import FactService
from backend.src.services.vector_store_service import VectorStoreService

__all__ = [
    "AuthService",
    "ConsentService",
    "SessionService",
    "AuditService",
    "ChannelBindingService",
    "MessageRouter",
    "message_router",
    "MessageHandler",
    "FactService",
    "VectorStoreService",
]


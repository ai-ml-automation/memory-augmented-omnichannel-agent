"""
Pydantic-схемы валидации данных на границе API (request/response).

Используются только в роутерах FastAPI для проверки входящих тел запросов
и сериализации ответов — доменный код работает с моделями SQLAlchemy.

Ключевые решения: from_attributes (сериализация ORM-объектов без ручного
маппинга) и ProblemDetail (RFC 7807 — единообразный формат ошибок API).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# User Schemas
# ============================================


class UserCreate(BaseModel):
    """
    Схема регистрации пользователя (POST /auth/register).

    Телефон используется как логин системы (длина 10-15), пароль —
    минимум 8 символов; валидация выполняется на границе API до
    обращения к БД.
    """

    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """
    Ответ с данными пользователя (без пароля и телефона в открытом виде).

    Возвращается после регистрации/логина; phone_hash — хэш телефона
    (152-ФЗ). from_attributes позволяет строить ответ из ORM-объекта User.
    """

    id: UUID
    phone_hash: str
    created_at: datetime
    is_active: bool
    tenant_id: str

    model_config = {"from_attributes": True}


# ============================================
# Auth Schemas
# ============================================


class LoginRequest(BaseModel):
    """
    Тело запроса логина (POST /auth/login).

    Телефон и пароль проверяются AuthService: телефон по хэшу, пароль
    через bcrypt. Длина здесь не ограничивается — политика в сервисе.
    """

    phone: str
    password: str


class TokenResponse(BaseModel):
    """
    Ответ с JWT-токеном доступа (POST /auth/login).

    access_token предъявляется в заголовке Authorization;
    token_type="bearer" — стандартная схема HTTP-аутентификации.
    """

    access_token: str
    token_type: str = "bearer"


# ============================================
# Consent Schemas
# ============================================


class ConsentGrant(BaseModel):
    """
    Запрос на предоставление согласия на обработку данных (152-ФЗ).

    channel — канал, для которого даётся согласие; ip_address фиксирует
    место дачи согласия для доказательной базы.
    """

    channel: str
    ip_address: Optional[str] = None


class ConsentResponse(BaseModel):
    """
    Статус согласия пользователя (152-ФЗ) для UI/API.

    has_active_consent — есть ли действующее согласие (revoked_at is None);
    granted_at/revoked_at — период действия текущего согласия.
    """

    has_active_consent: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


# ============================================
# Session Schemas
# ============================================


class SessionResponse(BaseModel):
    """
    Данные сессии диалога (GET /sessions).

    from_attributes позволяет строить ответ из ORM-объекта Session;
    ended_at=None означает активную (незакрытую) сессию.
    """

    id: UUID
    user_id: UUID
    channel_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============================================
# Fact Schemas
# ============================================


class FactResponse(BaseModel):
    """
    Данные факта памяти (GET /memory, /facts).

    Сериализует ORM-объект Fact: value — текст факта, weight — важность,
    expires_at — дата устаревания (None = бессрочный), is_superseded —
    признак замещения более актуальным фактом.
    """

    id: UUID
    user_id: UUID
    type: str
    value: str
    weight: float
    channel: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_superseded: bool

    model_config = {"from_attributes": True}


# ============================================
# Health Schemas
# ============================================


class HealthResponse(BaseModel):
    """
    Ответ эндпоинта /health.

    status — общий статус приложения, services — словарь «сервис: статус»
    (postgres, redis, qdrant и т.д.) для мониторинга зависимостей.
    """

    status: str
    services: dict[str, str]


# ============================================
# Error Schemas (RFC 7807)
# ============================================


class ProblemDetail(BaseModel):
    """
    RFC 7807 Problem Details — единый формат ошибок HTTP API.

    type/title/status — машинно-читаемое описание, detail/instance —
    человекочитаемые детали и ссылка на конкретный экземпляр ошибки.
    """

    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None

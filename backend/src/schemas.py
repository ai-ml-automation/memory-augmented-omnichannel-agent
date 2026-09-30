"""
Pydantic Schemas for API validation
Used only at the API boundary for request/response validation
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# User Schemas
# ============================================


class UserCreate(BaseModel):
    """Schema for user registration."""

    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """Schema for user response."""

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
    """Schema for login request."""

    phone: str
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"


# ============================================
# Consent Schemas
# ============================================


class ConsentGrant(BaseModel):
    """Schema for granting consent."""

    channel: str
    ip_address: Optional[str] = None


class ConsentResponse(BaseModel):
    """Schema for consent status response."""

    has_active_consent: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


# ============================================
# Session Schemas
# ============================================


class SessionResponse(BaseModel):
    """Schema for session response."""

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
    """Schema for fact response."""

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
    """Schema for health check response."""

    status: str
    services: dict[str, str]


# ============================================
# Error Schemas (RFC 7807)
# ============================================


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs."""

    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None

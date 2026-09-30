"""
Unit Tests for AuthService
Tests registration, login, password verification, phone hashing.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_register_creates_user(db_session: AsyncSession):
    """Test that register creates a user with password_hash."""
    service = AuthService(db_session)
    user = await service.register("+79991234567", "testpassword123")

    assert user is not None
    assert user.id is not None
    assert user.phone_hash is not None
    assert user.password_hash is not None
    assert len(user.password_hash) > 0
    assert user.is_active is True
    assert user.tenant_id == "default"


@pytest.mark.asyncio
async def test_register_duplicate_phone_raises(db_session: AsyncSession):
    """Test that registering same phone twice raises ValueError."""
    service = AuthService(db_session)
    await service.register("+79991234567", "password1")

    with pytest.raises(ValueError, match="already exists"):
        await service.register("+79991234567", "password2")


@pytest.mark.asyncio
async def test_login_returns_token(db_session: AsyncSession):
    """Test that login with valid credentials returns JWT."""
    service = AuthService(db_session)
    await service.register("+79991234567", "testpassword123")

    token = await service.login("+79991234567", "testpassword123")

    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_wrong_password_raises(db_session: AsyncSession):
    """Test that login with wrong password raises ValueError."""
    service = AuthService(db_session)
    await service.register("+79991234567", "testpassword123")

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("+79991234567", "wrongpassword")


@pytest.mark.asyncio
async def test_login_nonexistent_user_raises(db_session: AsyncSession):
    """Test that login with nonexistent phone raises ValueError."""
    service = AuthService(db_session)

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("+79999999999", "password")


@pytest.mark.asyncio
async def test_get_current_user_valid_token(db_session: AsyncSession):
    """Test that get_current_user returns user for valid JWT."""
    service = AuthService(db_session)
    user = await service.register("+79991234567", "testpassword123")
    token = await service.login("+79991234567", "testpassword123")

    current_user = await service.get_current_user(token)

    assert current_user.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises(db_session: AsyncSession):
    """Test that get_current_user raises ValueError for invalid token."""
    service = AuthService(db_session)

    with pytest.raises(ValueError, match="Invalid token"):
        await service.get_current_user("invalid.token.here")


def test_hash_phone_deterministic():
    """Test that _hash_phone produces consistent HMAC-SHA256 hashes."""
    service = AuthService.__new__(AuthService)

    # Import settings directly
    from backend.src.config import get_settings
    settings = get_settings()

    h1 = service._hash_phone("+79991234567")
    h2 = service._hash_phone("+79991234567")
    h3 = service._hash_phone("+79991234568")

    assert h1 == h2  # Same phone -> same hash
    assert h1 != h3  # Different phone -> different hash
    assert len(h1) == 64  # SHA-256 hex digest is 64 chars

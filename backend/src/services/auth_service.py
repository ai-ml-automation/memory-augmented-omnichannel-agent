"""
Authentication Service
Registration, login, JWT handling
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.models import User

settings = get_settings()


class AuthService:
    """Service for user authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, phone: str, password: str) -> User:
        """
        Register new user.

        Args:
            phone: Phone number
            password: Plain text password

        Returns:
            Created User instance

        Raises:
            ValueError: If user with this phone already exists
        """
        phone_hash = self._hash_phone(phone)

        # Check if user already exists
        existing = await self.db.execute(
            select(User).where(User.phone_hash == phone_hash)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("User with this phone already exists")

        # Hash password with bcrypt (12 rounds)
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")

        # Create user with password hash
        user = User(
            id=uuid.uuid4(),
            phone_hash=phone_hash,
            password_hash=password_hash,
            is_active=True,
            tenant_id="default",  # TODO: Multi-tenant support
        )
        self.db.add(user)
        await self.db.flush()

        return user

    async def login(self, phone: str, password: str) -> str:
        """
        Login user and return JWT token.

        Args:
            phone: Phone number
            password: Plain text password

        Returns:
            JWT access token

        Raises:
            ValueError: If credentials are invalid
        """
        # Find user by phone hash
        phone_hash = self._hash_phone(phone)
        result = await self.db.execute(
            select(User).where(User.phone_hash == phone_hash)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Invalid credentials")

        # Verify password against stored hash
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            user.password_hash.encode("utf-8"),
        ):
            raise ValueError("Invalid credentials")

        # I.1.2: Increment JWT version (invalidates all existing tokens)
        user.jwt_version += 1
        await self.db.flush()

        # Generate JWT with version
        token = self._generate_token(user.id, user.jwt_version)
        return token

    async def get_current_user(self, token: str) -> User:
        """
        Validate JWT and return user.

        Args:
            token: JWT access token

        Returns:
            User instance

        Raises:
            ValueError: If token is invalid, revoked, or user not found
        """
        try:
            payload = jwt.decode(
                token,
                settings.effective_jwt_secret,
                algorithms=[settings.JWT_ALGORITHM],
            )
            user_id = payload.get("sub")
            if user_id is None:
                raise ValueError("Invalid token")

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                raise ValueError("Token expired")

        except jwt.PyJWTError as e:
            raise ValueError(f"Invalid token: {e}") from e

        # Get user
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # I.1.2: Check JWT version (revocation check)
        token_version = payload.get("ver", 0)
        if user.jwt_version != token_version:
            raise ValueError(
                "Token revoked (password changed or consent revoked)"
            )

        return user

    def _hash_phone(self, phone: str) -> str:
        """
        Hash phone number using SHA-256 with tenant-specific salt.

        Uses HMAC-SHA256 instead of bcrypt because bcrypt is designed
        for low-entropy passwords and is vulnerable to rainbow tables
        for high-entropy data like phone numbers.
        """
        salt = settings.SECRET_KEY.encode("utf-8")
        return hmac.new(
            salt,
            phone.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _generate_token(self, user_id: uuid.UUID, version: int = 1) -> str:
        """Generate JWT token for user with version for revocation support."""
        payload = {
            "sub": str(user_id),
            "ver": version,
            "exp": datetime.utcnow()
            + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(
            payload,
            settings.effective_jwt_secret,
            algorithm=settings.JWT_ALGORITHM,
        )

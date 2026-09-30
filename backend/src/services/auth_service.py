"""
Сервис аутентификации пользователей: регистрация, логин, JWT.

Реализует 152-ФЗ-совместимую модель доступа: телефон хранится только как
HMAC-SHA256-хеш (псевдонимизация), пароль — bcrypt, JWT — короткоживущий
с версионированием (jwt_version) для мгновенной инвалидации всех токенов.

Логика согласована с `AuthService`, `dependencies.get_current_admin` и моделью User.
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
    """
    Сервис аутентификации: регистрация, логин, проверка JWT.

    Жизненный цикл: создаётся на каждый запрос с сессией БД (AsyncSession),
    не хранит состояния между вызовами.

    Ключевые решения:
    - телефон хешируется HMAC-SHA256 (не bcrypt): bcrypt рассчитан на
      низкоэнтропийные пароли и уязвим к rainbow-таблицам для телефонов;
    - JWT содержит версию (ver): инкремент jwt_version при логине мгновенно
      инвалидирует все выпущенные ранее токены (I.1.2).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, phone: str, password: str) -> User:
        """
        Регистрация нового пользователя.
        Args:
            phone: номер телефона
            password: пароль в открытом виде (хешируется bcrypt, 12 раундов)
        Returns:
            созданный User
        Raises:
            ValueError: если пользователь с таким телефоном уже существует
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
        Логин: проверка пароля и выпуск JWT.
        Args:
            phone: номер телефона
            password: пароль в открытом виде
        Returns:
            JWT access token
        Raises:
            ValueError: если учётные данные неверны
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
        Проверка JWT и возврат пользователя.

        Помимо подписи проверяет exp и версию (ver): расхождение с jwt_version
        означает отзыв токена (I.1.2) — вызывается ValueError.
        Args:
            token: JWT access token
        Returns:
            User
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
        Хеширование телефона: HMAC-SHA256 с солью приложения.
        Почему не bcrypt: он рассчитан на низкоэнтропийные пароли, для телефонов
        уязвим к rainbow-таблицам. HMAC с солью SECRET_KEY даёт псевдонимизацию.
        Args:
            phone: номер телефона
        Returns:
            hex-строка SHA-256 хеша
        """
        salt = settings.SECRET_KEY.encode("utf-8")
        return hmac.new(
            salt,
            phone.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _generate_token(self, user_id: uuid.UUID, version: int = 1) -> str:
        """
        Генерация JWT с версией для отзыва (revocation).
        Полезная нагрузка: sub (user_id), ver (version), exp (JWT_EXPIRATION_HOURS),
        iat. Секрет — effective_jwt_secret из настроек.
        Args:
            user_id: идентификатор пользователя
            version: версия токена (jwt_version)
        Returns:
            JWT-строка
        """
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

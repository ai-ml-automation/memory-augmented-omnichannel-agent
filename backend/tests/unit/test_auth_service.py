"""
Unit Tests for AuthService
Проверяют регистрацию, логин, проверку пароля, получение пользователя по JWT
и детерминированный HMAC-SHA256-хэш телефона.

Зачем эти тесты: аутентификация — рубеж безопасности. Пароль не хранится
открытым текстом, а телефон — хэшируется (HMAC-SHA256), чтобы утечка БД
не раскрыла личные данные. Тесты ловят регрессии в этой логике:
дубликаты аккаунтов, вход с неверным паролем, приём мусорных токенов.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_register_creates_user(db_session: AsyncSession):
    """Ловит баг, если register не создаёт полноценную запись пользователя.

    После вызова должны быть: id, phone_hash, непустой password_hash
    (bcrypt), is_active=True и tenant_id="default". Без любого из этих
    полей вход пользователя позже упадёт или аккаунт окажется сломанным.
    """
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
    """Ловит баг, если повторная регистрация телефона не отклоняется.

    Сервис обязан бросить ValueError с "already exists", иначе один номер
    сможет создать несколько аккаунтов — потеря связи аккаунта с владельцем
    и обход ограничений на одного пользователя на телефон.
    """
    service = AuthService(db_session)
    await service.register("+79991234567", "password1")

    with pytest.raises(ValueError, match="already exists"):
        await service.register("+79991234567", "password2")


@pytest.mark.asyncio
async def test_login_returns_token(db_session: AsyncSession):
    """Ловит баг, если login с корректными данными не выдаёт JWT.

    Проверяет всю цепочку: регистрация, хэширование пароля и его проверка
    при входе, выпуск непустого токена. Пустой токен означает обрыв
    в любом из этих звеньев — без теста сломается вход пользователей.
    """
    service = AuthService(db_session)
    await service.register("+79991234567", "testpassword123")

    token = await service.login("+79991234567", "testpassword123")

    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_wrong_password_raises(db_session: AsyncSession):
    """Ловит баг, если неверный пароль не отклоняется при входе.

    login обязан бросить ValueError "Invalid credentials" и не выдать токен.
    Пропуск неверного пароля открывает вход под чужим аккаунтом — это
    критический дефект аутентификации, который тест должен ловить первым.
    """
    service = AuthService(db_session)
    await service.register("+79991234567", "testpassword123")

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("+79991234567", "wrongpassword")


@pytest.mark.asyncio
async def test_login_nonexistent_user_raises(db_session: AsyncSession):
    """Ловит баг, если вход несуществующего номера не отклоняется.

    Должен бросаться тот же ValueError "Invalid credentials", что и при
    неверном пароле, — сервис не должен раскрывать, существует ли номер.
    Иначе перебор номеров даст злоумышленнику список реальных аккаунтов.
    """
    service = AuthService(db_session)

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("+79999999999", "password")


@pytest.mark.asyncio
async def test_get_current_user_valid_token(db_session: AsyncSession):
    """Ловит баг, если get_current_user не распознаёт валидный JWT.

    Регистрирует и логинит пользователя, затем расшифровывает токен:
    возвращённый пользователь должен совпасть по id с зарегистрированным.
    Несовпадение id означает сломанный разбор токена или подмену субъекта.
    """
    service = AuthService(db_session)
    user = await service.register("+79991234567", "testpassword123")
    token = await service.login("+79991234567", "testpassword123")

    current_user = await service.get_current_user(token)

    assert current_user.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises(db_session: AsyncSession):
    """Ловит баг, если мусорный токен не отклоняется get_current_user.

    Строка "invalid.token.here" не является валидным JWT — сервис обязан
    бросить ValueError "Invalid token". Пропуск невалидного токена означает,
    что защищённые маршруты начнут доверять подделанным токенам.
    """
    service = AuthService(db_session)

    with pytest.raises(ValueError, match="Invalid token"):
        await service.get_current_user("invalid.token.here")


def test_hash_phone_deterministic():
    """Ловит баг, если _hash_phone недетерминирован или не SHA-256.

    Один и тот же телефон обязан давать одинаковый 64-символьный hex
    (HMAC-SHA256), разные телефоны — разные хэши. Это позволяет искать
    пользователя по телефону, не храня открытый номер: нарушение
    детерминированности сломает логин по номеру.
    """
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

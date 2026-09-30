"""
E2E-тесты полного сценария аутентификации.

Покрывают регистрацию (успех и дубликат), логин (верный/неверный
пароль, httpOnly-cookie), GET /auth/me с сессией и без неё, а также
логаут с последующей проверкой, что сессия действительно закрыта.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """Ловит сбой регистрации: валидные данные не дают 201 и тела ответа.

    Контракт /auth/register: 201 + id, phone_hash, created_at, is_active.
    """
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "phone_hash" in data
    assert "created_at" in data
    assert "is_active" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_user_duplicate(client: AsyncClient):
    """Ловит дубликаты аккаунтов: повторная регистрация не отклоняется.

    Один номер телефона = один аккаунт; повторный запрос обязан
    вернуть 400, иначе пользователь плодит лишние записи.
    """
    payload = {
        "phone": "+79991234567",
        "password": "TestPassword123!",
    }
    response1 = await client.post("/auth/register", json=payload)
    assert response1.status_code == 201

    response2 = await client.post("/auth/register", json=payload)
    assert response2.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Ловит сбой логина: токен и cookie не выдаются после регистрации.

    Проверяет 200, access_token в теле, token_type=bearer и наличие
    cookie access_token — всё, что нужно SPA для авторизации.
    """
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Ловит дыру в логине: неверный пароль не отклоняется.

    Чужие пароли не должны давать доступ; 401 обязателен,
    иначе аутентификация бессмысленна.
    """
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "WrongPassword999!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """Ловит потерю сессии: /auth/me с cookie не отдаёт пользователя.

    Сверяет id из /auth/me с id из регистрации — сессия должна
    идентифицировать именно того пользователя, что залогинился.
    """
    register_response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert register_response.status_code == 201
    registered_user = register_response.json()

    login_response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200
    # Cookie is automatically stored by httpx AsyncClient

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    data = me_response.json()
    assert data["id"] == registered_user["id"]
    assert "phone_hash" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """Ловит дыру в авторизации: /auth/me доступен без cookie.

    Личные данные (152-ФЗ) обязаны быть закрытыми — 401 без сессии.
    """
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Ловит незакрытую сессию: после логаута токен продолжает работать.

    POST /auth/logout обязан инвалидировать сессию: до логаута
    /auth/me даёт 200, после — 401.
    """
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )
    await client.post(
        "/auth/login",
        json={
            "phone": "+79991234567",
            "password": "TestPassword123!",
        },
    )

    # Verify auth works before logout
    me_before = await client.get("/auth/me")
    assert me_before.status_code == 200

    # Logout
    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200
    data = logout_response.json()
    assert "message" in data

    # Verify auth no longer works
    me_after = await client.get("/auth/me")
    assert me_after.status_code == 401

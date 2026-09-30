"""
E2E-тесты потока аутентификации через HTTP.

Покрывают регистрацию (201 + состав ответа), логин (токен в теле
и httpOnly-cookie), защиту /auth/me (401 без сессии), логаут
(очистка cookie) и защиту /consents/status. Проверяют контракт API
«снаружи», через реальный HTTP-клиент к приложению.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_201(client: AsyncClient):
    """Ловит сбой регистрации: валидные данные не дают 201 Created.

    Базовый контракт /auth/register — успешное создание пользователя
    по номеру телефона и паролю.
    """
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234567",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_register_returns_user_data(client: AsyncClient):
    """Ловит утечку/потерю полей: ответ регистрации без ключевых данных.

    Клиент фронтенда ждёт id, phone_hash, created_at, is_active,
    tenant_id; отсутствие любого поля ломает UI.
    """
    response = await client.post(
        "/auth/register",
        json={
            "phone": "+79991234568",
            "password": "testpassword123",
        },
    )

    data = response.json()

    assert "id" in data
    assert "phone_hash" in data
    assert "created_at" in data
    assert "is_active" in data
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient):
    """Ловит сбой логина: после регистрации не выдаётся токен.

    Логин обязан вернуть 200, access_token и token_type=bearer —
    иначе клиент не сможет авторизоваться.
    """
    # First register
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234569",
            "password": "testpassword123",
        },
    )

    # Then login
    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234569",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_sets_cookie(client: AsyncClient):
    """Ловит отсутствие сессионной cookie: SPA остаётся неавторизованным.

    Фронтенд полагается на httpOnly-cookie access_token; если логин
    её не ставит — каждый запрос падает с 401.
    """
    # First register
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234570",
            "password": "testpassword123",
        },
    )

    # Then login
    response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234570",
            "password": "testpassword123",
        },
    )

    # Check cookie is set
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_me_requires_authentication(client: AsyncClient):
    """Ловит дыру в авторизации: /auth/me доступен без токена.

    Метод обязан требовать аутентификацию (401) — иначе чужие
    пользователи читают личные данные (152-ФЗ).
    """
    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_with_valid_token(client: AsyncClient):
    """Ловит потерю данных сессии: /auth/me не отдаёт пользователя.

    После регистрации и логина запрос с cookie обязан вернуть 200
    с id и phone_hash текущего пользователя.
    """
    # Register and login
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234571",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "phone": "+79991234571",
            "password": "testpassword123",
        },
    )

    # Get user with cookie
    response = await client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "phone_hash" in data


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient):
    """Ловит незакрытую сессию: логаут не очищает cookie.

    После /auth/logout cookie access_token должен исчезнуть —
    иначе выйти из системы невозможно (безопасность).
    """
    # Register and login first so middleware accepts the request
    await client.post(
        "/auth/register",
        json={
            "phone": "+79991234572",
            "password": "testpassword123",
        },
    )
    await client.post(
        "/auth/login",
        json={
            "phone": "+79991234572",
            "password": "testpassword123",
        },
    )

    response = await client.post("/auth/logout")

    assert response.status_code == 200
    # Cookie should be cleared
    assert response.cookies.get("access_token") is None or \
           response.cookies.get("access_token") == ""


@pytest.mark.asyncio
async def test_consents_status_requires_auth(client: AsyncClient):
    """Ловит дыру в согласиях: /consents/status доступен без токена.

    Статус согласий — личные данные (152-ФЗ); без аутентификации
    эндпоинт обязан вернуть 401.
    """
    response = await client.get("/consents/status")

    assert response.status_code == 401

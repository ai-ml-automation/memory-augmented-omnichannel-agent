"""
E2E-тесты эндпоинтов согласий.

Покрывают выдачу согласия (grant), проверку статуса и отзыв (revoke,
RTBF по 152-ФЗ). Все эндпоинты требуют аутентификацию через JWT-cookie.
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str) -> None:
    """Регистрирует пользователя и логинит его, ставя JWT-cookie.

    Args:
        client: HTTP-клиент e2e-фикстуры.
        phone: номер телефона пользователя (уникальный на тест).
    """
    await client.post(
        "/auth/register",
        json={
            "phone": phone,
            "password": "ConsentTest123!",
        },
    )
    await client.post(
        "/auth/login",
        json={"phone": phone, "password": "ConsentTest123!"},
    )


@pytest.mark.asyncio
async def test_consent_grant(client: AsyncClient):
    """Ловит сбой выдачи согласия: grant не создаёт активную запись.

    Контракт /consents/grant: 201 + has_active_consent=True,
    иначе согласие не фиксируется и чат-обработка незаконна.
    """
    await _register_and_login(client, "+79991000001")

    resp = await client.post(
        "/consents/grant",
        json={
            "scope": "messaging",
            "channel": "telegram",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_active_consent"] is True


@pytest.mark.asyncio
async def test_consent_status(client: AsyncClient):
    """Ловит потерю статуса: /consents/status без ключа has_active_consent.

    Статус согласий нужен UI и чат-сервису для проверки правомерности
    обработки (152-ФЗ).
    """
    await _register_and_login(client, "+79991000002")

    resp = await client.get("/consents/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_active_consent" in data


@pytest.mark.asyncio
async def test_consent_revoke(client: AsyncClient):
    """Ловит незакрытый отзыв: revoke не гасит активное согласие.

    RTBF: после выдачи согласия и его отзыва has_active_consent
    обязан стать False — иначе данные продолжают обрабатываться.
    """
    await _register_and_login(client, "+79991000003")

    # Grant first, then revoke
    await client.post(
        "/consents/grant",
        json={"scope": "messaging", "channel": "max"},
    )

    resp = await client.post("/consents/revoke")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_active_consent"] is False

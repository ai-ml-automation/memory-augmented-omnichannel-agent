"""
E2E-тесты health-эндпоинта приложения.

Проверяют доступность /health и корневого "/" без аутентификации,
а также формат ответа: status (healthy/degraded/unhealthy) и services
(словарь состояния подсистем).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.main import app


@pytest.mark.asyncio
async def test_health_check_returns_200():
    """Ловит недоступность health: /health не отвечает 200.

    Если health-эндпоинт падает — мониторинг не может отличить
    живое приложение от мёртвого.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check_returns_correct_format():
    """Ловит поломку контракта: /health без полей status и services.

    UI и внешние проверки ждут именно эти ключи; их отсутствие
    ломает интеграцию с мониторингом.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert "status" in data
    assert "services" in data
    assert isinstance(data["services"], dict)


@pytest.mark.asyncio
async def test_health_check_status_is_string():
    """Ловит невалидный статус: /health вне healthy/degraded/unhealthy.

    Скрипты мониторинга сравнивают статус со строками; любое
    другое значение ломает алертинг.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert isinstance(data["status"], str)
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.asyncio
async def test_health_check_services_is_dict():
    """Ловит сбой структуры: services не является словарём.

    По ключам services (БД, Redis, вектор-стор) агрегируется
    общий статус; не-словарь ломает разбор на клиенте.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    data = response.json()

    assert isinstance(data["services"], dict)


@pytest.mark.asyncio
async def test_root_endpoint_returns_200():
    """Ловит недоступность корня: "/" не отвечает 200.

    Корневой эндпоинт — точка входа API; его падение блокирует
    все запросы клиентов.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_root_endpoint_returns_message():
    """Ловит потерю приветствия: "/" без поля message.

    Корень API обязан отдавать строку message (название сервиса);
    её отсутствие ломает клиентов, ожидающих это поле.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    data = response.json()

    assert "message" in data
    assert isinstance(data["message"], str)

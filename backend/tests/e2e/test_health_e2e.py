"""
E2E-тесты health-эндпоинта через общий клиент.

Проверяет, что /health доступен без аутентификации и отдаёт
валидный статус со словарём подсистем.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Ловит поломку health: /health закрыт или не отдаёт статус.

    /health обязан работать без cookie (для k8s probe и LB) и
    содержать status + services — иначе деплой ломается.
    """
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert "services" in data
    assert isinstance(data["services"], dict)

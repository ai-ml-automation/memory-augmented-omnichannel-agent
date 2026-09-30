"""
Единая точка приёма вебхуков от мессенджеров (Telegram, VK, MAX).

Зачем единый роутер: все каналы омниканального шлюза обрабатываются одним
конвейером `process_message` (Celery), поэтому эндпоинты возвращают 200 OK
немедленно, а реальная обработка уходит в фон (Phase C.2, fire-and-forget).

Безопасность (Phase B.2):
- Telegram: проверка заголовка X-Telegram-Bot-Api-Secret-Token через compare_digest;
- VK: проверка поля secret в данных Callback API;
- MAX: подпись не предусмотрена провайдером, верификация не выполняется.

В dev-режиме (секрет не задан в настройках) проверка пропускается — см. @see get_settings.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.database import get_db
from backend.src.integrations.max_gateway import MAXGateway
from backend.src.integrations.telegram_gateway import TelegramGateway
from backend.src.integrations.vk_gateway import VKGateway
from backend.src.tasks.message_tasks import process_message

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Initialize gateways (lazy)
max_gateway = MAXGateway()
telegram_gateway = TelegramGateway()
vk_gateway = VKGateway()


# ------------------------------------------------------------------
# B.2.1: Telegram webhook secret verification
# ------------------------------------------------------------------

def _verify_telegram_secret(request: Request) -> None:
    """
    Проверка заголовка X-Telegram-Bot-Api-Secret-Token от Telegram.

    Telegram присылает этот заголовок на каждый вызов, если секрет задан
    при регистрации вебхука (setWebhook). Сравнение через hmac.compare_digest
    исключает timing-атаку по длине секрета.

    Если секрет не сконфигурирован — проверка пропускается (dev-режим),
    в проде секрет обязателен (Phase B.2.1).

    Raises:
        HTTPException: 403, если заголовок отсутствует или не совпадает
    """
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        # Secret not configured - skip verification (dev mode)
        return

    received = request.headers.get("x-telegram-bot-api-secret-token", "")
    expected = settings.TELEGRAM_WEBHOOK_SECRET

    if not hmac.compare_digest(received, expected):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "Telegram webhook rejected: invalid secret token (ip=%s)",
            client_ip,
        )
        raise HTTPException(status_code=403, detail="Forbidden")


# ------------------------------------------------------------------
# B.2.2: VK callback secret verification
# ------------------------------------------------------------------

def _verify_vk_secret(data: dict) -> None:
    """
    Проверка поля secret в данных VK Callback API.

    VK добавляет это поле в каждый callback, если оно задано в настройках
    сообщества. Сравнение через hmac.compare_digest — защита от timing-атак.

    Подводный камень: confirmation-запрос приходит БЕЗ поля secret — его
    обрабатывает `vk_webhook` до вызова этой функции.

    Raises:
        HTTPException: 403, если секрет не совпадает
    """
    if not settings.VK_CALLBACK_SECRET:
        # Secret not configured - skip verification (dev mode)
        return

    received = data.get("secret", "")
    expected = settings.VK_CALLBACK_SECRET

    if not hmac.compare_digest(str(received), expected):
        logger.warning("VK webhook rejected: invalid secret")
        raise HTTPException(status_code=403, detail="Forbidden")


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/max")
async def max_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Приём сообщений из мессенджера MAX.

    Почему асинхронно: обработка (идентификация, память, ответ) занимает
    секунды — держать HTTP-соединение мессенджера недопустимо, поэтому
    сообщение передаётся в Celery-задачу `process_message` и эндпоинт
    сразу возвращает 200 OK (Phase C.2.3).

    Args:
        request: исходный HTTP-запрос с JSON-данными вебхука
        db: сессия БД (передаётся в фоновую задачу)

    Returns:
        {"status": "ok"} — подтверждение приёма

    Raises:
        HTTPException: 400 при невалидных данных, 500 при внутренней ошибке
    """
    try:
        data = await request.json()
        parsed = await max_gateway.get_webhook_data(data)

        if not parsed["external_id"]:
            raise HTTPException(status_code=400, detail="Invalid message data")

        # C.2.3: Dispatch async, return 200 OK immediately
        process_message.delay(
            channel_type="MAX",
            external_id=parsed["external_id"],
            text=parsed["text"],
        )

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MAX webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Приём сообщений из Telegram.

    Перед обработкой вызывается проверка секрета (Phase B.2.1): без неё
    любой может слать сообщения от имени бота и засорять память клиентов.

    Данные передаются в Celery-задачу `process_message` (fire-and-forget),
    ответ 200 OK возвращается сразу (Phase C.2.3).

    Args:
        request: исходный HTTP-запрос с JSON-данными вебхука
        db: сессия БД (передаётся в фоновую задачу)

    Returns:
        {"status": "ok"} — подтверждение приёма

    Raises:
        HTTPException: 403 при неверном секрете, 400/500 при ошибках данных
    """
    _verify_telegram_secret(request)

    try:
        data = await request.json()
        parsed = await telegram_gateway.get_webhook_data(data)

        if not parsed["external_id"]:
            raise HTTPException(status_code=400, detail="Invalid message data")

        # C.2.3: Dispatch async, return 200 OK immediately
        process_message.delay(
            channel_type="TG",
            external_id=parsed["external_id"],
            text=parsed["text"],
        )

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Telegram webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vk")
async def vk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Приём сообщений из VK (Callback API).

    Особенность VK: запрос confirmation (подтверждение адреса сервера)
    обрабатывается ДО проверки секрета и возвращает идентификатор группы —
    иначе VK не завершит регистрацию вебхука.

    Обычные сообщения проходят проверку секрета (Phase B.2.2), затем
    уходят в Celery-задачу `process_message`, ответ — 200 OK (Phase C.2.3).

    Args:
        request: исходный HTTP-запрос с JSON-данными вебхука
        db: сессия БД (передаётся в фоновую задачу)

    Returns:
        {"status": "ok"} или {"response": VK_GROUP_ID} для confirmation

    Raises:
        HTTPException: 403 при неверном секрете, 400/500 при ошибках данных
    """
    try:
        data = await request.json()

        # VK Callback API requires confirmation
        if data.get("type") == "confirmation":
            # Confirmation is safe to return without secret check
            return {"response": settings.VK_GROUP_ID}

        # B.2.2: Verify VK secret
        _verify_vk_secret(data)

        parsed = await vk_gateway.get_webhook_data(data)

        if not parsed["external_id"]:
            raise HTTPException(status_code=400, detail="Invalid message data")

        # C.2.3: Dispatch async, return 200 OK immediately
        process_message.delay(
            channel_type="VK",
            external_id=parsed["external_id"],
            text=parsed["text"],
        )

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("VK webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unified")
async def unified_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Универсальный эндпоинт вебхуков для произвольного канала.

    Позволяет подключать новые каналы без отдельного эндпоинта: маршрутизация
    по полю channel (TG/VK/MAX) с соответствующей проверкой секрета на месте.
    Используется для интеграционных тестов и каналов без собственного роутера.

    Args:
        request: исходный HTTP-запрос с JSON-данными вебхука
        db: сессия БД (передаётся в фоновую задачу)

    Returns:
        {"status": "ok"} — подтверждение приёма

    Raises:
        HTTPException: 400 при неизвестном канале или невалидных данных
    """
    try:
        data = await request.json()
        channel = data.get("channel", "").upper()

        if channel == "TG":
            _verify_telegram_secret(request)
            parsed = await telegram_gateway.get_webhook_data(data)
        elif channel == "VK":
            _verify_vk_secret(data)
            parsed = await vk_gateway.get_webhook_data(data)
        elif channel == "MAX":
            parsed = await max_gateway.get_webhook_data(data)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown channel: {channel}",
            )

        if not parsed["external_id"]:
            raise HTTPException(status_code=400, detail="Invalid message data")

        # C.2.3: Dispatch async, return 200 OK immediately
        process_message.delay(
            channel_type=channel,
            external_id=parsed["external_id"],
            text=parsed["text"],
        )

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unified webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

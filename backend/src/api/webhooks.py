"""
Webhooks Router
Unified endpoint for all messenger webhooks

Security (Phase B.2):
- Telegram: X-Telegram-Bot-Api-Secret-Token header verification
- VK: secret parameter verification in callback data

Async (Phase C.2):
- Messages processed via Celery tasks (fire-and-forget)
- Webhook returns 200 OK immediately
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
    Verify X-Telegram-Bot-Api-Secret-Token header.

    Telegram sends this header on every webhook call when the
    secret token is set via setWebhook(secret_token=...).

    Raises 403 if the token is missing or does not match.
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
    Verify VK Callback API secret parameter.

    VK sends 'secret' field in every callback if configured in
    the group settings.

    Raises 403 if the secret does not match.
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
    Handle MAX webhook.

    Receives messages from MAX messenger and processes them async.
    C.2.3: Returns 200 OK immediately, processes in background via Celery.
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
    Handle Telegram webhook.

    Receives messages from Telegram and processes them async.
    B.2.1: Verifies X-Telegram-Bot-Api-Secret-Token header.
    C.2.3: Returns 200 OK immediately, processes in background via Celery.
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
    Handle VK webhook (Callback API).

    Receives messages from VK and processes them async.
    B.2.2: Verifies VK 'secret' parameter.
    C.2.3: Returns 200 OK immediately, processes in background via Celery.
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
    Unified webhook endpoint.

    Accepts messages from any channel and routes them async.
    Applies per-channel secret verification.
    C.2.3: Returns 200 OK immediately, processes in background via Celery.
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

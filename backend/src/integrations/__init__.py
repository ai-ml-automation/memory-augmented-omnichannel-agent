"""
Integrations Package
Channel gateways for messengers
"""

from backend.src.integrations.max_gateway import MAXGateway
from backend.src.integrations.telegram_gateway import TelegramGateway
from backend.src.integrations.vk_gateway import VKGateway

__all__ = ["MAXGateway", "TelegramGateway", "VKGateway"]

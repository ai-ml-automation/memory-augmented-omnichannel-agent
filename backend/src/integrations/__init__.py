"""
Пакет интеграций: шлюзы мессенджеров.

Реэкспорт-фасад: MAXGateway, TelegramGateway, VKGateway — публичный
контракт пакета (__all__ фиксирует его). VoiceGateway и VoiceProcessor
намеренно не реэкспортируются: голосовой конвейер используется через
voice_service, а не как часть фасада интеграций.
"""

from backend.src.integrations.max_gateway import MAXGateway
from backend.src.integrations.telegram_gateway import TelegramGateway
from backend.src.integrations.vk_gateway import VKGateway

__all__ = ["MAXGateway", "TelegramGateway", "VKGateway"]

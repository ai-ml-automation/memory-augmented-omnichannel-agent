"""
Шлюз голосовых каналов (SIP, WebRTC, телефония).

Назначение: единая точка интеграции голосовых каналов — входящие
звонки, отправка аудио, завершение звонка и статусы.
Почему два класса в одном модуле: VoiceGateway отвечает за жизненный
цикл звонка (сигнализация), VoiceProcessor — за контентную обработку
(ASR → память → LLM → TTS); это разные обязанности одной области.
Почему гейт ENABLE_VOICE: без флага все методы возвращают failure
без исключений — отключённый канал не должен ронять конвейер.
"""

import logging
import uuid
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VoiceGateway:
    """
    Шлюз голосовых каналов.

    Поддерживаемые виды транспорта:
    - SIP (через OPAL/Opalvoip)
    - WebRTC (через aiortc)
    - Телефонные провайдеры (Маруся, SberStanza)

    Реализации методов — заглушки-стабы: интеграция с конкретными
    провайдерами телефонии подключается позже (точки TODO), контракт
    сигнализации (call_id, статусы) уже зафиксирован.
    """

    def __init__(self):
        self._sip_client = None
        self._webrtc_peer = None

    async def handle_incoming_call(
        self,
        caller_id: str,
        call_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Обработать входящий звонок.

        Почему call_id генерируется здесь: звонок должен иметь
        идентификатор для последующих send_audio_response/end_call,
        даже если провайдер его не прислал.

        Args:
            caller_id: Идентификатор звонящего.
            call_id: Идентификатор звонка (генерируется при отсутствии).

        Returns:
            {success, call_id, caller_id, status} — при выключенном
            ENABLE_VOICE возвращает {success: False, error: "Voice
            disabled"} без исключений.
        """
        if not settings.ENABLE_VOICE:
            return {
                "success": False,
                "error": "Voice disabled",
            }

        try:
            # Generate call ID if not provided
            if not call_id:
                call_id = str(uuid.uuid4())

            logger.info(f"Incoming call: {caller_id} (call: {call_id})")

            # TODO: Integrate with telephony provider
            # For now, return placeholder

            return {
                "success": True,
                "call_id": call_id,
                "caller_id": caller_id,
                "status": "connected",
            }

        except Exception as e:
            logger.error(f"Call handling error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def send_audio_response(
        self,
        call_id: str,
        audio_data: bytes,
        **kwargs: Any,
    ) -> bool:
        """
        Отправить аудио-ответ звонящему.

        Почему вход в байтах, а не файлом: аудио приходит из TTS в
        памяти (WAV-bytes), и передача без записи на диск не оставляет
        следов — приватность 152-ФЗ.

        Args:
            call_id: Идентификатор звонка.
            audio_data: Аудио-данные для отправки.

        Returns:
            True при успешной отправке.
        """
        if not settings.ENABLE_VOICE:
            return False

        try:
            logger.info(f"Sending audio to call {call_id}")

            # TODO: Send audio via telephony provider
            return True

        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            return False

    async def end_call(
        self,
        call_id: str,
        **kwargs: Any,
    ) -> bool:
        """
        Завершить голосовой звонок.

        Args:
            call_id: Идентификатор звонка.

        Returns:
            True при успешном завершении.
        """
        if not settings.ENABLE_VOICE:
            return False

        try:
            logger.info(f"Ending call {call_id}")

            # TODO: End call via telephony provider
            return True

        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False

    async def get_call_status(
        self,
        call_id: str,
    ) -> dict[str, Any]:
        """
        Получить статус звонка.

        Заглушка: без интеграции с провайдером телефонии статус всегда
        unknown с нулевой длительностью — контракт зафиксирован, данные
        появятся после подключения реального транспорта.

        Args:
            call_id: Идентификатор звонка.

        Returns:
            {call_id, status, duration}.
        """
        return {
            "call_id": call_id,
            "status": "unknown",
            "duration": 0,
        }


class VoiceProcessor:
    """
    Обработка голосового сообщения полным конвейером:
    ASR → поиск памяти → LLM → TTS (Phase C.3.3).

    Пока генерация контента не подключена (TODO: поиск памяти и LLM),
    ответ формируется эхом: «Вы сказали: <распознанный текст>» — чтобы
    конвейер был проверяемым от ASR до TTS без внешних зависимостей.
    """

    def __init__(self, db: Any):
        self.db = db

    async def process(
        self,
        audio_data: bytes,
        caller_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Обработать голосовое сообщение.

        Почему SpeechService импортируется внутри метода: сервис речи
        тяжёлый (модели/клиенты SpeechKit), локальный импорт избегает
        загрузки при импорте модуля — асинхронный конвейер не должен
        платить за это на старте.

        Args:
            audio_data: Аудио голосового сообщения.
            caller_id: Идентификатор звонящего.

        Returns:
            {success, text, audio, confidence} при успехе; при сбое ASR —
            {success: False, error} с причиной.
        """
        from backend.src.services.speech_service import SpeechService

        # 1. ASR: Speech to text
        speech_service = SpeechService()
        asr_result = await speech_service.speech_to_text(audio_data)

        if not asr_result["success"]:
            return {
                "success": False,
                "error": f"ASR failed: {asr_result['error']}",
            }

        text = asr_result["text"]

        # 2. Memory search
        # TODO: Get user_id from caller_id
        # memory_service = MemorySearchService(self.db)
        # context = await memory_service.get_memory_context(...)

        # 3. LLM generation
        # TODO: Generate response with context

        # 4. TTS: Text to speech
        tts_result = await speech_service.text_to_speech(
            text=f"Вы сказали: {text}",
            voice="alena",
        )

        return {
            "success": True,
            "text": text,
            "audio": tts_result.get("audio"),
            "confidence": asr_result.get("confidence", 0),
        }

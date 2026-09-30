"""
Сервис речи: распознавание (ASR) и синтез (TTS) через Yandex SpeechKit.

Предоставляет единый интерфейс поверх облачного SpeechKit: клиенты ASR и TTS
инициализируются лениво (при первом использовании) и только при включённых
флагах ENABLE_ASR/ENABLE_TTS.

Ключевые решения:
- ленивые клиенты: приложение стартует и тестируется без speechkit и токенов;
- все ошибки превращаются в словарь с текстом ошибки (fail-open для каналов);
- аудио для ASR пишется во временный файл — SpeechKit принимает путь к файлу.
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SpeechService:
    """
    Сервис обработки речи: ASR (речь → текст) и TTS (текст → речь).

    Жизненный цикл: лёгкий объект, клиенты speechkit создаются лениво
    и переиспользуются между вызовами (слоты _asr_client/_tts_client).

    Почему один сервис на оба направления: ASR и TTS используют один SDK
    (speechkit) и общие настройки (YANDEX_OAUTH_TOKEN, YANDEX_FOLDER_ID),
    что упрощает конфигурацию и замену провайдера (Whisper/Silero — локальные).
    """

    def __init__(self):
        """
        Пустой сервис без загрузки SDK.

        Клиенты ASR/TTS заполняются лениво (см. _get_asr_client/_get_tts_client),
        поэтому конструктор не требует сети и установленного speechkit.
        """
        self._asr_client = None
        self._tts_client = None

    def _get_asr_client(self) -> Any:
        """
        Ленивая инициализация клиента распознавания речи (SpeechKit).

        Загрузка SDK и создание сессии происходят только при первом вызове:
        если ENABLE_ASR=false — ошибка, не создающая клиент. При отсутствии
        пакета speechkit поднимается RuntimeError с понятным сообщением.

        Returns:
            клиент speechkit.Session для ASR
        """
        if self._asr_client is None:
            if not settings.ENABLE_ASR:
                raise RuntimeError("ASR disabled (ENABLE_ASR=false)")

            try:
                # Yandex SpeechKit for ASR
                import speechkit

                self._asr_client = speechkit.Session(
                    oauth_token=settings.YANDEX_OAUTH_TOKEN,
                    folder_id=settings.YANDEX_FOLDER_ID,
                )
                logger.info("ASR client initialized (Yandex SpeechKit)")
            except ImportError:
                raise RuntimeError("speechkit package not installed")

        return self._asr_client

    def _get_tts_client(self) -> Any:
        """
        Ленивая инициализация клиента синтеза речи (SpeechKit).

        Аналогично ASR-клиенту: создаётся при первом использовании, требует
        ENABLE_TTS=true и установленный пакет speechkit; ошибки — RuntimeError.

        Returns:
            клиент speechkit.Session для TTS
        """
        if self._tts_client is None:
            if not settings.ENABLE_TTS:
                raise RuntimeError("TTS disabled (ENABLE_TTS=false)")

            try:
                # Yandex SpeechKit for TTS
                import speechkit

                self._tts_client = speechkit.Session(
                    oauth_token=settings.YANDEX_OAUTH_TOKEN,
                    folder_id=settings.YANDEX_FOLDER_ID,
                )
                logger.info("TTS client initialized (Yandex SpeechKit)")
            except ImportError:
                raise RuntimeError("speechkit package not installed")

        return self._tts_client

    async def speech_to_text(
        self,
        audio_data: bytes,
        language: str = "ru-RU",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Распознавание речи: аудио → текст.

        При ENABLE_ASR=false сразу возвращается ошибка без обращения к SDK.
        Аудио сохраняется во временный файл (SpeechKit принимает путь, а не
        байты), файл удаляется в finally — не оставляем следов аудио на диске
        (защита персональных данных, 152-ФЗ).

        Args:
            audio_data: аудио в байтах (PCM, WAV, OGG)
            language: код языка (ru-RU по умолчанию)

        Returns:
            dict: text, success, confidence; при ошибке — text="" и error
        """
        if not settings.ENABLE_ASR:
            return {
                "text": "",
                "success": False,
                "error": "ASR disabled",
            }

        try:
            client = self._get_asr_client()

            # Save audio to temp file
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            try:
                # Recognize speech
                result = client.recognize(
                    tmp_path,
                    language=language,
                )

                return {
                    "text": result.text if result else "",
                    "success": True,
                    "confidence": getattr(result, "confidence", 0.0),
                }
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"ASR error: {e}")
            return {
                "text": "",
                "success": False,
                "error": str(e),
            }

    async def text_to_speech(
        self,
        text: str,
        voice: str = "alena",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Синтез речи: текст → аудио.

        При ENABLE_TTS=false возвращается ошибка без обращения к SDK. Голоса
        SpeechKit (alena, filipp, ermil) и скорость задаются параметрами вызова.

        Args:
            text: текст для озвучивания
            voice: имя голоса (alena, filipp, ermil)
            speed: скорость речи (1.0 — нормальная)

        Returns:
            dict: audio, success, duration; при ошибке — audio=None и error
        """
        if not settings.ENABLE_TTS:
            return {
                "audio": None,
                "success": False,
                "error": "TTS disabled",
            }

        try:
            client = self._get_tts_client()

            # Synthesize speech
            result = client.synthesize(
                text,
                voice=voice,
                speed=speed,
            )

            return {
                "audio": result.audio if result else None,
                "success": True,
                "duration": getattr(result, "duration", 0),
            }

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {
                "audio": None,
                "success": False,
                "error": str(e),
            }

    async def process_voice_message(
        self,
        audio_data: bytes,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Обработка голосового сообщения: ASR → текст.

        Утилитарный вариант без памяти и LLM: только распознавание речи.
        Используется там, где нужен текст без полного голосового сценария
        (например, в тестах и простых каналах).

        Args:
            audio_data: аудио голосового сообщения

        Returns:
            dict: success, text, confidence; при ошибке — error
        """
        # 1. ASR: Speech to text
        asr_result = await self.speech_to_text(audio_data)

        if not asr_result["success"]:
            return {
                "success": False,
                "error": f"ASR failed: {asr_result['error']}",
            }

        return {
            "success": True,
            "text": asr_result["text"],
            "confidence": asr_result.get("confidence", 0),
        }

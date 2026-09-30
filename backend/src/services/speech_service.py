"""
Speech Service
ASR (Automatic Speech Recognition) and TTS (Text-to-Speech)
"""

import logging
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SpeechService:
    """
    Speech processing service.

    Supports:
    - ASR: Speech-to-text (Yandex SpeechKit, Whisper)
    - TTS: Text-to-speech (Yandex SpeechKit, Coqui)
    """

    def __init__(self):
        self._asr_client = None
        self._tts_client = None

    def _get_asr_client(self) -> Any:
        """Lazy initialization of ASR client."""
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
        """Lazy initialization of TTS client."""
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
        Convert speech to text.

        Args:
            audio_data: Audio data (PCM, WAV, OGG)
            language: Language code

        Returns:
            Transcription result
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
        Convert text to speech.

        Args:
            text: Text to speak
            voice: Voice name (alena, filipp, ermil)
            speed: Speech speed

        Returns:
            Audio result
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
        Process voice message: ASR → LLM → TTS.

        Args:
            audio_data: Voice message audio

        Returns:
            Processing result
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

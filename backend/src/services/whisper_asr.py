"""
Whisper ASR Service
OpenAI Whisper for speech-to-text (Phase D.3.1).
Lazy initialization — model loaded only on first use.
"""

import logging
import tempfile
import os
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhisperASR:
    """
    Whisper-based ASR with lazy initialization.
    Phase D.3.1: Model loaded only on first process_audio call.
    """

    def __init__(self):
        self._model = None

    def _get_model(self) -> Any:
        """Lazy load Whisper model."""
        if self._model is None:
            if not settings.ENABLE_ASR:
                raise RuntimeError("ASR disabled (ENABLE_ASR=false)")

            try:
                import whisper

                model_name = settings.WHISPER_MODEL or "base"
                self._model = whisper.load_model(model_name)
                logger.info("Whisper model loaded: %s", model_name)
            except ImportError:
                raise RuntimeError(
                    "openai-whisper package not installed. "
                    "Install with: pip install openai-whisper"
                )

        return self._model

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ru",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Transcribe audio to text using Whisper.

        Args:
            audio_data: Audio bytes (WAV, MP3, etc.)
            language: Language code (e.g., 'ru', 'en')

        Returns:
            Dict with text, success, confidence
        """
        if not settings.ENABLE_ASR:
            return {
                "text": "",
                "success": False,
                "error": "ASR disabled",
            }

        try:
            model = self._get_model()

            # Write audio to temp file (Whisper needs file path)
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            try:
                # Transcribe
                import asyncio
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: model.transcribe(
                        tmp_path,
                        language=language,
                    ),
                )

                text = result.get("text", "").strip()

                # Calculate average confidence from segments
                segments = result.get("segments", [])
                confidence = 0.0
                if segments:
                    avg_prob = sum(
                        s.get("avg_logprob", 0) for s in segments
                    ) / len(segments)
                    # Convert logprob to rough confidence (0-1)
                    confidence = min(1.0, max(0.0, (avg_prob + 5) / 5))

                return {
                    "text": text,
                    "success": True,
                    "confidence": confidence,
                    "language": result.get("language", language),
                }
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.error("Whisper transcription error: %s", e)
            return {
                "text": "",
                "success": False,
                "error": str(e),
            }

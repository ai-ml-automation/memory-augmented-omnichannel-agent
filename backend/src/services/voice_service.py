"""
Voice Service
Business logic for voice processing pipeline (Phase C.3.3).
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.services.llm_service import LLMService
from backend.src.services.memory_search_service import MemorySearchService
from backend.src.services.speech_service import SpeechService

logger = logging.getLogger(__name__)
settings = get_settings()


class VoiceService:
    """Voice processing pipeline: ASR -> Memory -> LLM -> TTS (Phase C.3.3)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.speech_service = SpeechService()
        self.memory_search = MemorySearchService(db)
        self.llm_service = LLMService()

    async def process_voice(
        self,
        audio_data: bytes,
        caller_id: str,
        language: str = "ru-RU",
    ) -> dict[str, Any]:
        """
        Process voice message through the full pipeline.

        ASR -> MemorySearch -> LLM -> TTS

        Returns:
            Dict with text, audio, confidence, error
        """
        if not settings.ENABLE_VOICE:
            return {"success": False, "error": "Voice processing disabled"}

        try:
            # 1. ASR: speech to text
            asr_result = await self.speech_service.speech_to_text(
                audio_data=audio_data,
                language=language,
            )
            if not asr_result.get("success"):
                return {"success": False, "error": asr_result.get("error", "ASR failed")}

            text = asr_result["text"]

            # 2. Memory search for context
            try:
                user_uuid = uuid.UUID(caller_id)
            except ValueError:
                user_uuid = None

            memory_context = ""
            if user_uuid:
                memory_context = await self.memory_search.get_memory_context(
                    user_id=user_uuid,
                    current_message=text,
                    max_facts=3,
                )

            # 3. LLM generation
            prompt_parts: list[str] = []
            if memory_context:
                prompt_parts.append(f"Контекст: {memory_context}")
            prompt_parts.append(f"Сообщение: {text}")
            prompt = "\n".join(prompt_parts)

            response_text = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7,
            )

            # 4. TTS: text to speech
            tts_result = await self.speech_service.text_to_speech(
                text=response_text,
                voice="alena",
                speed=1.0,
            )

            return {
                "success": True,
                "text": response_text,
                "audio": tts_result.get("audio"),
                "confidence": asr_result.get("confidence"),
                "error": None,
            }

        except Exception as e:
            logger.error("Voice pipeline error: %s", e)
            return {"success": False, "error": str(e)}

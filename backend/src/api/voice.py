"""
Voice Router
API endpoints for voice processing (Phase C.3.3).
Thin router — /process delegates to VoiceService.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.database import get_db
from backend.src.services.speech_service import SpeechService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceMessageRequest(BaseModel):
    """Voice message request schema."""
    caller_id: str
    language: str = "ru-RU"


class VoiceMessageResponse(BaseModel):
    """Voice message response schema."""
    success: bool
    text: str | None = None
    audio: bytes | None = None
    confidence: float | None = None
    error: str | None = None


class VoiceHealthCheck(BaseModel):
    """Voice health check schema."""
    asr_enabled: bool
    tts_enabled: bool
    voice_enabled: bool


@router.post("/transcribe", response_model=VoiceMessageResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = "ru-RU",
) -> VoiceMessageResponse:
    """
    Transcribe audio to text.

    Args:
        audio: Audio file
        language: Language code

    Returns:
        Transcription result
    """
    if not settings.ENABLE_ASR:
        return VoiceMessageResponse(
            success=False,
            error="ASR disabled",
        )

    try:
        audio_data = await audio.read()

        speech_service = SpeechService()
        result = await speech_service.speech_to_text(
            audio_data=audio_data,
            language=language,
        )

        return VoiceMessageResponse(
            success=result["success"],
            text=result.get("text"),
            confidence=result.get("confidence"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize")
async def synthesize_text(
    text: str,
    voice: str = "alena",
    speed: float = 1.0,
) -> dict[str, Any]:
    """
    Synthesize text to speech.

    Args:
        text: Text to speak
        voice: Voice name
        speed: Speech speed

    Returns:
        Audio result
    """
    if not settings.ENABLE_TTS:
        return {
            "success": False,
            "error": "TTS disabled",
        }

    try:
        speech_service = SpeechService()
        result = await speech_service.text_to_speech(
            text=text,
            voice=voice,
            speed=speed,
        )

        return {
            "success": result["success"],
            "audio": result.get("audio"),
            "duration": result.get("duration"),
            "error": result.get("error"),
        }

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process", response_model=VoiceMessageResponse)
async def process_voice_message(
    audio: UploadFile = File(...),
    caller_id: str = "unknown",
    db: AsyncSession = Depends(get_db),
) -> VoiceMessageResponse:
    """
    Process voice message: ASR -> Memory -> LLM -> TTS.
    C.3.3: Delegates to VoiceService.
    """
    if not settings.ENABLE_VOICE:
        return VoiceMessageResponse(
            success=False,
            error="Voice processing disabled",
        )

    try:
        audio_data = await audio.read()
        from backend.src.services.voice_service import VoiceService
        svc = VoiceService(db)
        result = await svc.process_voice(
            audio_data=audio_data,
            caller_id=caller_id,
        )

        return VoiceMessageResponse(
            success=result["success"],
            text=result.get("text"),
            audio=result.get("audio"),
            confidence=result.get("confidence"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error("Voice processing error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/stream")
async def voice_stream(websocket: Any) -> None:
    """
    WebSocket endpoint for real-time voice streaming.
    Phase D.3.4: Receives audio chunks, processes, returns audio response.
    """

    await websocket.accept()

    if not settings.ENABLE_VOICE:
        await websocket.send_json({
            "type": "error",
            "message": "Voice processing disabled",
        })
        await websocket.close()
        return

    try:
        while True:
            # Receive audio chunk
            data = await websocket.receive_bytes()

            # Process: ASR -> text -> LLM -> TTS -> audio
            from backend.src.services.whisper_asr import WhisperASR

            # Transcribe
            asr = WhisperASR()
            asr_result = await asr.transcribe(data)

            if not asr_result["success"]:
                await websocket.send_json({
                    "type": "error",
                    "message": f"ASR failed: {asr_result.get('error')}",
                })
                continue

            # Send transcription
            await websocket.send_json({
                "type": "transcription",
                "text": asr_result["text"],
                "confidence": asr_result.get("confidence", 0),
            })

            # Generate response (would need LLM here - simplified for now)
            response_text = f"Получено: {asr_result['text']}"

            # Synthesize response
            from backend.src.services.silero_tts import SileroTTS
            tts = SileroTTS()
            tts_result = await tts.synthesize(response_text)

            if tts_result["success"]:
                await websocket.send_bytes(tts_result["audio"])
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"TTS failed: {tts_result.get('error')}",
                })

    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/health", response_model=VoiceHealthCheck)
async def voice_health_check() -> VoiceHealthCheck:
    """
    Check voice service health.

    Returns:
        Voice service status
    """
    return VoiceHealthCheck(
        asr_enabled=settings.ENABLE_ASR,
        tts_enabled=settings.ENABLE_TTS,
        voice_enabled=settings.ENABLE_VOICE,
    )

"""
Голосовой роутер: API обработки голоса (Phase C.3.3).

Точка входа голосового канала: транскрибация (ASR), синтез (TTS), полный
конвейер ASR -> Memory -> LLM -> TTS, стриминг по WebSocket и health-check.
Каждая операция гейтится своим флагом конфигурации (ENABLE_ASR / ENABLE_TTS /
ENABLE_VOICE) — если фича выключена, отдаётся аккуратный ответ с success=False
вместо 500. Тонкий роутер: обработка делегируется SpeechService и
VoiceService, здесь только UploadFile-параметры и формат ответа.
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
    """Запрос голосового сообщения: кто звонит и на каком языке.

    caller_id — идентификатор абонента, по которому память привязывается
    к конкретному пользователю в голосовом канале.
    """

    caller_id: str
    language: str = "ru-RU"


class VoiceMessageResponse(BaseModel):
    """Ответ голосового канала.

    Успех отделён от данных: даже при ошибке конвейера возвращается
    success=False + error вместо HTTP-500 — клиент (IVR/телефония) может
    корректно обработать сбой и сказать абоненту понятный текст.
    """

    success: bool
    text: str | None = None
    audio: bytes | None = None
    confidence: float | None = None
    error: str | None = None


class VoiceHealthCheck(BaseModel):
    """Состояние голосовых компонентов.

    Отдельно ASR, TTS и общий конвейер: по этим флагам клиент (IVR/фронтенд)
    понимает, какие операции доступны, и не предлагает недоступные.
    """

    asr_enabled: bool
    tts_enabled: bool
    voice_enabled: bool


@router.post("/transcribe", response_model=VoiceMessageResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = "ru-RU",
) -> VoiceMessageResponse:
    """
    Транскрибация аудио в текст (ASR).

    Гейт ENABLE_ASR: если распознавание выключено, не тратим ресурсы
    на обработку файла — сразу возвращаем success=False. При ошибке
    распознавания — 500 с текстом ошибки (это уже сбой, а не флаг).

    Args:
        audio: Аудиофайл для распознавания.
        language: Код языка (по умолчанию ru-RU).

    Returns:
        Распознанный текст + уверенность, либо ошибка.

    Raises:
        500: Сбой распознавания.
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
    Синтез речи из текста (TTS).

    Гейт ENABLE_TTS аналогичен ASR: выключенный синтез не обрабатывается.
    Параметры voice и speed дают голосовому каналу управлять тембром и темпом.

    Args:
        text: Текст для озвучивания.
        voice: Имя голоса (по умолчанию alena).
        speed: Скорость речи (1.0 — нормальная).

    Returns:
        Аудио + длительность, либо ошибка.

    Raises:
        500: Сбой синтеза.
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
    Полный голосовой конвейер: ASR -> Memory -> LLM -> TTS.

    C.3.3: делегирует VoiceService — тот распознаёт речь, достаёт память
    по caller_id, генерирует ответ и синтезирует его в аудио. Ленивый импорт
    VoiceService держит роутер лёгким при старте. Гейт ENABLE_VOICE отключает
    конвейер целиком.

    Args:
        audio: Аудиофайл абонента.
        caller_id: Идентификатор абонента (для памяти).
        db: Сессия БД.

    Returns:
        Текст + аудио-ответ + уверенность, либо ошибка.

    Raises:
        500: Сбой конвейера.
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
    WebSocket-стрим для реального времени (Phase D.3.4).

    Принимает чанки аудио от клиента, каждый чанк транскрибирует (WhisperASR),
    отдаёт транскрипцию, формирует ответ и синтезирует его в аудио (SileroTTS).
    Ошибки ASR/TTS отправляются как JSON-сообщения, а не рвут соединение, —
    клиент продолжает стримить. Если конвейер выключен — закрываем сразу.

    Args:
        websocket: Активное WebSocket-соединение.
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
    Состояние голосового сервиса.

    По флагам клиент (IVR/фронтенд) решает, какие кнопки показывать:
    если TTS выключен, незачем предлагать озвучку.

    Returns:
        Статус ASR, TTS и голосового конвейера.
    """
    return VoiceHealthCheck(
        asr_enabled=settings.ENABLE_ASR,
        tts_enabled=settings.ENABLE_TTS,
        voice_enabled=settings.ENABLE_VOICE,
    )

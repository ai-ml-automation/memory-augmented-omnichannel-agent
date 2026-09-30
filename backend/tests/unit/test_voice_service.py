"""
Unit Tests for VoiceService (Phase C.3.3)

Pure-mock тесты конвейера голосового канала:
ASR → поиск памяти → LLM → TTS и graceful handling сбоев на каждом звене.

Зачем pure-mock: проверяют оркестрацию голосового диалога без реальных
SpeechService/LLM — отключение голосового канала через ENABLE_VOICE,
короткое замыкание при ошибке распознавания, полный конвейер с передачей
контекста памяти и параметров синтеза речи.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Patch targets (match import names inside voice_service module)
# ---------------------------------------------------------------------------
_PATCH_SPEECH = "backend.src.services.voice_service.SpeechService"
_PATCH_MEMSEARCH = "backend.src.services.voice_service.MemorySearchService"
_PATCH_LLM = "backend.src.services.voice_service.LLMService"
_PATCH_SETTINGS = "backend.src.services.voice_service.settings"

_active_settings_patcher = None


def _make_svc(enable_voice: bool = True):
    """Создать VoiceService со всеми внутренними сервисами-моками.

    Патч settings запускается без context-manager (persistent), потому что
    process_voice читает модульную переменную settings в момент вызова,
    а не при конструировании. Caller обязан остановить patcher, либо
    следующий вызов _make_svc остановит предыдущий автоматически.

    Args:
        enable_voice: значение ENABLE_VOICE для мок-настроек.

    Returns:
        кортеж (VoiceService, mock_settings): сервис с замоканными
        speech_service/memory_search/llm_service и сами мок-настройки.
    """
    global _active_settings_patcher

    mock_db = MagicMock()

    # Create a mock settings object
    mock_settings = MagicMock()
    mock_settings.ENABLE_VOICE = enable_voice

    # Stop any previously-active settings patcher
    if _active_settings_patcher is not None:
        _active_settings_patcher.stop()
        _active_settings_patcher = None

    # Start persistent settings patch (survives context-manager exit)
    _active_settings_patcher = patch(_PATCH_SETTINGS, mock_settings)
    _active_settings_patcher.start()

    with patch(_PATCH_SPEECH) as SpeechCls, \
         patch(_PATCH_MEMSEARCH) as SearchCls, \
         patch(_PATCH_LLM) as LLMCls:

        from backend.src.services.voice_service import VoiceService

        svc = VoiceService(mock_db)
        svc.speech_service = SpeechCls.return_value
        svc.memory_search = SearchCls.return_value
        svc.llm_service = LLMCls.return_value

        return svc, mock_settings


# ---------------------------------------------------------------------------
# process_voice tests
# ---------------------------------------------------------------------------


class TestProcessVoice:
    """Группа тестов process_voice: конвейер ASR → память → LLM → TTS.

    Покрывают выключенный голосовой канал, короткое замыкание при сбое
    распознавания и полный конвейер с передачей контекста памяти.
    """

    @pytest.mark.asyncio
    async def test_process_voice_disabled_returns_error(self):
        """Ловит баг, если при ENABLE_VOICE=False канал не отключается.

        process_voice обязан сразу вернуть success=False с ошибкой,
        содержащей "disabled", и не трогать SpeechService/LLM. Пропуск
        проверки флага приведёт к попытке синтеза без провайдера.
        """
        svc, _settings = _make_svc(enable_voice=False)

        result = await svc.process_voice(
            audio_data=b"audio-bytes",
            caller_id=str(uuid.uuid4()),
        )

        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_process_voice_asr_failure(self):
        """Ловит баг, если сбой ASR не прерывает конвейер.

        При success=False из speech_to_text сервис обязан вернуть ошибку
        и НЕ вызывать ни поиск памяти, ни LLM. Продолжение конвейера
        после сбоя распознавания даст ответ на пустой/битый текст.
        """
        svc, _settings = _make_svc(enable_voice=True)

        svc.speech_service.speech_to_text = AsyncMock(
            return_value={"success": False, "error": "Audio too short"}
        )

        result = await svc.process_voice(
            audio_data=b"tiny",
            caller_id=str(uuid.uuid4()),
        )

        assert result["success"] is False
        assert result["error"] == "Audio too short"
        # Memory search and LLM should NOT have been called
        svc.memory_search.get_memory_context.assert_not_called()
        svc.llm_service.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_voice_full_pipeline(self):
        """Ловит баг, если полный голосовой конвейер теряет звено.

        Проверяет всю цепочку: распознанный текст уходит в поиск памяти
        (user_id, current_message, max_facts=3), промпт LLM содержит
        контекст памяти и текст запроса (max_tokens=500), а TTS вызывается
        с ответом, голосом "alena" и speed=1.0. Результат агрегирует
        текст, аудио, confidence и пустой error.
        """
        svc, _settings = _make_svc(enable_voice=True)

        # 1. ASR
        svc.speech_service.speech_to_text = AsyncMock(
            return_value={
                "success": True,
                "text": "Test voice input",
                "confidence": 0.95,
            }
        )

        # 2. Memory search
        svc.memory_search.get_memory_context = AsyncMock(
            return_value="User prefers email responses"
        )

        # 3. LLM
        svc.llm_service.generate = AsyncMock(
            return_value="Sure, I can help with that."
        )

        # 4. TTS
        svc.speech_service.text_to_speech = AsyncMock(
            return_value={"audio": b"wav-bytes"}
        )

        uid = uuid.uuid4()
        result = await svc.process_voice(
            audio_data=b"full-audio",
            caller_id=str(uid),
            language="ru-RU",
        )

        assert result["success"] is True
        assert result["text"] == "Sure, I can help with that."
        assert result["audio"] == b"wav-bytes"
        assert result["confidence"] == 0.95
        assert result["error"] is None

        # Verify memory search was called with correct args
        svc.memory_search.get_memory_context.assert_awaited_once_with(
            user_id=uid,
            current_message="Test voice input",
            max_facts=3,
        )

        # Verify LLM prompt includes memory context and user message
        svc.llm_service.generate.assert_awaited_once()
        llm_kwargs = svc.llm_service.generate.call_args.kwargs
        assert "User prefers email responses" in llm_kwargs["prompt"]
        assert "Test voice input" in llm_kwargs["prompt"]
        assert llm_kwargs["max_tokens"] == 500

        # Verify TTS was called with response
        svc.speech_service.text_to_speech.assert_awaited_once_with(
            text="Sure, I can help with that.",
            voice="alena",
            speed=1.0,
        )

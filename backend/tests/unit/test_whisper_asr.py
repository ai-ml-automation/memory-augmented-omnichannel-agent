"""
Unit Tests for WhisperASR Service (Phase D.3.1)

Pure-mock тесты распознавания речи — реальная модель Whisper не грузится.

Зачем эти тесты: ASR-канал зависит от внешней модели и флага ENABLE_ASR.
Тесты фиксируют graceful degradation (выключенный канал, отсутствующий
пакет whisper) и успешную транскрипцию с расчётом confidence.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


_PATCH_ASR_SETTINGS = "backend.src.services.whisper_asr.settings"


class TestWhisperASR:
    """Группа тестов WhisperASR.transcribe (D.3.1).

    Покрывают выключенный канал (ENABLE_ASR=False), отсутствующий
    пакет whisper и успешную транскрипцию с confidence.
    """

    @pytest.mark.asyncio
    @patch(_PATCH_ASR_SETTINGS)
    async def test_transcribe_disabled_returns_error(self, mock_settings):
        """Ловит баг, если при ENABLE_ASR=False канал не отключается.

        transcribe обязан вернуть success=False с пустым текстом и ошибкой
        "disabled", не трогая модель. Пропуск флага приведёт к попытке
        загрузить Whisper без необходимости и к падению в проде.
        """
        from backend.src.services.whisper_asr import WhisperASR

        mock_settings.ENABLE_ASR = False

        asr = WhisperASR()
        result = await asr.transcribe(b"fake-audio-data")

        assert result["success"] is False
        assert result["text"] == ""
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    @patch(_PATCH_ASR_SETTINGS)
    async def test_transcribe_model_not_installed(self, mock_settings):
        """Ловит баг, если отсутствие пакета whisper роняет transcribe.

        Когда модуль whisper недоступен (patch.dict sys.modules),
        transcribe обязан вернуть success=False с сообщением об ошибке,
        а не бросить исключение — ASR-канал деградирует мягко.
        """
        from backend.src.services.whisper_asr import WhisperASR

        mock_settings.ENABLE_ASR = True
        mock_settings.WHISPER_MODEL = "base"

        asr = WhisperASR()

        with patch.dict("sys.modules", {"whisper": None}):
            result = await asr.transcribe(b"fake-audio-data")

        # _get_model raises RuntimeError, caught by the generic handler
        assert result["success"] is False
        assert "not installed" in result["error"].lower() or "error" in result["error"].lower()

    @pytest.mark.asyncio
    @patch(_PATCH_ASR_SETTINGS)
    async def test_transcribe_success(self, mock_settings):
        """Ловит баг, если успешная транскрипция теряет текст/confidence.

        При замоканной модели transcribe обязан вернуть success=True,
        распознанный текст (кириллица), язык и confidence в диапазоне
        [0, 1], рассчитанный из avg_logprob сегментов.
        """
        from backend.src.services.whisper_asr import WhisperASR

        mock_settings.ENABLE_ASR = True
        mock_settings.WHISPER_MODEL = "base"

        # Mock the whisper module and its model
        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Привет, как дела?",
            "language": "ru",
            "segments": [
                {"avg_logprob": -0.5},
                {"avg_logprob": -0.3},
            ],
        }
        mock_whisper.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            asr = WhisperASR()
            result = await asr.transcribe(b"fake-audio-data")

        assert result["success"] is True
        assert result["text"] == "Привет, как дела?"
        assert result["language"] == "ru"
        assert 0.0 <= result["confidence"] <= 1.0

"""
Unit Tests for WhisperASR Service (Phase D.3.1)

Pure-mock tests — no actual Whisper model loading.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


_PATCH_ASR_SETTINGS = "backend.src.services.whisper_asr.settings"


class TestWhisperASR:
    """Tests for WhisperASR transcribe (D.3.1)."""

    @pytest.mark.asyncio
    @patch(_PATCH_ASR_SETTINGS)
    async def test_transcribe_disabled_returns_error(self, mock_settings):
        """When ENABLE_ASR=False, transcribe returns error dict."""
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
        """When whisper package is missing, RuntimeError is raised."""
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
        """When whisper is mocked, transcribe returns text and confidence."""
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

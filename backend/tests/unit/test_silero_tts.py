"""
Unit Tests for SileroTTS Service (Phase D.3.2)

Pure-mock тесты синтеза речи — модель и GPU не требуются.

Зачем эти тесты: TTS-канал зависит от torch и флага ENABLE_TTS.
Тесты фиксируют graceful degradation (выключенный канал, отсутствующий
torch) и успешный синтез WAV с корректными sample_rate и duration.
"""

from unittest.mock import MagicMock, patch

import pytest


_PATCH_TTS_SETTINGS = "backend.src.services.silero_tts.settings"


class TestSileroTTS:
    """Группа тестов SileroTTS.synthesize (D.3.2).

    Покрывают выключенный канал (ENABLE_TTS=False), отсутствующий
    torch и успешный синтез WAV-аудио.
    """

    @pytest.mark.asyncio
    @patch(_PATCH_TTS_SETTINGS)
    async def test_synthesize_disabled_returns_error(self, mock_settings):
        """Ловит баг, если при ENABLE_TTS=False канал не отключается.

        synthesize обязан вернуть success=False с audio=None и ошибкой
        "disabled". Пропуск флага приведёт к загрузке torch/Silero
        без необходимости и падению синтеза в проде.
        """
        from backend.src.services.silero_tts import SileroTTS

        mock_settings.ENABLE_TTS = False

        tts = SileroTTS()
        result = await tts.synthesize("Привет мир")

        assert result["success"] is False
        assert result["audio"] is None
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    @patch(_PATCH_TTS_SETTINGS)
    async def test_synthesize_model_not_installed(self, mock_settings):
        """Ловит баг, если отсутствие torch роняет synthesize.

        Когда модуль torch недоступен (patch.dict sys.modules),
        synthesize обязан вернуть success=False с audio=None, а не
        бросить исключение — TTS-канал деградирует мягко.
        """
        from backend.src.services.silero_tts import SileroTTS

        mock_settings.ENABLE_TTS = True

        tts = SileroTTS()

        with patch.dict("sys.modules", {"torch": None}):
            result = await tts.synthesize("Привет мир")

        assert result["success"] is False
        assert result["audio"] is None
        assert "error" in result

    @pytest.mark.asyncio
    @patch(_PATCH_TTS_SETTINGS)
    async def test_synthesize_success(self, mock_settings):
        """Ловит баг, если успешный синтез теряет WAV или метаданные.

        При замоканных torch/Silero synthesize обязан вернуть success=True,
        WAV-байты с сигнатурой RIFF, sample_rate=24000 и положительную
        длительность — без них голосовой канал не отдаст аудио клиенту.
        """
        from backend.src.services.silero_tts import SileroTTS

        mock_settings.ENABLE_TTS = True

        # Build a mock torch module with hub.load returning a model
        import numpy as np

        mock_torch = MagicMock()
        # audio_tensor: a 1-D numpy-compatible array
        audio_array = np.sin(
            np.linspace(0, 2 * 3.14159, 24000, dtype=np.float32)
        ) * 0.5
        mock_audio_tensor = MagicMock()
        mock_audio_tensor.numpy.return_value = audio_array
        mock_audio_tensor.__len__ = lambda self: len(audio_array)

        mock_model = MagicMock()
        mock_model.apply_tts.return_value = mock_audio_tensor

        mock_torch.hub.load.return_value = (mock_model, "example text")
        mock_torch.float32 = np.float32

        with patch.dict("sys.modules", {"torch": mock_torch}):
            tts = SileroTTS()
            result = await tts.synthesize("Привет мир")

        assert result["success"] is True
        assert isinstance(result["audio"], bytes)
        assert result["audio"][:4] == b"RIFF"  # WAV header
        assert result["sample_rate"] == 24000
        assert result["duration"] > 0

"""
Silero TTS Service
Open-source text-to-speech using Silero models (Phase D.3.2).
Lazy initialization — model loaded only on first use.
"""

import logging
import io
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SileroTTS:
    """
    Silero-based TTS with lazy initialization.
    Phase D.3.2: Model loaded only on first synthesize call.
    """

    def __init__(self):
        self._model = None
        self._sample_rate = 24000

    def _get_model(self) -> Any:
        """Lazy load Silero TTS model."""
        if self._model is None:
            if not settings.ENABLE_TTS:
                raise RuntimeError("TTS disabled (ENABLE_TTS=false)")

            try:
                import torch

                model, example_text = torch.hub.load(
                    repo_or_dir="snakers4/silero-models",
                    model="silero_tts",
                    language="ru",
                    source="github",
                )
                self._model = model
                logger.info("Silero TTS model loaded")
            except ImportError:
                raise RuntimeError(
                    "torch package not installed. "
                    "Install with: pip install torch"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load Silero model: {e}")

        return self._model

    async def synthesize(
        self,
        text: str,
        voice: str = "ru_4",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Synthesize text to speech using Silero.

        Args:
            text: Text to speak
            voice: Voice ID (ru_0, ru_1, ..., ru_4)
            speed: Speech speed (0.5 - 2.0)

        Returns:
            Dict with audio bytes, sample_rate, success
        """
        if not settings.ENABLE_TTS:
            return {
                "audio": None,
                "success": False,
                "error": "TTS disabled",
            }

        try:
            model = self._get_model()
            import asyncio

            loop = asyncio.get_event_loop()

            def _synthesize():
                return model.apply_tts(
                    text=text,
                    speaker=voice,
                    sample_rate=self._sample_rate,
                    put_accent=True,
                    put_yo=True,
                )

            audio_tensor = await loop.run_in_executor(None, _synthesize)

            # Convert tensor to WAV bytes
            audio_bytes = self._tensor_to_wav(audio_tensor)

            return {
                "audio": audio_bytes,
                "success": True,
                "sample_rate": self._sample_rate,
                "duration": len(audio_tensor) / self._sample_rate,
            }

        except Exception as e:
            logger.error("Silero TTS error: %s", e)
            return {
                "audio": None,
                "success": False,
                "error": str(e),
            }

    def _tensor_to_wav(self, audio_tensor: Any) -> bytes:
        """Convert PyTorch tensor to WAV bytes."""
        import struct

        # Normalize to 16-bit PCM
        audio = audio_tensor.numpy()
        max_val = max(abs(audio.max()), abs(audio.min()))
        if max_val > 0:
            audio = (audio / max_val * 32767).astype("int16")
        else:
            audio = audio.astype("int16")

        # Write WAV header
        num_channels = 1
        sample_width = 2  # 16-bit
        byte_rate = self._sample_rate * num_channels * sample_width
        block_align = num_channels * sample_width
        data_size = len(audio) * sample_width

        buf = io.BytesIO()
        # RIFF header
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        # fmt chunk
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))  # chunk size
        buf.write(struct.pack("<H", 1))  # PCM
        buf.write(struct.pack("<H", num_channels))
        buf.write(struct.pack("<I", self._sample_rate))
        buf.write(struct.pack("<I", byte_rate))
        buf.write(struct.pack("<H", block_align))
        buf.write(struct.pack("<H", sample_width * 8))
        # data chunk
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(audio.tobytes())

        return buf.getvalue()

    def reset(self) -> None:
        """Reset model (release memory)."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Silero TTS model reset")

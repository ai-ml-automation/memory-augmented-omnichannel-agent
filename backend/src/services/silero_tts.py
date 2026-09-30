"""
Синтез речи открытой моделью Silero TTS (Phase D.3.2).

Почему локальная модель: текст ответа может содержать персональные данные
пользователя, поэтому он не должен отправляться в облачные TTS (152-ФЗ);
Silero работает полностью на сервере.

Ключевые решения:
- модель загружается лениво (torch.hub.load) при первом синтезе;
- синтез выполняется в executor — не блокирует event loop;
- выходной тензор конвертируется в WAV-байты вручную (без внешних
  аудио-библиотек).
"""

import logging
import io
from typing import Any

from backend.src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SileroTTS:
    """
    Синтез речи на базе Silero с ленивой загрузкой модели.

    Жизненный цикл: лёгкий объект; модель загружается при первом synthesize
    и переиспользуется; reset() освобождает модель (память/GPU).

    Почему Silero, а не облако: полностью локальная модель с русскими голосами,
    отсутствие внешних вызовов — ключевое требование приватности (152-ФЗ).
    """

    def __init__(self):
        """
        Пустой сервис с фиксированной частотой дискретизации.

        Модель загружается лениво; _sample_rate=24000 используется и для
        синтеза (Silero выводит 24 кГц), и для заголовка WAV-файла.
        """
        self._model = None
        self._sample_rate = 24000

    def _get_model(self) -> Any:
        """
        Ленивая загрузка модели Silero TTS.

        Модель загружается через torch.hub из репозитория snakers4/silero-models
        (русская версия). ENABLE_TTS=false → RuntimeError; отсутствие torch —
        RuntimeError; сбой загрузки модели — RuntimeError с причиной.

        Returns:
            загруженная модель Silero TTS
        """
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
        Синтез речи: текст → WAV-аудио.

        Синхронный вызов модели (может занимать заметное время) выполняется
        в executor. Включены put_accent и put_yo — корректная расстановка
        ударений и буквы ё для естественного русского звучания.

        Args:
            text: текст для озвучивания
            voice: идентификатор голоса (ru_0 ... ru_4)
            speed: скорость речи (0.5–2.0)

        Returns:
            dict: audio (WAV-байты), success, sample_rate, duration;
                при ошибке — audio=None и error
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
        """
        Конвертация тензора PyTorch в WAV-байты (16-bit PCM).

        WAV-заголовок (RIFF/fmt/data) собирается вручную через struct.pack —
        это исключает зависимость от аудио-библиотек. Тензор нормализуется
        к максимальной амплитуде int16 перед записью.

        Args:
            audio_tensor: тензор аудио (float32, 1 канал)

        Returns:
            bytes: WAV-файл с частотой _sample_rate
        """
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
        """
        Сброс модели для освобождения памяти.

        Удаляет ссылку на модель (del + None), позволяя сборщику мусора
        освободить память CPU/GPU. Нужен при длительных простоях голосового
        сценария или в тестах для очистки состояния.
        """
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Silero TTS model reset")

"""
Распознавание речи локальной моделью OpenAI Whisper (Phase D.3.1).

Почему локальная модель, а не облачный API: аудио с персональными данными
не покидает сервер (152-ФЗ), нет зависимости от сети и внешнего провайдера.

Ключевые решения:
- модель загружается лениво при первом распознавании — старт приложения без
  тяжёлого ML-стека (модель объёмом сотни МБ);
- Whisper синхронный и долгий — вызов выполняется в executor, чтобы не
  блокировать event loop;
- аудио пишется во временный файл: Whisper принимает путь, а не байты.
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
    Распознавание речи на базе Whisper с ленивой загрузкой модели.

    Жизненный цикл: лёгкий объект; модель whisper.load_model создаётся при
    первом transcribe и переиспользуется (слот _model).

    Почему переиспользование: загрузка модели — самая дорогая операция
    (секунды и сотни МБ памяти), повторная загрузка на каждый запрос
    сделала бы голосовой сценарий непригодным для реального использования.
    """

    def __init__(self):
        """
        Пустой сервис: модель не загружается при создании.

        Слот _model заполняется лениво в _get_model; конструктор не требует
        установленного whisper и не потребляет память модели.
        """
        self._model = None

    def _get_model(self) -> Any:
        """
        Ленивая загрузка модели Whisper.

        Модель (WHISPER_MODEL, по умолчанию "base") загружается один раз.
        При ENABLE_ASR=false — RuntimeError без загрузки; при отсутствии
        пакета openai-whisper — RuntimeError с инструкцией установки.

        Returns:
            загруженная модель whisper
        """
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
        Распознавание аудио в текст.

        Аудио сохраняется во временный файл и удаляется в finally (аудио — это
        персональные данные, следов на диске оставаться не должно). Синхронный
        вызов модели выполняется в run_in_executor — транскрибация может занять
        секунды и не должна блокировать обработку других запросов.

        Достоверность (confidence) пересчитывается из среднего avg_logprob
        сегментов в диапазон 0..1.

        Args:
            audio_data: аудио в байтах (WAV, MP3 и др.)
            language: код языка ('ru', 'en')

        Returns:
            dict: text, success, confidence, language; при ошибке — error
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

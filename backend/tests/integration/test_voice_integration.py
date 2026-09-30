"""
V.3: Интеграционные тесты голосового пайплайна.

Проверяют эндпоинты транскрибации и синтеза через HTTP-клиент:
transcribe принимает WAV и возвращает текст, synthesize отдаёт
аудио; оба отклоняют пустой ввод. Требуют ENABLE_VOICE=true и
работающие TTS/STT; аудио-фикстура — backend/tests/fixtures/audio/test.wav
(при отсутствии генерируется generate_audio.py).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient

VOICE_ENABLED = os.environ.get("ENABLE_VOICE", "false").lower() == "true"
AUDIO_DIR = Path(__file__).parent.parent / "fixtures" / "audio"
AUDIO_PATH = AUDIO_DIR / "test.wav"


def _ensure_audio_fixture() -> Path:
    """Генерирует test.wav, если файла нет, и возвращает путь к нему.

    Returns:
        Path: путь к существующему WAV-фикстуре.
    """
    if not AUDIO_PATH.exists():
        script = AUDIO_DIR / "generate_audio.py"
        subprocess.run(
            [sys.executable, str(script)],
            check=True,
            cwd=str(AUDIO_DIR),
        )
    return AUDIO_PATH


@pytest.mark.skipif(not VOICE_ENABLED, reason="Voice disabled (ENABLE_VOICE not set)")
class TestVoiceTranscribe:
    """Группа тестов транскрибации: /voice/transcribe при включённом голосе.

    Покрывают успешный путь (WAV → текст) и отклонение пустого
    аудио. Активны только при ENABLE_VOICE=true (V.3).
    """

    @pytest.mark.asyncio
    async def test_transcribe_returns_text(self, client: AsyncClient):
        """Ловит поломку ASR-пути: валидный WAV не превращается в текст.

        Отправляем реальный WAV-файл с параметром ru-RU и ждём
        success=True с непустым текстом (V.3).
        """
        audio_path = _ensure_audio_fixture()
        audio_data = audio_path.read_bytes()
        response = await client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", audio_data, "audio/wav")},
            params={"language": "ru-RU"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["text"] is not None
        assert len(data["text"]) > 0

    @pytest.mark.asyncio
    async def test_transcribe_rejects_empty_audio(self, client: AsyncClient):
        """Ловит обработку пустого аудио: сервис не должен молча падать.

        Пустой файл обязан завершиться ошибкой 4xx/5xx, а не висеть
        или возвращать успех с мусором.
        """
        response = await client.post(
            "/voice/transcribe",
            files={"audio": ("empty.wav", b"", "audio/wav")},
            params={"language": "ru-RU"},
        )
        assert response.status_code in (400, 422, 500)


@pytest.mark.skipif(not VOICE_ENABLED, reason="Voice disabled (ENABLE_VOICE not set)")
class TestVoiceSynthesize:
    """Группа тестов синтеза: /voice/synthesize при включённом голосе.

    Покрывают успешный путь (текст → аудио-байты) и отклонение
    пустого текста. Активны только при ENABLE_VOICE=true (V.3).
    """

    @pytest.mark.asyncio
    async def test_synthesize_returns_audio(self, client: AsyncClient):
        """Ловит поломку TTS-пути: текст не превращается в аудио-байты.

        Синтез «Hello world» голосом alena обязан вернуть success=True
        и непустой аудио-буфер (base64) заметной длины (V.3).
        """
        response = await client.post(
            "/voice/synthesize",
            json={"text": "Hello world", "voice": "alena"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["audio"] is not None
        assert len(data["audio"]) > 1000

    @pytest.mark.asyncio
    async def test_synthesize_rejects_empty_text(self, client: AsyncClient):
        """Ловит синтез пустого текста: должен быть отклонён валидацией.

        Пустая строка не может быть озвучена — API обязан вернуть
        400/422, а не пытаться синтезировать мусор.
        """
        response = await client.post(
            "/voice/synthesize",
            json={"text": "", "voice": "alena"},
        )
        assert response.status_code in (400, 422)

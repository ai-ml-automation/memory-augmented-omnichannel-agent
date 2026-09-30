"""
V.3: Voice Pipeline Integration Tests
Tests for voice transcribe and synthesize endpoints.

Requires ENABLE_VOICE=true and working TTS/STT services.
Audio fixture: backend/tests/fixtures/audio/test.wav
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
    """Generate test.wav if missing."""
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

    @pytest.mark.asyncio
    async def test_transcribe_returns_text(self, client: AsyncClient):
        """Transcribe a short WAV -> text."""
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
        """Empty audio file -> error."""
        response = await client.post(
            "/voice/transcribe",
            files={"audio": ("empty.wav", b"", "audio/wav")},
            params={"language": "ru-RU"},
        )
        assert response.status_code in (400, 422, 500)


@pytest.mark.skipif(not VOICE_ENABLED, reason="Voice disabled (ENABLE_VOICE not set)")
class TestVoiceSynthesize:

    @pytest.mark.asyncio
    async def test_synthesize_returns_audio(self, client: AsyncClient):
        """Text -> audio bytes."""
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
        """Empty text -> error."""
        response = await client.post(
            "/voice/synthesize",
            json={"text": "", "voice": "alena"},
        )
        assert response.status_code in (400, 422)

"""
Generate test.wav fixture for voice pipeline integration tests.

Creates a 2-second 440Hz sine wave at 16kHz mono — sufficient for
testing STT/TTS HTTP contracts without real speech.
"""

import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 16000
DURATION = 2.0
FREQUENCY = 440  # A4


def generate(output_path: str = "test.wav") -> str:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    audio = np.sin(2 * np.pi * FREQUENCY * t) * 0.5
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)
    return output_path


if __name__ == "__main__":
    path = generate("test.wav")
    print(f"Generated {path} successfully")

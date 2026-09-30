"""
Генератор фикстуры test.wav для голосовых интеграционных тестов.

Создаёт двухсекундную синусоиду 440 Гц (16 кГц, моно) — достаточно для
проверки HTTP-контрактов STT/TTS без реальной речи.
"""

import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 16000
DURATION = 2.0
FREQUENCY = 440  # A4


def generate(output_path: str = "test.wav") -> str:
    """Синтезирует WAV-файл с тоном и сохраняет его по пути.

    Args:
        output_path: путь к создаваемому файлу, по умолчанию "test.wav".

    Returns:
        Путь к записанному файлу (тот же output_path).
    """
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    audio = np.sin(2 * np.pi * FREQUENCY * t) * 0.5
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(output_path, SAMPLE_RATE, audio_int16)
    return output_path


if __name__ == "__main__":
    path = generate("test.wav")
    print(f"Generated {path} successfully")

"""
Утилита шифрования персональных данных (PII) в состоянии покоя.

Использует AES-256-GCM: алгоритм обеспечивает и конфиденциальность,
и аутентичность (tag), что исключает незаметную модификацию зашифрованных данных.

Почему шифруем на уровне приложения, а не БД:
- данные остаются защищёнными даже при утечке дампа PostgreSQL;
- требование 152-ФЗ о защите персональных данных при хранении.

Формат на выходе: base64(nonce(12) || ciphertext || tag(16)).
Алгоритм и упаковка синхронизированы с `decrypt` и тестами `test_crypto.py` —
изменение формата ломает чтение ранее сохранённых данных.
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.src.config import get_settings

logger = logging.getLogger(__name__)

# 32 bytes = AES-256
_KEY_LENGTH = 32
# 12 bytes = standard nonce for GCM
_NONCE_LENGTH = 12


def _get_key() -> bytes:
    """
    Получение 32-байтного ключа AES из эффективного ключа приложения.
    Ключ берётся из настроек (`effective_encryption_key`), а не генерируется:
    это позволяет расшифровать данные после перезапуска без хранения ключа в БД.

    ВАЖНО (подводный камень): ключ короче 32 байт дополняется нулями, длиннее —
    обрезается. Оба случая ослабляют стойкость: длина ключа — ровно 32 байта.
    Returns:
        bytes: ключ длины ровно `_KEY_LENGTH` (32) байта
    """
    settings = get_settings()
    raw = settings.effective_encryption_key.encode("utf-8")
    # If key is shorter than 32 bytes, pad with null bytes; if longer, truncate
    return raw[:_KEY_LENGTH].ljust(_KEY_LENGTH, b"\0")


def encrypt(plaintext: str) -> str:
    """
    Шифрование строки AES-256-GCM.

    Новый случайный nonce на каждый вызов: повтор nonce с тем же ключом раскрывает
    данные и позволяет подделать tag. Формат: base64(nonce||ciphertext||tag).
    Args:
        plaintext: открытый текст (UTF-8)
    Returns:
        base64-строка, пригодная для хранения в БД
    """
    key = _get_key()
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)

    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Pack: nonce || ciphertext || tag
    packed = nonce + ciphertext_with_tag
    return base64.b64encode(packed).decode("ascii")


def decrypt(ciphertext_b64: str) -> str:
    """
    Расшифровка AES-256-GCM-строки в исходный текст.

    Любая ошибка (неверный ключ, повреждённые данные) оборачивается в ValueError
    с общим сообщением — причина не раскрывается вызывающему.
    Args:
        ciphertext_b64: результат `encrypt`
    Returns:
        расшифрованный текст (UTF-8)
    """
    try:
        key = _get_key()
        packed = base64.b64decode(ciphertext_b64)

        if len(packed) < _NONCE_LENGTH:
            raise ValueError("Ciphertext too short")

        nonce = packed[:_NONCE_LENGTH]
        ciphertext_with_tag = packed[_NONCE_LENGTH:]

        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Decryption failed: %s", type(e).__name__)
        raise ValueError("Decryption failed: invalid ciphertext or wrong key") from e


def is_encrypted(value: str) -> bool:
    """
    Эвристика: похоже ли значение на зашифрованное.
    Зашифрованные значения — base64 от nonce(12)+ciphertext+tag(16): минимум
    29 байт → 40 символов. Эвристика, а не гарантия: полную проверку делает `decrypt`.
    Args:
        value: проверяемая строка
    Returns:
        True при длине ≥ 40 и корректном base64
    """
    if len(value) < 40:
        return False
    try:
        decoded = base64.b64decode(value, validate=True)
        return len(decoded) >= _NONCE_LENGTH + 1
    except Exception:
        return False

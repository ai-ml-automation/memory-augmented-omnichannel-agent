"""
Crypto Utility
AES-256-GCM encryption/decryption for PII data at rest.

152-FZ compliance: encrypting personal data before DB storage.
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
    """Derive a 32-byte AES key from effective encryption key."""
    settings = get_settings()
    raw = settings.effective_encryption_key.encode("utf-8")
    # If key is shorter than 32 bytes, pad with null bytes; if longer, truncate
    return raw[:_KEY_LENGTH].ljust(_KEY_LENGTH, b"\0")


def encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext using AES-256-GCM.

    Returns base64-encoded string: nonce(12) + ciphertext + tag(16).

    Args:
        plaintext: String to encrypt

    Returns:
        Base64-encoded ciphertext
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
    Decrypt AES-256-GCM ciphertext.

    Args:
        ciphertext_b64: Base64-encoded ciphertext from encrypt()

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If decryption fails (wrong key, corrupted data)
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
    Quick heuristic to check if a value is likely encrypted.

    Encrypted values are base64 strings with minimum length
    (nonce 12 + tag 16 + at least 1 byte ciphertext = 29 bytes → 40 chars base64).

    Args:
        value: String to check

    Returns:
        True if value looks like encrypted data
    """
    if len(value) < 40:
        return False
    try:
        decoded = base64.b64decode(value, validate=True)
        return len(decoded) >= _NONCE_LENGTH + 1
    except Exception:
        return False

import pytest

from backend.src.utils.crypto import encrypt, decrypt, is_encrypted


class TestEncryptionIntegration:
    """Integration tests for AES-256-GCM encryption (Phase B.1)."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt should return original text."""
        plaintext = "User likes coffee and works at Yandex"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_different_plaintexts_different_ciphertexts(self):
        """Same plaintext encrypted twice should produce different ciphertexts (nonce)."""
        plaintext = "test data"
        enc1 = encrypt(plaintext)
        enc2 = encrypt(plaintext)
        assert enc1 != enc2  # Different nonces
        assert decrypt(enc1) == plaintext
        assert decrypt(enc2) == plaintext

    def test_encryption_with_unicode(self):
        """Russian text should encrypt/decrypt correctly."""
        plaintext = "Пользователь любит кофе и работает в Яндексе"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

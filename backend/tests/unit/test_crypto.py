"""
Unit Tests for crypto utility
AES-256-GCM encrypt/decrypt round-trip, edge cases.
"""

import base64
import os
from unittest.mock import patch

import pytest

from backend.src.utils.crypto import encrypt, decrypt, is_encrypted


class TestEncryptDecrypt:
    def test_round_trip_ascii(self):
        plaintext = "User prefers dark mode"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_unicode(self):
        plaintext = "test unicode value"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_empty_string(self):
        plaintext = ""
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_long_text(self):
        plaintext = "A" * 10000
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_ciphertext_differs_each_time(self):
        plaintext = "Same text"
        c1 = encrypt(plaintext)
        c2 = encrypt(plaintext)
        assert c1 != c2
        assert decrypt(c1) == decrypt(c2) == plaintext

    def test_decrypt_wrong_key_fails(self):
        plaintext = "secret data"
        ciphertext = encrypt(plaintext)
        random_key = os.urandom(32)
        with patch("backend.src.utils.crypto._get_key", return_value=random_key):
            with pytest.raises(ValueError, match="Decryption failed"):
                decrypt(ciphertext)

    def test_decrypt_corrupted_data_fails(self):
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt("AAAAinvalidbase64data")

    def test_decrypt_too_short_fails(self):
        short = base64.b64encode(b"tooshort").decode()
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt(short)


class TestIsEncrypted:
    def test_encrypted_value_detected(self):
        ciphertext = encrypt("test data")
        assert is_encrypted(ciphertext) is True

    def test_plaintext_not_detected(self):
        assert is_encrypted("Hello world") is False

    def test_short_string_not_detected(self):
        assert is_encrypted("abc") is False

    def test_base64_non_encrypted_not_detected(self):
        short_b64 = base64.b64encode(b"short").decode()
        assert is_encrypted(short_b64) is False

    def test_empty_string_not_detected(self):
        assert is_encrypted("") is False


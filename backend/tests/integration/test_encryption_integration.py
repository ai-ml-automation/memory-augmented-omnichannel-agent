"""
Сквозные тесты AES-256-GCM шифрования (Phase B.1).

Проверяют контракт crypto-модуля на уровне API: roundtrip
encrypt→decrypt возвращает исходный текст, каждый вызов encrypt
даёт новый ciphertext (случайный nonce), кириллица шифруется
корректно. Ловит регрессии схемы шифрования без знания реализации.
"""

import pytest

from backend.src.utils.crypto import encrypt, decrypt, is_encrypted


class TestEncryptionIntegration:
    """Группа сквозных тестов шифрования на реальном crypto-модуле.

    Покрывают roundtrip encrypt→decrypt, уникальность ciphertext
    для одного текста (случайный nonce) и корректность кириллицы —
    основной язык системы (152-ФЗ).
    """

    def test_encrypt_decrypt_roundtrip(self):
        """Ловит обрыв цепочки шифрования: decrypt не восстанавливает текст.

        Шифруем русскую фразу про пользователя, расшифровываем и
        сравниваем с оригиналом; шифротекст обязан отличаться.
        """
        plaintext = "User likes coffee and works at Yandex"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_different_plaintexts_different_ciphertexts(self):
        """Ловит фиксированный nonce: одинаковый текст шифруется одинаково.

        AES-256-GCM обязан использовать свежий nonce на каждый вызов —
        иначе ciphertext предсказуем и шифрование теряет смысл.
        """
        plaintext = "test data"
        enc1 = encrypt(plaintext)
        enc2 = encrypt(plaintext)
        assert enc1 != enc2  # Different nonces
        assert decrypt(enc1) == plaintext
        assert decrypt(enc2) == plaintext

    def test_encryption_with_unicode(self):
        """Ловит поломку юникода: кириллица после decrypt искажается.

        Русский текст — основной язык системы (152-ФЗ), поэтому
        сквозная проверка с русской строкой обязательна.
        """
        plaintext = "Пользователь любит кофе и работает в Яндексе"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

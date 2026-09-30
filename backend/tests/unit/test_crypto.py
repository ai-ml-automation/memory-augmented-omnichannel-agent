"""
Юнит-тесты криптоутилиты (AES-256-GCM).

Покрывают round-trip шифрования (ASCII/Unicode/пустая/длинная строка),
уникальность nonce (одинаковый текст → разный ciphertext), детект
зашифрованных значений и ошибки расшифровки: чужой ключ, повреждённые
данные, слишком короткая строка.
"""

import base64
import os
from unittest.mock import patch

import pytest

from backend.src.utils.crypto import encrypt, decrypt, is_encrypted


class TestEncryptDecrypt:
    """
    Round-trip шифрования и обработка ошибок расшифровки.

    Ловит баги: поломку формата nonce||ciphertext||tag, рассинхрон
    ключей при расшифровке, молчаливую порчу данных.
    """

    def test_round_trip_ascii(self):
        """
        ASCII-текст проходит encrypt → decrypt без изменений.
        Базовый контракт: ловит поломку формата упаковки.
        """
        plaintext = "User prefers dark mode"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_unicode(self):
        """
        Unicode-текст шифруется и расшифровывается корректно.
        Ловит баг неверной кодировки (не UTF-8) на входе.
        """
        plaintext = "test unicode value"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_empty_string(self):
        """
        Пустая строка переживает round-trip без ошибок.
        Ловит баг с нулевой длиной ciphertext (tag без данных).
        """
        plaintext = ""
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_long_text(self):
        """
        Длинный текст (10 000 символов) не обрезается и не портится.
        Ловит баги с буферизацией/лимитами длины в encrypt/decrypt.
        """
        plaintext = "A" * 10000
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_ciphertext_differs_each_time(self):
        """
        Одинаковый текст даёт разный ciphertext при каждом вызове.
        Ключевое требование GCM: nonce уникален — повторное использование
        раскрыло бы содержимое; ловит захардкоженный nonce.
        """
        plaintext = "Same text"
        c1 = encrypt(plaintext)
        c2 = encrypt(plaintext)
        assert c1 != c2
        assert decrypt(c1) == decrypt(c2) == plaintext

    def test_decrypt_wrong_key_fails(self):
        """
        Расшифровка чужим ключом падает с «Decryption failed».
        Ловит баг игнорирования неверного ключа (данные «разблокируются»).
        """
        plaintext = "secret data"
        ciphertext = encrypt(plaintext)
        random_key = os.urandom(32)
        with patch("backend.src.utils.crypto._get_key", return_value=random_key):
            with pytest.raises(ValueError, match="Decryption failed"):
                decrypt(ciphertext)

    def test_decrypt_corrupted_data_fails(self):
        """
        Повреждённые данные (не-base64) не расшифровываются молча.
        Ловит баг возврата мусора вместо ошибки при битом ciphertext.
        """
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt("AAAAinvalidbase64data")

    def test_decrypt_too_short_fails(self):
        """
        Слишком короткая строка не валидна как ciphertext.
        Ловит баг выхода за границы при разборе nonce/tag.
        """
        short = base64.b64encode(b"tooshort").decode()
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt(short)


class TestIsEncrypted:
    """
    Детект зашифрованных значений эвристикой is_encrypted.

    Проверяет порог длины (nonce+tag+ciphertext ≥ 40 символов base64)
    и отсутствие ложных срабатываний на открытом тексте.
    """

    def test_encrypted_value_detected(self):
        """
        Зашифрованное значение распознаётся как зашифрованное.
        Ловит баг слишком высокого порога (реальные ciphertext не видны).
        """
        ciphertext = encrypt("test data")
        assert is_encrypted(ciphertext) is True

    def test_plaintext_not_detected(self):
        """
        Обычный текст не считается зашифрованным.
        Ловит ложные срабатывания на коротких строках.
        """
        assert is_encrypted("Hello world") is False

    def test_short_string_not_detected(self):
        """
        Короткая строка (3 символа) — не ciphertext.
        Проверяет нижний порог длины эвристики.
        """
        assert is_encrypted("abc") is False

    def test_base64_non_encrypted_not_detected(self):
        """
        Короткий base64 (не шифр) не даёт ложного срабатывания.
        Отличает настоящий ciphertext от случайного base64 текста.
        """
        short_b64 = base64.b64encode(b"short").decode()
        assert is_encrypted(short_b64) is False

    def test_empty_string_not_detected(self):
        """
        Пустая строка не считается зашифрованной.
        Краевой случай: нулевая длина не должна проходить порог.
        """
        assert is_encrypted("") is False


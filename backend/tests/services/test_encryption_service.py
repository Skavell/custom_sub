import pytest
from app.services.encryption_service import encrypt_value, decrypt_value


def test_encrypt_decrypt_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    plaintext = "super_secret_token_abc123"
    ciphertext = encrypt_value(key, plaintext)
    assert ciphertext != plaintext
    assert decrypt_value(key, ciphertext) == plaintext


def test_wrong_key_raises():
    key_a = "key-a-for-encryption-32-chars!!!"
    key_b = "key-b-for-encryption-32-chars!!!"
    ciphertext = encrypt_value(key_a, "secret")
    with pytest.raises(Exception):
        decrypt_value(key_b, ciphertext)


def test_empty_string_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    assert decrypt_value(key, encrypt_value(key, "")) == ""


def test_unicode_string_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    plaintext = "секретный токен 🔑"
    assert decrypt_value(key, encrypt_value(key, plaintext)) == plaintext


def test_nonce_uniqueness():
    """Two encryptions of same plaintext produce different ciphertexts."""
    key = "test-key-for-encryption-32-chars!"
    c1 = encrypt_value(key, "same")
    c2 = encrypt_value(key, "same")
    assert c1 != c2

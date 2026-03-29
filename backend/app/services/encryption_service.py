import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(key_str: str) -> bytes:
    """Derive exactly 32 bytes from the config string via SHA-256.

    NOTE: This assumes key_str is a high-entropy random secret (from .env),
    NOT a user-chosen password. Do not use this with low-entropy inputs.
    """
    return hashlib.sha256(key_str.encode()).digest()


def encrypt_value(key_str: str, plaintext: str) -> str:
    """AES-256-GCM encrypt. Returns base64(12-byte nonce + ciphertext+tag)."""
    key = _derive_key(key_str)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(key_str: str, encoded: str) -> str:
    """AES-256-GCM decrypt.
    Raises InvalidTag if key is wrong or data is tampered.
    Raises ValueError if encoded is not valid base64.
    """
    import binascii
    key = _derive_key(key_str)
    try:
        data = base64.b64decode(encoded)
    except binascii.Error as exc:
        raise ValueError(f"Invalid base64 ciphertext: {exc}") from exc
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
